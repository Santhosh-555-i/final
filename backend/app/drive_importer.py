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
from app.google_drive_api import google_drive_helper, GoogleDriveHelper
from app.clustering import FaceClusteringEngine
from app.sync_tracker import task_tracker


class GoogleDriveImporter:
    """
    High-performance Google Drive importer supporting public folders, individual file links,
    and lists of Drive URLs. Downloads concurrently, generates thumbnails, detects faces,
    extracts 512-d vector embeddings, and indexes them into the database with live progress tracking.
    """

    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.heic', '.jfif', '.avif'}

    def __init__(self):
        self.clustering_engine = FaceClusteringEngine(
            db_service.db_path if settings.DB_MODE == "sqlite" else None
        )

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
        processes ML embeddings, computes person clusters, and saves into event gallery with live progress updates.
        """
        clean_url = drive_url.strip()
        if not clean_url:
            if task_id:
                task_tracker.update_task(task_id, status="failed", error="No Drive URL provided.", progress_message="No Drive URL provided.")
            return {"success": False, "imported_count": 0, "total_faces": 0, "message": "No Drive URL provided."}

        # Update event record with drive link
        try:
            db_service.update_event_drive_link(event_id, clean_url)
        except Exception:
            pass

        if task_id:
            task_tracker.update_task(
                task_id,
                status="downloading",
                progress_message="Connecting to Google Drive and scanning folder contents..."
            )

        temp_dir = tempfile.mkdtemp(prefix="eventlens_drive_")
        downloaded_image_paths: List[str] = []

        try:
            # Check if user entered multiple URLs separated by newlines, commas, semicolons, or spaces
            raw_urls = [u.strip() for u in re.split(r'[\n,;\s]+', clean_url) if u.strip().startswith("http") or len(u.strip()) >= 20]
            if not raw_urls:
                raw_urls = [clean_url]

            folder_ids: Set[str] = set()
            file_ids: Set[str] = set()
            direct_urls: Set[str] = set()

            for u in raw_urls:
                f_id, f_type = google_drive_helper.extract_id(u)
                if f_id:
                    if f_type == "folder":
                        folder_ids.add(f_id)
                    elif f_type == "file":
                        file_ids.add(f_id)
                    else: # "id" (could be folder or file)
                        folder_ids.add(f_id)
                        file_ids.add(f_id)
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

            # 4. Fallback: If 0 files found and we had candidate folder IDs, try downloading them as single files
            if not downloaded_image_paths and folder_ids:
                for fid in folder_ids:
                    path = self._download_single_drive_file(fid, temp_dir)
                    if path:
                        downloaded_image_paths.append(path)

            # Deduplicate paths
            downloaded_image_paths = list(dict.fromkeys(downloaded_image_paths))

            if not downloaded_image_paths:
                err_msg = "Could not download images from the provided Google Drive link. Please ensure folder sharing is set to 'Anyone with the link can view' (Public) or provide valid image URLs."
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
                    if not GoogleDriveHelper.is_valid_image_bytes(image_bytes):
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
                finally:
                    del image_bytes
                    import gc
                    gc.collect()

            # Automatically compute person clusters so "People" tab is immediately populated
            try:
                self.clustering_engine.compute_event_clusters(event_id)
                print(f"[Drive Import] Person clusters computed for event {event_id}.")
            except Exception as e:
                print(f"[Drive Import Warning] Auto-clustering notice: {e}")

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
        """Downloads all images from a public Google Drive folder fast with concurrent streams & gdown fallback"""
        results: List[str] = []

        # Attempt 1: Direct concurrent scraping & stream download (sub-second)
        try:
            items = google_drive_helper.list_folder_files(folder_id)
            if items:
                print(f"[Drive Importer] Retrieved {len(items)} items from Drive Helper. Downloading concurrently...")
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(self._download_single_drive_file, item["id"], output_dir): item["id"]
                        for item in items[:150]
                    }
                    for future in as_completed(futures):
                        try:
                            path = future.result()
                            if path:
                                results.append(path)
                        except Exception:
                            pass
                if results:
                    return results
        except Exception as e:
            print(f"[Drive Importer Scraper Notice] {e}")

        # Attempt 2: gdown download_folder fallback
        try:
            import gdown
            folder_out_dir = os.path.join(output_dir, f"folder_{folder_id}")
            os.makedirs(folder_out_dir, exist_ok=True)
            
            # Try with URL
            try:
                gdown.download_folder(
                    url=f"https://drive.google.com/drive/folders/{folder_id}", 
                    output=folder_out_dir, 
                    quiet=True, 
                    use_cookies=True
                )
            except Exception:
                gdown.download_folder(
                    id=folder_id, 
                    output=folder_out_dir, 
                    quiet=True, 
                    use_cookies=True
                )
            
            for root, _, files in os.walk(folder_out_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    full_p = os.path.join(root, file)
                    if ext in self.IMAGE_EXTENSIONS:
                        results.append(full_p)
                    else:
                        # Check extensionless file
                        try:
                            if os.path.getsize(full_p) > 1000:
                                with open(full_p, "rb") as test_f:
                                    if GoogleDriveHelper.is_valid_image_bytes(test_f.read(1024)):
                                        results.append(full_p)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Drive Importer Notice] gdown folder download attempt: {e}")

        return results

    def _download_single_drive_file(self, file_id: str, output_dir: str) -> Optional[str]:
        """Downloads single file by Google Drive File ID fast with concurrent endpoints"""
        dest_file = os.path.join(output_dir, f"drive_{file_id}.jpg")
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 1000:
            return dest_file

        data = google_drive_helper.download_file_bytes(file_id)
        if data and len(data) > 500:
            with open(dest_file, "wb") as f:
                f.write(data)
            return dest_file

        return None

    def _download_direct_url(self, url: str, output_dir: str) -> Optional[str]:
        """Downloads direct image URL fast (supports Dropbox, S3, Cloudinary, Imgur, etc.)"""
        try:
            # Handle Dropbox dl=0 -> dl=1
            fetch_url = url
            if "dropbox.com" in fetch_url and "dl=0" in fetch_url:
                fetch_url = fetch_url.replace("dl=0", "dl=1")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            resp = requests.get(fetch_url, timeout=12, headers=headers, allow_redirects=True)
            if resp.status_code == 200 and GoogleDriveHelper.is_valid_image_bytes(resp.content):
                filename = f"web_img_{abs(hash(url)) % 1000000}.jpg"
                dest_file = os.path.join(output_dir, filename)
                with open(dest_file, "wb") as f:
                    f.write(resp.content)
                return dest_file
        except Exception as e:
            print(f"[Drive Importer] Direct URL download error {url}: {e}")
        return None

drive_importer = GoogleDriveImporter()
