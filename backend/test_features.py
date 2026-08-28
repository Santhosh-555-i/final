import sys
import os
import io
import uuid
import numpy as np
from PIL import Image

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import db_service
from app.ml_engine import ml_engine
from app.storage import storage_service
from app.drive_importer import drive_importer

def create_sample_face_image_bytes(color=(200, 150, 120)):
    img = Image.new("RGB", (300, 300), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_tests():
    print("=== TEST 1: Create Event with Password & Drive Link ===")
    test_code = f"TEST{uuid.uuid4().hex[:6].upper()}"
    created = db_service.create_event(
        title="Test Protected Wedding",
        event_code=test_code,
        password="SecretPass123",
        drive_link="https://drive.google.com/drive/folders/test-sample-folder"
    )
    print(f"Created event: {created}")
    assert created["event_code"] == test_code
    assert created["is_protected"] is True
    assert created["drive_link"] == "https://drive.google.com/drive/folders/test-sample-folder"
    print("PASS: Event created successfully with password and drive link.")

    print("\n=== TEST 2: Password Verification ===")
    assert db_service.verify_event_password(test_code, "SecretPass123") is True
    print("PASS: Correct password verified.")
    assert db_service.verify_event_password(test_code, "WrongPass") is False
    print("PASS: Incorrect password rejected.")

    print("\n=== TEST 3: Get Event (Sanitized Output) ===")
    ev_data = db_service.get_event_by_code(test_code)
    assert ev_data is not None
    assert "password_hash" not in ev_data
    assert ev_data["is_protected"] is True
    print(f"PASS: Event retrieved safely: {ev_data}")

    print("\n=== TEST 4: Photo Insertion & Vector Indexing ===")
    img_bytes = create_sample_face_image_bytes((180, 130, 110))
    img_url, thumb_url = storage_service.save_photo_and_thumbnail(img_bytes, "test_attendee.jpg")
    faces = ml_engine.extract_faces_and_embeddings(img_bytes)
    print(f"Detected {len(faces)} face(s) in sample image.")
    assert len(faces) > 0
    photo_rec = db_service.insert_photo_and_embeddings(
        event_id=created["id"],
        image_url=img_url,
        thumbnail_url=thumb_url,
        faces=faces
    )
    print(f"PASS: Photo inserted: {photo_rec}")

    print("\n=== TEST 5: Vector Match Search ===")
    # Same person selfie
    selfie_bytes = create_sample_face_image_bytes((180, 130, 110))
    selfie_vec = ml_engine.extract_single_selfie_embedding(selfie_bytes)
    assert selfie_vec is not None
    matches = db_service.match_selfie_vector(created["id"], selfie_vec, threshold=0.5)
    print(f"Matches found: {len(matches)}")
    assert len(matches) > 0
    print(f"Top match similarity: {matches[0]['similarity']}")
    print("PASS: Face vector search successfully matched attendee.")

    print("\n=== TEST 6: Get All Event Photos ===")
    photos = db_service.get_event_photos(created["id"])
    assert len(photos) > 0
    print(f"PASS: Found {len(photos)} photos in event gallery.")

    print("\n=== ALL BACKEND TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
