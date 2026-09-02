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

            # Collection of targets to process: list of dicts {id, image_url, thumbnail_url, get_bytes_fn}
            work_items: List[Dict] = []

            # 1. Scrape Folder file IDs directly without downloading files to storage
            for folder_id in folder_ids:
                print(f"[Drive Import] Scanning Google Drive Folder ID: {folder_id} for direct CDN streaming...")
                folder_items = google_drive_helper.list_folder_files(folder_id)
                for item in folder_items:
                    fid = item.get("id")
                    if fid:
                        work_items.append({
                            "id": fid,
                            "image_url": f"https://lh3.googleusercontent.com/d/{fid}=w2048",
                            "thumbnail_url": f"https://lh3.googleusercontent.com/d/{fid}=w600",
                            "type": "drive_id",
                            "source": fid
                        })

            # 2. Add individual Drive file IDs
            for fid in file_ids:
                if not any(w["id"] == fid for w in work_items):
                    work_items.append({
                        "id": fid,
                        "image_url": f"https://lh3.googleusercontent.com/d/{fid}=w2048",
                        "thumbnail_url": f"https://lh3.googleusercontent.com/d/{fid}=w600",
                        "type": "drive_id",
                        "source": fid
                    })

            # 3. Add direct URLs
            for u in direct_urls:
                u_fid, _ = google_drive_helper.extract_id(u)
                if u_fid:
                    work_items.append({
                        "id": u_fid,
                        "image_url": f"https://lh3.googleusercontent.com/d/{u_fid}=w2048",
                        "thumbnail_url": f"https://lh3.googleusercontent.com/d/{u_fid}=w600",
                        "type": "drive_id",
                        "source": u_fid
                    })
                else:
                    work_items.append({
                        "id": str(uuid.uuid4()),
                        "image_url": u,
                        "thumbnail_url": u,
                        "type": "direct_url",
                        "source": u
                    })

            # 4. Fallback: If scraping returned 0 items from folder, use concurrent folder downloader
            if not work_items and (folder_ids or file_ids):
                for folder_id in folder_ids:
                    f_paths = self._download_drive_folder(folder_id, clean_url, temp_dir)
                    downloaded_image_paths.extend(f_paths)

                for fid in file_ids:
                    p = self._download_single_drive_file(fid, temp_dir)
                    if p:
                        downloaded_image_paths.append(p)

                downloaded_image_paths = list(dict.fromkeys(downloaded_image_paths))
                for p in downloaded_image_paths:
                    # Extract file_id if present in filename
                    f_match = re.search(r'drive_([a-zA-Z0-9_-]{20,})', p)
                    if f_match:
                        fid = f_match.group(1)
                        img_u = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
                        thumb_u = f"https://lh3.googleusercontent.com/d/{fid}=w600"
                    else:
                        img_u = storage_service.resolve_image_url(os.path.basename(p), is_thumbnail=False)
                        thumb_u = storage_service.resolve_image_url(os.path.basename(p), is_thumbnail=True)

                    work_items.append({
                        "id": str(uuid.uuid4()),
                        "image_url": img_u,
                        "thumbnail_url": thumb_u,
                        "type": "local_path",
                        "source": p
                    })

            if not work_items:
                err_msg = "Could not find accessible images in the provided Google Drive link. Please ensure folder sharing is set to 'Anyone with the link can view' (Public)."
                if task_id:
                    task_tracker.update_task(task_id, status="failed", error=err_msg, progress_message="Folder scan failed.")
                return {
                    "success": False,
                    "imported_count": 0,
                    "total_faces": 0,
                    "message": err_msg
                }

            total_photos = len(work_items)
            print(f"[Drive Import] Found {total_photos} photos. Starting in-memory zero-storage ML analysis...")

            if task_id:
                task_tracker.update_task(
                    task_id,
                    status="indexing",
                    total=total_photos,
                    current=0,
                    progress_message=f"Analyzing and indexing 0/{total_photos} photos directly from Drive..."
                )

            # In-memory streaming analysis: 0 Supabase storage, 0 disk storage
            imported_count = 0
            total_faces = 0

            def _process_item(item: Dict) -> Optional[int]:
                try:
                    img_bytes = None
                    item_type = item.get("type")
                    source = item.get("source")

                    if item_type == "drive_id":
                        img_bytes = google_drive_helper.download_file_bytes(source)
                    elif item_type == "direct_url":
                        headers = {"User-Agent": "Mozilla/5.0"}
                        resp = requests.get(source, timeout=12, headers=headers)
                        if resp.status_code == 200:
                            img_bytes = resp.content
                    elif item_type == "local_path" and os.path.exists(source):
                        with open(source, "rb") as f:
                            img_bytes = f.read()

                    if not img_bytes or not GoogleDriveHelper.is_valid_image_bytes(img_bytes):
                        return None

                    # Extract 512-d FaceNet embeddings directly in memory
                    faces = ml_engine.extract_faces_and_embeddings(img_bytes)

                    # Store in DB pointing to Google Drive CDN URLs (Zero Supabase storage used)
                    db_service.insert_photo_and_embeddings(
                        event_id=event_id,
                        image_url=item["image_url"],
                        thumbnail_url=item["thumbnail_url"],
                        faces=faces
                    )

                    del img_bytes
                    return len(faces)
                except Exception as item_err:
                    print(f"[Drive Import Warning] Failed processing item {item.get('id')}: {item_err}")
                    return None

            with ThreadPoolExecutor(max_workers=6, thread_name_prefix="drive_streamer") as executor:
                futures = {executor.submit(_process_item, it): it for it in work_items}
                for future in as_completed(futures):
                    face_cnt = future.result()
                    if face_cnt is not None:
                        imported_count += 1
                        total_faces += face_cnt
                        if task_id:
                            task_tracker.update_task(
                                task_id,
                                current=imported_count,
                                faces_detected=total_faces,
                                progress_message=f"Analyzed {imported_count}/{total_photos} photos directly from Drive ({total_faces} faces indexed)..."
                            )

            # Invalidate event cache so vector search matrix is instantly updated
            db_service.invalidate_event_cache(event_id)

            # Compute person clusters
            try:
                self.clustering_engine.compute_event_clusters(event_id)
            except Exception as e:
                print(f"[Drive Import Warning] Auto-clustering notice: {e}")

            if task_id:
                task_tracker.update_task(
                    task_id,
                    status="completed",
                    current=imported_count,
                    faces_detected=total_faces,
                    progress_message=f"Analysis complete! {imported_count} photos linked from Google Drive with {total_faces} face vectors."
                )

            return {
                "success": True,
                "imported_count": imported_count,
                "total_faces": total_faces,
                "task_id": task_id,
                "message": f"Successfully analyzed {imported_count} photos directly from Google Drive (0 MB Supabase storage used) and indexed {total_faces} face embeddings!"
            }

        except Exception as ex:
            if task_id:
                task_tracker.update_task(task_id, status="failed", error=str(ex), progress_message="Indexing error encountered.")
            raise ex

        finally:
            # Clean up any temporary files immediately
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
