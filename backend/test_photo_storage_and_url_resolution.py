import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.storage import storage_service
from app.database import db_service

class TestPhotoStorageAndUrlResolution(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_clean_filename_extraction(self):
        self.assertEqual(
            storage_service.extract_clean_filename("https://xyz.supabase.co/storage/v1/object/public/photos/photo_123.jpg?token=abc"),
            "photo_123.jpg"
        )
        self.assertEqual(
            storage_service.extract_clean_filename("/static/raw/photo_7034f088-0815-418a-acc3-73fb45d33cf3.jpg"),
            "photo_7034f088-0815-418a-acc3-73fb45d33cf3.jpg"
        )
        self.assertEqual(
            storage_service.extract_clean_filename("/static/thumbnails/thumb_abc.jpg"),
            "thumb_abc.jpg"
        )

    def test_url_resolution(self):
        # Full URL should be preserved
        full_url = "https://example.com/storage/photo.jpg"
        self.assertEqual(storage_service.resolve_image_url(full_url), full_url)

        # Empty or None should return placeholder
        self.assertEqual(storage_service.resolve_image_url(""), "/placeholder.jpg")

    def test_health_endpoint_reports_status(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("supabase_configured", data)
        self.assertIn("db_mode", data)

    def test_fallback_static_or_file_stream(self):
        # Create a temporary dummy image in local storage to verify streaming
        import os
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "raw"), exist_ok=True)
        test_file = os.path.join(settings.LOCAL_STORAGE_DIR, "raw", "photo_test_diag.jpg")
        with open(test_file, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50)

        try:
            # 1. Test /static/raw/photo_test_diag.jpg
            resp = self.client.get("/static/raw/photo_test_diag.jpg")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("content-type"), "image/jpeg")

            # 2. Test /api/photos/file/photo_test_diag.jpg
            resp2 = self.client.get("/api/photos/file/photo_test_diag.jpg")
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.headers.get("content-type"), "image/jpeg")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

if __name__ == "__main__":
    unittest.main()
