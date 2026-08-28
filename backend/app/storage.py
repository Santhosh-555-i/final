import os
import uuid
from PIL import Image
import io
from app.config import settings

class StorageService:
    def __init__(self):
        if settings.DB_MODE == "supabase":
            try:
                from supabase import create_client
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
                print("[Storage] Connected to Supabase Storage service")
            except Exception as e:
                raise RuntimeError(f"[Storage Error] Could not initialize Supabase Storage: {e}")
        else:
            self.supabase = None
            print("[Storage] Using local SQLite/filesystem storage")

    def save_photo_and_thumbnail(self, image_bytes: bytes, filename: str) -> tuple[str, str]:
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

        # Generate thumbnail
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        thumb_io = io.BytesIO()
        img.save(thumb_io, format="JPEG", quality=85)
        thumb_bytes = thumb_io.getvalue()

        if settings.DB_MODE == "supabase":
            try:
                # Upload to Supabase bucket 'photos' using service role
                self.supabase.storage.from_("photos").upload(
                    path=raw_filename,
                    file=image_bytes,
                    file_options={"content-type": "image/jpeg"}
                )
                self.supabase.storage.from_("photos").upload(
                    path=thumb_filename,
                    file=thumb_bytes,
                    file_options={"content-type": "image/jpeg"}
                )
                raw_url = self.supabase.storage.from_("photos").get_public_url(raw_filename)
                thumb_url = self.supabase.storage.from_("photos").get_public_url(thumb_filename)
                return raw_url, thumb_url
            except Exception as e:
                raise RuntimeError(f"[Storage Error] Supabase upload failed: {e}")

        # Local storage (only when DB_MODE=sqlite)
        raw_path = os.path.join(settings.LOCAL_STORAGE_DIR, "raw", raw_filename)
        thumb_path = os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails", thumb_filename)

        with open(raw_path, "wb") as f:
            f.write(image_bytes)

        with open(thumb_path, "wb") as f:
            f.write(thumb_bytes)

        # Static URLs served by FastAPI
        raw_url = f"/static/raw/{raw_filename}"
        thumb_url = f"/static/thumbnails/{thumb_filename}"
        return raw_url, thumb_url

    def delete_photo_files(self, raw_url: str, thumb_url: str) -> None:
        """Deletes photo files from Supabase or Local Storage based on mode"""
        if settings.DB_MODE == "supabase":
            try:
                # Extract filename from URL (e.g. https://.../storage/v1/object/public/photos/photo_xyz.jpg)
                raw_filename = raw_url.split("/")[-1] if raw_url else None
                thumb_filename = thumb_url.split("/")[-1] if thumb_url else None
                
                paths_to_remove = [p for p in (raw_filename, thumb_filename) if p]
                if paths_to_remove:
                    self.supabase.storage.from_("photos").remove(paths_to_remove)
            except Exception as e:
                print(f"[Storage Error] Failed to delete from Supabase: {e}")
        else:
            for url in (raw_url, thumb_url):
                if url and url.startswith("/static/"):
                    rel = url.replace("/static/", "")
                    full = os.path.join(settings.LOCAL_STORAGE_DIR, rel)
                    if os.path.exists(full):
                        try:
                            os.remove(full)
                        except Exception:
                            pass

storage_service = StorageService()
