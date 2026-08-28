import sys
import os
import io
import zipfile
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

client = TestClient(app)

def create_dummy_image():
    img = Image.new("RGB", (200, 200), color=(170, 120, 95))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_full_flow():
    print(">>> 1. Testing Create Password-Protected Event with Drive Link...")
    evt_payload = {
        "title": "Maya & Rahul Anniversary",
        "event_code": "ANNIVERSARY2026",
        "password": "passcode123",
        "drive_link": "https://drive.google.com/drive/folders/sample123"
    }
    # Clean up if already exists
    res = client.post("/api/events/create", json=evt_payload)
    if res.status_code == 400 and "already exists" in res.text:
        print("Event already exists, testing get existing event...")
        res = client.get("/api/events/ANNIVERSARY2026")
        assert res.status_code == 200
        event_data = res.json()
    else:
        assert res.status_code == 201
        event_data = res.json()
    
    print(f"Event Data: {event_data}")
    assert event_data["event_code"] == "ANNIVERSARY2026"
    assert event_data["is_protected"] is True

    print("\n>>> 2. Testing Password Verification Endpoint...")
    # Wrong password
    res = client.post("/api/events/verify-password", json={
        "event_code": "ANNIVERSARY2026",
        "password": "wrong_password"
    })
    assert res.status_code == 401
    print("PASS: Wrong password correctly rejected with 401.")

    # Correct password
    res = client.post("/api/events/verify-password", json={
        "event_code": "ANNIVERSARY2026",
        "password": "passcode123"
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
    print("PASS: Correct password unlocked event.")

    print("\n>>> 3. Testing Upload Batch Photos...")
    img_data = create_dummy_image()
    files = [("files", ("photo1.jpg", img_data, "image/jpeg")), ("files", ("photo2.jpg", img_data, "image/jpeg"))]
    res = client.post("/api/photos/upload-batch", data={"event_id": event_data["id"]}, files=files)
    assert res.status_code == 201
    uploaded_photos = res.json()
    print(f"Uploaded {len(uploaded_photos)} photos.")
    assert len(uploaded_photos) == 2

    print("\n>>> 4. Testing Get Event Photos...")
    res = client.get(f"/api/events/ANNIVERSARY2026/photos")
    assert res.status_code == 200
    photos_list = res.json()
    assert len(photos_list) >= 2
    print(f"PASS: Retrieved {len(photos_list)} event gallery photos.")

    print("\n>>> 5. Testing Selfie AI Match...")
    selfie_file = ("selfie", ("my_selfie.jpg", img_data, "image/jpeg"))
    res = client.post("/api/photos/match", data={"event_id": event_data["id"]}, files=[selfie_file])
    assert res.status_code == 200
    match_data = res.json()
    print(f"Match results: {match_data['count']} matching photos found.")
    assert match_data["count"] >= 1

    print("\n>>> 6. Testing ZIP Download Generation...")
    photo_urls = [p["image_url"] for p in uploaded_photos]
    res = client.post("/api/photos/download-zip", json=photo_urls)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    
    # Verify zip content
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        print(f"ZIP files contained: {namelist}")
        assert len(namelist) >= 1
    print("PASS: ZIP archive successfully created and validated.")

    print("\n>>> ALL FULL INTEGRATION TESTS PASSED! <<<")

if __name__ == "__main__":
    test_full_flow()
