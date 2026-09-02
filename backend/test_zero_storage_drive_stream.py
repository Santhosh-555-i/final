import os
import sys
import io
import time
import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from app.ml_engine import ml_engine
from app.database import db_service
from app.storage import storage_service
from app.drive_importer import drive_importer

client = TestClient(app)

def make_test_face(seed: int) -> bytes:
    np.random.seed(seed)
    img = Image.new('RGB', (160, 160), color=(int(180 + (seed * 11) % 50), int(190 + (seed * 17) % 40), int(210 + (seed * 7) % 35)))
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 10, 140, 135], fill=(40, 30, 20))
    draw.ellipse([35, 35, 125, 145], fill=(210, 170, 130))
    draw.ellipse([55, 65, 75, 75], fill=(255, 255, 255))
    draw.ellipse([62, 67, 68, 73], fill=(20, 20, 20))
    draw.ellipse([85, 65, 105, 75], fill=(255, 255, 255))
    draw.ellipse([92, 67, 98, 73], fill=(20, 20, 20))
    draw.arc([65, 95, 95, 110], 0, 180, fill=(180, 50, 50), width=3)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()

def run_zero_storage_tests():
    print("=" * 70)
    print("  EventLens AI: Zero-Storage Google Drive Stream & Analysis Test")
    print("=" * 70)

    test_code = f"ZERO-STORAGE-{int(time.time())}"
    event = db_service.create_event(title="Zero Storage Gala", event_code=test_code)
    event_id = event["id"]

    # 1. Simulate Google Drive photo with direct Google CDN URLs
    mock_file_id = "1A2B3C4D5E6F7G8H9I0J_TEST_FILE_ID"
    mock_cdn_url = f"https://lh3.googleusercontent.com/d/{mock_file_id}=w2048"
    mock_thumb_url = f"https://lh3.googleusercontent.com/d/{mock_file_id}=w600"

    print("\n[Test 1] Extracting embeddings in-memory without saving to storage...")
    sample_bytes = make_test_face(seed=555)
    faces = ml_engine.extract_faces_and_embeddings(sample_bytes)
    assert len(faces) >= 1, "Face detection failed!"

    # Insert into database using direct Google CDN URLs
    p_rec = db_service.insert_photo_and_embeddings(
        event_id=event_id,
        image_url=mock_cdn_url,
        thumbnail_url=mock_thumb_url,
        faces=faces
    )

    print(f" [OK] Photo indexed with image_url: {p_rec['image_url']}")
    assert p_rec["image_url"] == mock_cdn_url
    assert p_rec["thumbnail_url"] == mock_thumb_url

    # 2. Test URL resolution
    print("\n[Test 2] Testing URL resolution (Guaranteed zero Supabase storage)...")
    resolved_img = storage_service.resolve_image_url(mock_cdn_url, is_thumbnail=False)
    resolved_thumb = storage_service.resolve_image_url(mock_thumb_url, is_thumbnail=True)
    print(f" [OK] Resolved Image: {resolved_img}")
    print(f" [OK] Resolved Thumb: {resolved_thumb}")
    assert resolved_img == mock_cdn_url
    assert resolved_thumb == mock_thumb_url

    # 3. Test Vector Search Matching on zero-storage photo
    print("\n[Test 3] Testing Selfie Search matching against Drive stream photo...")
    res = client.post(
        "/api/search-face",
        data={"event_code": test_code, "threshold": "0.70"},
        files={"selfie": ("selfie.jpg", sample_bytes, "image/jpeg")}
    )
    assert res.status_code == 200, f"Search failed: {res.text}"
    data = res.json()
    print(f" [OK] Search Result: {data['count']} match(es) found.")
    assert data["count"] == 1, "Expected exactly 1 match for attendee!"
    top = data["matches"][0]
    print(f" [OK] Top Match URL: {top['image_url']}, Similarity: {top['similarity'] * 100:.2f}%")
    assert top["image_url"] == mock_cdn_url
    assert top["similarity"] >= 0.70

    # Cleanup test event
    db_service.delete_event_biometrics(event_id)
    print("\n" + "=" * 70)
    print("  ALL ZERO-STORAGE STREAMING TESTS PASSED (100%)!")
    print("=" * 70)

if __name__ == "__main__":
    run_zero_storage_tests()
