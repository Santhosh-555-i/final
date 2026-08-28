import sys
import os
import io
import base64
import zipfile
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import db_service

client = TestClient(app)

def create_sample_face_image():
    # 200x200 sample image simulating an attendee face
    img = Image.new("RGB", (200, 200), color=(180, 130, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_new_routes():
    print(">>> 1. Creating Test Event...")
    evt_payload = {
        "title": "Summer Gala 2026",
        "event_code": "SUMMER2026",
        "password": "gala123password",
        "drive_link": "https://drive.google.com/drive/folders/1abc987654321xyz"
    }
    res = client.post("/api/events/create", json=evt_payload)
    if res.status_code == 400:
        event = db_service.get_event_by_code("SUMMER2026")
    else:
        assert res.status_code == 201
        event = res.json()
    
    event_id = event["id"]
    print(f"Event initialized: ID={event_id}, Code={event['event_code']}")

    print("\n>>> 2. Testing POST /api/admin/sync-drive...")
    sync_res = client.post("/api/admin/sync-drive", json={
        "drive_link": "https://drive.google.com/drive/folders/1abc987654321xyz",
        "event_id": event_id
    })
    print(f"Sync Drive Response: Status={sync_res.status_code}, Body={sync_res.json()}")
    assert sync_res.status_code == 202
    sync_data = sync_res.json()
    assert sync_data["success"] is True
    task_id = sync_data["task_id"]
    assert task_id is not None

    print("\n>>> 3. Testing GET /api/admin/sync-status/{task_id}...")
    status_res = client.get(f"/api/admin/sync-status/{task_id}")
    print(f"Sync Status: {status_res.json()}")
    assert status_res.status_code == 200
    assert status_res.json()["task_id"] == task_id

    print("\n>>> 4. Testing Upload Batch Photos to seed data...")
    img_data = create_sample_face_image()
    files = [
        ("files", ("attendee_photo1.jpg", img_data, "image/jpeg")),
        ("files", ("attendee_photo2.jpg", img_data, "image/jpeg"))
    ]
    upload_res = client.post("/api/photos/upload-batch", data={"event_id": event_id}, files=files)
    assert upload_res.status_code == 201
    uploaded_photos = upload_res.json()
    print(f"Uploaded {len(uploaded_photos)} photos.")
    assert len(uploaded_photos) == 2

    print("\n>>> 5. Testing GET /api/admin/stats/{event_id}...")
    stats_res = client.get(f"/api/admin/stats/{event_id}")
    print(f"Admin Stats: {stats_res.json()}")
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    assert stats_data["total_photos"] >= 2
    assert stats_data["total_faces_detected"] >= 2

    print("\n>>> 6. Testing POST /api/admin/index-faces...")
    index_res = client.post("/api/admin/index-faces", json={"event_id": event_id})
    print(f"Index Faces Response: {index_res.json()}")
    assert index_res.status_code == 200
    assert index_res.json()["success"] is True

    print("\n>>> 7. Testing POST /api/search-face with multipart form...")
    search_multipart_res = client.post(
        "/api/search-face",
        data={"event_id": event_id, "threshold": "0.3"},
        files={"selfie": ("selfie.jpg", img_data, "image/jpeg")}
    )
    print(f"Search Face (Multipart): Status={search_multipart_res.status_code}")
    assert search_multipart_res.status_code == 200
    match_result = search_multipart_res.json()
    print(f"Found {match_result['count']} matched photos via multipart search.")
    assert match_result["count"] >= 1

    print("\n>>> 8. Testing POST /api/search-face with JSON Base64...")
    b64_img = base64.b64encode(img_data).decode("utf-8")
    search_json_res = client.post(
        "/api/search-face",
        json={
            "event_id": event_id,
            "selfie_base64": f"data:image/jpeg;base64,{b64_img}",
            "threshold": 0.3
        }
    )
    print(f"Search Face (Base64 JSON): Status={search_json_res.status_code}")
    assert search_json_res.status_code == 200
    match_json_result = search_json_res.json()
    print(f"Found {match_json_result['count']} matched photos via Base64 JSON search.")
    assert match_json_result["count"] >= 1

    print("\n>>> 9. Testing High-Res ZIP Download...")
    photo_urls = [p["image_url"] for p in uploaded_photos]
    zip_res = client.post("/api/photos/download-zip", json=photo_urls)
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
        print(f"ZIP Files contains: {zf.namelist()}")
        assert len(zf.namelist()) >= 1

    print("\n>>> ALL V2 API ROUTE TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_new_routes()
