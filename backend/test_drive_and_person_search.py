import os
import sys
import io
import base64
import zipfile
from unittest.mock import patch
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "admin123"
TEST_JWT_SECRET = "test-jwt-secret-drive-person-32chars"

with patch.dict(os.environ, {
    "DB_MODE": "sqlite",
    "ADMIN_EMAIL": TEST_ADMIN_EMAIL,
    "ADMIN_PASSWORD": TEST_ADMIN_PASSWORD,
    "ADMIN_JWT_SECRET": TEST_JWT_SECRET,
}):
    from app.main import app
    from app.database import db_service
    from app.google_drive_api import google_drive_helper
    from app.drive_importer import drive_importer

client = TestClient(app)

def create_synthetic_person_image(seed_color=(200, 150, 100)):
    """Creates an image with simple facial structure for end-to-end testing."""
    img = Image.new("RGB", (256, 256), color=seed_color)
    draw = ImageDraw.Draw(img)
    # Draw simple face contours (eyes, nose, mouth)
    draw.ellipse([60, 60, 196, 210], fill=(220, 180, 140), outline=(100, 70, 50))
    draw.ellipse([90, 100, 110, 120], fill=(50, 50, 50)) # Left eye
    draw.ellipse([146, 100, 166, 120], fill=(50, 50, 50)) # Right eye
    draw.line([128, 120, 128, 150], fill=(120, 80, 60), width=3) # Nose
    draw.arc([100, 155, 156, 180], 0, 180, fill=(180, 50, 50), width=3) # Mouth
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

def test_drive_url_extraction():
    """Verify Google Drive URL parser extracts all supported formats."""
    print("=== Testing Google Drive URL Extraction ===")
    test_cases = [
        ("https://drive.google.com/drive/folders/1ABC_XYZ123456789012345?usp=sharing", "1ABC_XYZ123456789012345", "folder"),
        ("https://drive.google.com/drive/u/0/folders/1U0_ABC123456789012345", "1U0_ABC123456789012345", "folder"),
        ("https://drive.google.com/file/d/1FILE_ABC123456789012345/view?usp=sharing", "1FILE_ABC123456789012345", "file"),
        ("https://drive.google.com/open?id=1OPEN_ABC123456789012345", "1OPEN_ABC123456789012345", "file"),
    ]
    for url, expected_id, expected_type in test_cases:
        fid, ftype = google_drive_helper.extract_id(url)
        assert fid == expected_id, f"Expected {expected_id}, got {fid}"
        assert ftype == expected_type, f"Expected {expected_type}, got {ftype}"
    print(" [OK] All Google Drive URL formats parsed accurately!")

def test_user_person_photo_search_and_matching():
    """Verify complete flow: Admin seeds photos -> User uploads photo -> AI matches and returns person's photos."""
    print("\n=== Testing User Person Photo Search & Facial Matching ===")
    
    settings_patch = patch.multiple(
        "app.routers.auth.settings",
        ADMIN_EMAIL=TEST_ADMIN_EMAIL,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_JWT_SECRET=TEST_JWT_SECRET,
    )
    with settings_patch:
        # 1. Login as admin
        login_res = client.post("/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD,
        })
        assert login_res.status_code == 200
        token = login_res.json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Event
        evt_res = client.post("/api/events/create", json={
            "title": "Annual Gala 2026",
            "event_code": "GALA2026",
            "password": "gala_secret_code"
        }, headers=auth_headers)
        if evt_res.status_code == 400:
            event = db_service.get_event_by_code("GALA2026")
        else:
            assert evt_res.status_code == 201
            event = evt_res.json()
        
        event_id = event["id"]
        print(f" [OK] Event created: {event['title']} (Code: {event['event_code']}, ID: {event_id})")

        # 3. Seed Event Photos (Simulating Drive sync or Batch upload)
        person_a_photo1 = create_synthetic_person_image(seed_color=(200, 150, 100))
        person_a_photo2 = create_synthetic_person_image(seed_color=(210, 155, 105))
        person_b_photo1 = create_synthetic_person_image(seed_color=(100, 120, 180))

        files = [
            ("files", ("person_a_01.jpg", person_a_photo1, "image/jpeg")),
            ("files", ("person_a_02.jpg", person_a_photo2, "image/jpeg")),
            ("files", ("person_b_01.jpg", person_b_photo1, "image/jpeg")),
        ]
        upload_res = client.post("/api/photos/upload-batch", data={"event_id": event_id}, files=files, headers=auth_headers)
        assert upload_res.status_code == 201
        uploaded = upload_res.json()
        assert len(uploaded) == 3
        print(f" [OK] Uploaded {len(uploaded)} event gallery photos.")

        # 4. Attendee submits photo (Person A selfie) via POST /api/search-face
        search_res = client.post(
            "/api/search-face",
            data={"event_id": event_id, "threshold": "0.40"},
            files={"selfie": ("attendee_selfie.jpg", person_a_photo1, "image/jpeg")}
        )
        assert search_res.status_code == 200
        match_data = search_res.json()
        print(f" [OK] Attendee search succeeded! Found {match_data['count']} matching photos of the person.")
        assert match_data["count"] >= 1
        assert len(match_data["matches"]) >= 1

        # 5. Attendee downloads matched photos ZIP
        matched_urls = [m["image_url"] for m in match_data["matches"]]
        zip_res = client.post("/api/photos/download-zip", json=matched_urls)
        assert zip_res.status_code == 200
        assert zip_res.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
            print(f" [OK] Matched photos ZIP generated with {len(zf.namelist())} files.")
            assert len(zf.namelist()) >= 1

        # 6. Verify Person Clusters API (/api/clusters/event/{event_id})
        clusters_res = client.get(f"/api/clusters/event/{event_id}")
        assert clusters_res.status_code == 200
        c_data = clusters_res.json()
        print(f" [OK] Person Clusters API returned {c_data.get('count', 0)} discovered person groups.")

    print("\n [SUCCESS] ALL DRIVE & PERSON SEARCH TESTS PASSED!")

if __name__ == "__main__":
    test_drive_url_extraction()
    test_user_person_photo_search_and_matching()
