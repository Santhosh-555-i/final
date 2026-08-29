import os
import uuid
import re
from PIL import Image
import io
import requests
from typing import Optional, Tuple
from app.config import settings

class StorageService:
    def __init__(self):
        self.bucket_name = settings.SUPABASE_BUCKET_NAME
        self.supabase = None
        
        if settings.DB_MODE == "supabase" and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                from supabase import create_client
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
                self._ensure_bucket()
                print(f"[Storage] Connected to Supabase Storage (bucket='{self.bucket_name}')")
            except Exception as e:
                print(f"[Storage Warning] Could not initialize Supabase Storage: {e}")
        else:
            print("[Storage] Using local filesystem storage")

    def _ensure_bucket(self):
        """Ensures the photos bucket exists in Supabase Storage."""
        if not self.supabase:
            return
        try:
            # Check if bucket exists or create it
            self.supabase.storage.create_bucket(self.bucket_name, options={"public": True})
        except Exception:
            # Bucket likely already exists
            pass

    def extract_clean_filename(self, path_or_url: str) -> str:
        """Extracts base filename from any path or Supabase / static URL."""
        if not path_or_url:
            return ""
        # Remove query parameters
        clean = path_or_url.split("?")[0].strip()
        # Remove leading prefixes
        clean = re.sub(r"^.*?/(raw|thumbnails|photos)/", "", clean)
        clean = clean.replace("/static/raw/", "").replace("/static/thumbnails/", "").replace("/static/", "")
        clean = os.path.basename(clean)
        return clean

    def resolve_image_url(self, url_or_path: str, is_thumbnail: bool = False, expires_in: int = 604800) -> str:
        """
        Resolves any stored photo path or URL into a valid production URL:
        - If already a valid full https:// URL to Supabase or CDN, keeps it.
        - If DB_MODE is supabase and path is legacy '/static/raw/photo_xyz.jpg', converts to Supabase URL.
        - If DB_MODE is sqlite, ensures relative '/static/...' path.
        """
        if not url_or_path:
            return "/placeholder.jpg"

        # If it's already an absolute URL
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return url_or_path

        clean_filename = self.extract_clean_filename(url_or_path)
        if not clean_filename:
            return url_or_path

        # If running in Supabase mode
        if settings.DB_MODE == "supabase":
            if self.supabase:
                try:
                    # Get public URL from Supabase bucket
                    public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(clean_filename)
                    if public_url:
                        return public_url
                except Exception as e:
                    print(f"[Storage Warning] Failed to get Supabase public URL for {clean_filename}: {e}")
            
            # Fallback to backend photo streaming endpoint
            endpoint = "thumbnail" if (is_thumbnail or clean_filename.startswith("thumb_")) else "file"
            return f"/api/photos/{endpoint}/{clean_filename}"

        # SQLite / Local mode
        if is_thumbnail or clean_filename.startswith("thumb_"):
            return f"/static/thumbnails/{clean_filename}"
        return f"/static/raw/{clean_filename}"

    def save_photo_and_thumbnail(self, image_bytes: bytes, filename: str) -> Tuple[str, str]:
        """
        Saves raw image bytes and generates a thumbnail.
        Returns: (image_url, thumbnail_url)
        """
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            file_ext = '.jpg'

        unique_id = str(uuid.uuid4())
        raw_filename = f"photo_{unique_id}{file_ext}"
        thumb_filename = f"thumb_{unique_id}{file_ext}"

        # Generate optimized thumbnail (400px JPEG)
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG", quality=85)
            thumb_bytes = thumb_io.getvalue()
        except Exception as img_err:
            print(f"[Storage Warning] Thumbnail generation fallback: {img_err}")
            thumb_bytes = image_bytes

        # 1. Supabase Storage Mode
        if settings.DB_MODE == "supabase" and self.supabase:
            try:
                # Upload raw image to Supabase
                self.supabase.storage.from_(self.bucket_name).upload(
                    path=raw_filename,
                    file=image_bytes,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )
                # Upload thumbnail to Supabase
                self.supabase.storage.from_(self.bucket_name).upload(
                    path=thumb_filename,
                    file=thumb_bytes,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )

                raw_url = self.supabase.storage.from_(self.bucket_name).get_public_url(raw_filename)
                thumb_url = self.supabase.storage.from_(self.bucket_name).get_public_url(thumb_filename)
                
                print(f"[Storage] Successfully uploaded photo {raw_filename} to Supabase bucket '{self.bucket_name}'")
                return raw_url, thumb_url
            except Exception as upload_err:
                print(f"[Storage Error] Supabase upload error: {upload_err}. Attempting auto-recovery...")
                try:
                    self._ensure_bucket()
                    self.supabase.storage.from_(self.bucket_name).upload(
                        path=raw_filename,
                        file=image_bytes,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                    self.supabase.storage.from_(self.bucket_name).upload(
                        path=thumb_filename,
                        file=thumb_bytes,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                    raw_url = self.supabase.storage.from_(self.bucket_name).get_public_url(raw_filename)
                    thumb_url = self.supabase.storage.from_(self.bucket_name).get_public_url(thumb_filename)
                    return raw_url, thumb_url
                except Exception as retry_err:
                    print(f"[Storage Error] Supabase retry failed: {retry_err}")
                    # Fallback to backend streaming URL if direct CDN fails
                    return f"/api/photos/file/{raw_filename}", f"/api/photos/thumbnail/{thumb_filename}"

        # 2. Local Filesystem Storage (for SQLite local development)
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "raw"), exist_ok=True)
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails"), exist_ok=True)

        raw_path = os.path.join(settings.LOCAL_STORAGE_DIR, "raw", raw_filename)
        thumb_path = os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails", thumb_filename)

        with open(raw_path, "wb") as f:
            f.write(image_bytes)

        with open(thumb_path, "wb") as f:
            f.write(thumb_bytes)

        raw_url = f"/static/raw/{raw_filename}"
        thumb_url = f"/static/thumbnails/{thumb_filename}"
        return raw_url, thumb_url

    def get_photo_bytes(self, url_or_path: str) -> Optional[bytes]:
        """
        Fetches photo binary bytes from local disk, Supabase Storage, or remote URL.
        Guarantees that ZIP downloads and image proxy endpoints always receive valid data.
        """
        if not url_or_path:
            return None

        clean_filename = self.extract_clean_filename(url_or_path)

        # Check local storage directory first if it exists
        if clean_filename:
            is_thumb = clean_filename.startswith("thumb_")
            sub_folder = "thumbnails" if is_thumb else "raw"
            local_file = os.path.join(settings.LOCAL_STORAGE_DIR, sub_folder, clean_filename)
            if os.path.exists(local_file):
                try:
                    with open(local_file, "rb") as f:
                        return f.read()
                except Exception:
                    pass

        # If Supabase client is available, try downloading from Supabase storage
        if self.supabase and clean_filename:
            try:
                data = self.supabase.storage.from_(self.bucket_name).download(clean_filename)
                if data and len(data) > 0:
                    return data
            except Exception as sb_err:
                print(f"[Storage] Supabase download attempt for {clean_filename}: {sb_err}")

        # If it is a full remote HTTP URL
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            try:
                resp = requests.get(url_or_path, timeout=10)
                if resp.status_code == 200 and len(resp.content) > 0:
                    return resp.content
            except Exception as http_err:
                print(f"[Storage] Remote HTTP fetch error for {url_or_path}: {http_err}")

        return None

    def delete_photo_files(self, raw_url: str, thumb_url: str) -> None:
        """Deletes photo files from Supabase or Local Storage."""
        raw_clean = self.extract_clean_filename(raw_url)
        thumb_clean = self.extract_clean_filename(thumb_url)

        if settings.DB_MODE == "supabase" and self.supabase:
            try:
                paths = [p for p in (raw_clean, thumb_clean) if p]
                if paths:
                    self.supabase.storage.from_(self.bucket_name).remove(paths)
            except Exception as e:
                print(f"[Storage Error] Failed to delete from Supabase storage: {e}")

        # Clean local files if present
        for clean, folder in [(raw_clean, "raw"), (thumb_clean, "thumbnails")]:
            if clean:
                full = os.path.join(settings.LOCAL_STORAGE_DIR, folder, clean)
                if os.path.exists(full):
                    try:
                        os.remove(full)
                    except Exception:
                        pass

storage_service = StorageService()
