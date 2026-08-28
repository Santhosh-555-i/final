import os
import re
import shutil
import tempfile
import uuid
import urllib.parse
import requests
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

from app.database import db_service
from app.storage import storage_service
from app.ml_engine import ml_engine
from app.config import settings
from app.google_drive_api import google_drive_helper

class SyncTaskTracker:
    """Stores in-memory status for real-time indexing and sync tracking"""
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}

    def create_task(self, event_id: str) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "task_id": task_id,
            "event_id": event_id,
            "status": "pending",
            "progress_message": "Initializing Google Drive connection...",
            "current": 0,
            "total": 0,
            "faces_detected": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "error": None
        }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)
            self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()

    def get_task(self, task_id: str) -> Optional[Dict]:
        return self.tasks.get(task_id)

task_tracker = SyncTaskTracker()


class GoogleDriveImporter:
    """
    High-performance Google Drive importer supporting public folders, individual file links,
    and lists of Drive URLs. Downloads concurrently, generates thumbnails, detects faces,
    extracts 512-d vector embeddings, and indexes them into the database with live progress tracking.
    """

    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.heic'}

    @staticmethod
    def extract_drive_folder_id(url: str) -> Optional[str]:
        """Extracts folder ID from various Google Drive folder URL formats"""
        fid, ftype = google_drive_helper.extract_id(url)
        return fid if ftype in ("folder", "id") else None

    @staticmethod
    def extract_drive_file_id(url: str) -> Optional[str]:
        """Extracts file ID from Google Drive file URL"""
        fid, ftype = google_drive_helper.extract_id(url)
        return fid if ftype in ("file", "id") else None

    def import_from_drive_link(
        self, 
        event_id: str, 
        drive_url: str, 
        task_id: Optional[str] = None
    ) -> Dict:
        """
        Main entrypoint: parses the drive URL(s), downloads all images concurrently,
        processes ML embeddings, and saves into event gallery with live progress updates.
        """
        clean_url = drive_url.strip()
        if not clean_url:
            if task_id:
                task_tracker.update_task(task_id, status="failed", error="No Drive URL provided.")
            return {"success": False, "imported_count": 0, "total_faces": 0, "message": "No Drive URL provided."}

        # Update event record with drive link
        db_service.update_event_drive_link(event_id, clean_url)

        if task_id:
            task_tracker.update_task(
                task_id,
                status="downloading",
                progress_message="Connecting to Google Drive and scanning folder contents..."
            )

        temp_dir = tempfile.mkdtemp(prefix="eventlens_drive_")
        downloaded_image_paths: List[str] = []

        try:
            # Check if user entered multiple URLs separated by newlines, commas, or spaces
            raw_urls = [u.strip() for u in re.split(r'[\n,\s]+', clean_url) if u.strip().startswith("http")]
            if not raw_urls:
                raw_urls = [clean_url]

            folder_ids: Set[str] = set()
            file_ids: Set[str] = set()
            direct_urls: Set[str] = set()

            for u in raw_urls:
                f_id = self.extract_drive_folder_id(u)
                if f_id:
                    folder_ids.add(f_id)
                    continue

                fl_id = self.extract_drive_file_id(u)
                if fl_id:
                    file_ids.add(fl_id)
                    continue

                if u.startswith("http://") or u.startswith("https://"):
                    direct_urls.add(u)

            # 1. Download Folders
            for folder_id in folder_ids:
                print(f"[Drive Import] Processing Google Drive Folder ID: {folder_id}")
                f_paths = self._download_drive_folder(folder_id, clean_url, temp_dir)
                downloaded_image_paths.extend(f_paths)

            # 2. Download Individual Drive Files concurrently
            if file_ids:
                print(f"[Drive Import] Downloading {len(file_ids)} direct Drive files concurrently...")
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {
                        executor.submit(self._download_single_drive_file, fid, temp_dir): fid
                        for fid in file_ids
                    }
                    for future in as_completed(futures):
                        try:
                            path = future.result()
                            if path:
                                downloaded_image_paths.append(path)
                        except Exception as e:
                            print(f"[Drive Importer] File download error: {e}")

            # 3. Download Direct URLs
            if direct_urls:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {
                        executor.submit(self._download_direct_url, u, temp_dir): u
                        for u in direct_urls
                    }
                    for future in as_completed(futures):
                        try:
                            path = future.result()
                            if path:
                                downloaded_image_paths.append(path)
                        except Exception as e:
                            print(f"[Drive Importer] Direct URL download error: {e}")

            # Deduplicate paths
            downloaded_image_paths = list(dict.fromkeys(downloaded_image_paths))

            if not downloaded_image_paths:
                err_msg = "Could not download images from the provided Google Drive link. Please ensure folder sharing is set to 'Anyone with the link can view' (Public) or provide valid Google Drive credentials."
                if task_id:
                    task_tracker.update_task(task_id, status="failed", error=err_msg, progress_message="Download failed.")
                return {
                    "success": False,
                    "imported_count": 0,
                    "total_faces": 0,
                    "message": err_msg
                }

            total_photos = len(downloaded_image_paths)
            print(f"[Drive Import] Successfully downloaded {total_photos} images. Starting FaceNet vector indexing...")

            if task_id:
                task_tracker.update_task(
                    task_id,
                    status="indexing",
                    total=total_photos,
                    current=0,
                    progress_message=f"Indexing 0/{total_photos} photos..."
                )

            # Process each downloaded image into the gallery with live progress updates
            imported_count = 0
            total_faces = 0

            for idx, img_path in enumerate(downloaded_image_paths, 1):
                try:
                    if not os.path.exists(img_path) or os.path.getsize(img_path) < 500:
                        continue

                    with open(img_path, "rb") as f:
                        image_bytes = f.read()

                    # Verify image validity
                    try:
                        with Image.open(img_path) as test_img:
                            test_img.verify()
                    except Exception:
                        continue

                    # 1. Save raw image & thumbnail
                    filename = os.path.basename(img_path)
                    image_url, thumbnail_url = storage_service.save_photo_and_thumbnail(image_bytes, filename)

                    # 2. Extract faces & 512-d embeddings
                    faces = ml_engine.extract_faces_and_embeddings(image_bytes)

                    # 3. Store in DB
                    db_service.insert_photo_and_embeddings(
                        event_id=event_id,
                        image_url=image_url,
                        thumbnail_url=thumbnail_url,
                        faces=faces
                    )

                    imported_count += 1
                    total_faces += len(faces)

                    # Update live progress
                    if task_id:
                        task_tracker.update_task(
                            task_id,
                            current=imported_count,
                            faces_detected=total_faces,
                            progress_message=f"Indexing {imported_count}/{total_photos} photos ({total_faces} faces detected)..."
                        )
                except Exception as e:
                    print(f"[Drive Import Warning] Failed to process photo {img_path}: {e}")

            if task_id:
                task_tracker.update_task(
                    task_id,
                    status="completed",
                    current=imported_count,
                    faces_detected=total_faces,
                    progress_message=f"Indexing complete! {imported_count} photos indexed with {total_faces} face vectors."
                )

            return {
                "success": True,
                "imported_count": imported_count,
                "total_faces": total_faces,
                "task_id": task_id,
                "message": f"Successfully imported {imported_count} photos and indexed {total_faces} face embeddings from Google Drive!"
            }

        except Exception as ex:
            if task_id:
                task_tracker.update_task(task_id, status="failed", error=str(ex), progress_message="Indexing error encountered.")
            raise ex

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _download_drive_folder(self, folder_id: str, folder_url: str, output_dir: str) -> List[str]:
        """Downloads all images from a public Google Drive folder using gdown and targeted web scraper"""
        results: List[str] = []

        # Attempt 1: gdown download_folder with fast execution
        try:
            import gdown
            print(f"[Drive Importer] Running gdown folder download for {folder_id}...")
            folder_out_dir = os.path.join(output_dir, f"folder_{folder_id}")
            os.makedirs(folder_out_dir, exist_ok=True)
            
            gdown.download_folder(
                id=folder_id, 
                output=folder_out_dir, 
                quiet=True, 
                use_cookies=False
            )
            
            for root, _, files in os.walk(folder_out_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.IMAGE_EXTENSIONS:
                        results.append(os.path.join(root, file))

            if results:
                print(f"[Drive Importer] gdown folder download retrieved {len(results)} images.")
                return results
        except Exception as e:
            print(f"[Drive Importer Notice] gdown folder download attempt: {e}")

        # Attempt 2: Targeted Public Google Drive folder items
        try:
            items = google_drive_helper.list_folder_files(folder_id)
            if items:
                print(f"[Drive Importer] Retrieved {len(items)} items from Drive Helper. Downloading concurrently...")
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {
                        executor.submit(self._download_single_drive_file, item["id"], output_dir): item["id"]
                        for item in items[:100]
                    }
                    for future in as_completed(futures):
                        try:
                            path = future.result()
                            if path:
                                results.append(path)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Drive Importer Scraper Notice] {e}")

        return results

    def _download_single_drive_file(self, file_id: str, output_dir: str) -> Optional[str]:
        """Downloads single file by Google Drive File ID fast with concurrent endpoints"""
        dest_file = os.path.join(output_dir, f"drive_{file_id}.jpg")
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 1000:
            return dest_file

        data = google_drive_helper.download_file_bytes(file_id)
        if data and len(data) > 1500:
            with open(dest_file, "wb") as f:
                f.write(data)
            return dest_file

        return None

    def _download_direct_url(self, url: str, output_dir: str) -> Optional[str]:
        """Downloads direct image URL fast"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, timeout=8, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 1000:
                filename = f"web_img_{abs(hash(url)) % 100000}.jpg"
                dest_file = os.path.join(output_dir, filename)
                with open(dest_file, "wb") as f:
                    f.write(resp.content)
                return dest_file
        except Exception as e:
            print(f"[Drive Importer] Direct URL download error {url}: {e}")
        return None

drive_importer = GoogleDriveImporter()
