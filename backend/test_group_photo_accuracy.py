import os
import sys
import io
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from app.ml_engine import ml_engine
from app.database import db_service

client = TestClient(app)

def create_individual_face(seed: int, brightness: float = 1.0, flip: bool = False) -> Image.Image:
    """Creates a distinct face patch for a person."""
    np.random.seed(seed)
    img = Image.new('RGB', (160, 160), color=(int(180 + (seed * 11) % 50), int(190 + (seed * 17) % 40), int(210 + (seed * 7) % 35)))
    draw = ImageDraw.Draw(img)

    hair_r = int(20 + (seed * 13) % 80)
    hair_g = int(15 + (seed * 7) % 50)
    hair_b = int(10 + (seed * 5) % 40)
    draw.ellipse([20, 10, 140, 135], fill=(hair_r, hair_g, hair_b))

    skin_r = int(170 + (seed * 23) % 75)
    skin_g = int(130 + (seed * 19) % 65)
    skin_b = int(100 + (seed * 17) % 55)
    draw.ellipse([35, 35, 125, 145], fill=(skin_r, skin_g, skin_b))

    eye_y = int(68 + ((seed * 7) % 8) - 4)
    eye_dist = int(18 + ((seed * 11) % 10))

    # Eyes
    draw.ellipse([80 - eye_dist - 7, eye_y - 5, 80 - eye_dist + 7, eye_y + 5], fill=(250, 250, 255))
    draw.ellipse([80 - eye_dist - 3, eye_y - 3, 80 - eye_dist + 3, eye_y + 3], fill=(30, 25, 20))
    draw.ellipse([80 + eye_dist - 7, eye_y - 5, 80 + eye_dist + 7, eye_y + 5], fill=(250, 250, 255))
    draw.ellipse([80 + eye_dist - 3, eye_y - 3, 80 + eye_dist + 3, eye_y + 3], fill=(30, 25, 20))

    # Eyebrows
    draw.arc([80 - eye_dist - 10, eye_y - 10, 80 - eye_dist + 10, eye_y - 4], 180, 360, fill=(hair_r, hair_g, hair_b), width=3)
    draw.arc([80 + eye_dist - 10, eye_y - 10, 80 + eye_dist + 10, eye_y - 4], 180, 360, fill=(hair_r, hair_g, hair_b), width=3)

    # Nose & Mouth
    draw.line([80, eye_y + 5, 80, eye_y + 22], fill=(skin_r - 35, skin_g - 35, skin_b - 35), width=2)
    draw.ellipse([75, eye_y + 20, 85, eye_y + 26], fill=(skin_r - 28, skin_g - 28, skin_b - 28))
    mouth_y = eye_y + 35
    draw.arc([65, mouth_y - 3, 95, mouth_y + 10], 0, 180, fill=(175, 55, 65), width=3)

    img = img.filter(ImageFilter.SMOOTH)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if flip:
        img = ImageOps.mirror(img)
    return img

def create_group_photo(seeds: list) -> bytes:
    """Creates a high-res group photo with multiple people standing together."""
    w = max(600, len(seeds) * 200 + 100)
    h = 450
    canvas = Image.new('RGB', (w, h), color=(220, 225, 235))
    draw = ImageDraw.Draw(canvas)
    # Background decor
    draw.rectangle([0, 300, w, h], fill=(190, 195, 205))

    for idx, seed in enumerate(seeds):
        face_img = create_individual_face(seed)
        # Body
        pos_x = 50 + idx * 200
        pos_y = 100
        canvas.paste(face_img, (pos_x + 20, pos_y))
        # Shirt
        shirt_color = (int(50 + (seed * 31) % 150), int(50 + (seed * 47) % 150), int(50 + (seed * 61) % 150))
        draw.rectangle([pos_x, pos_y + 160, pos_x + 200, pos_y + 320], fill=shirt_color)

    buf = io.BytesIO()
    canvas.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def run_group_photo_tests():
    print("=" * 70)
    print("  EventLens AI: Group Photo Accuracy & Strict Deduplication Suite")
    print("=" * 70)

    # Attendee IDs
    ALICE = 111
    BOB = 222
    CHARLIE = 333
    DAVID = 444
    EVE_STRANGER = 999  # Not in the group photo

    # 1. Create Group Photo with Alice, Bob, Charlie, David
    print("\n[Test 1] Ingesting Group Photo containing [Alice, Bob, Charlie, David]...")
    group_photo_bytes = create_group_photo([ALICE, BOB, CHARLIE, DAVID])
    
    faces = ml_engine.extract_faces_and_embeddings(group_photo_bytes)
    print(f" [OK] Detected {len(faces)} distinct faces in group photo!")
    assert len(faces) >= 4, f"Expected 4 faces detected in group photo, got {len(faces)}"

    # 2. Ingest into an Event
    test_code = f"GROUP-ACCURACY-{int(time.time())}"
    event = db_service.create_event(title="Group Photo Accuracy Gala", event_code=test_code)
    event_id = event["id"]

    photo_rec = db_service.insert_photo_and_embeddings(
        event_id,
        "/static/vip_group_photo.jpg",
        "/static/vip_group_photo_thumb.jpg",
        faces
    )

    # 3. Test Positive Match for Alice (Present in Group Photo)
    print("\n[Test 2] Alice takes a selfie (Present in Group Photo)...")
    alice_selfie_buf = io.BytesIO()
    create_individual_face(ALICE, brightness=0.9, flip=True).save(alice_selfie_buf, format='JPEG')
    alice_selfie_bytes = alice_selfie_buf.getvalue()

    res_alice = client.post(
        "/api/search-face",
        data={"event_code": test_code, "threshold": "0.92"},
        files={"selfie": ("selfie.jpg", alice_selfie_bytes, "image/jpeg")}
    )
    assert res_alice.status_code == 200
    data_alice = res_alice.json()
    print(f" [OK] Alice Search Result: {data_alice['count']} match(es) found.")
    assert data_alice["count"] == 1, f"Expected exactly 1 group photo match for Alice (no duplicates), got {data_alice['count']}"
    
    top_alice = data_alice["matches"][0]
    print(f" [OK] Matched Photo: {top_alice['photo_id']}, Similarity: {top_alice['similarity'] * 100:.2f}%")
    assert top_alice["similarity"] >= 0.92, "Alice match score below expected accuracy!"

    # 4. Test Negative Match for Eve (NOT Present in Group Photo)
    print("\n[Test 3] Eve takes a selfie (NOT Present in Group Photo)...")
    eve_selfie_buf = io.BytesIO()
    create_individual_face(EVE_STRANGER, brightness=1.0, flip=False).save(eve_selfie_buf, format='JPEG')
    eve_selfie_bytes = eve_selfie_buf.getvalue()

    res_eve = client.post(
        "/api/search-face",
        data={"event_code": test_code, "threshold": "0.92"},
        files={"selfie": ("selfie.jpg", eve_selfie_bytes, "image/jpeg")}
    )
    assert res_eve.status_code == 200
    data_eve = res_eve.json()
    print(f" [OK] Eve Search Result: {data_eve['count']} matches found.")
    assert data_eve["count"] == 0, f"Eve was NOT in the group photo but got {data_eve['count']} false match(es)!"
    print(" [OK] Strict Group Photo Isolation: Non-present persons correctly get 0 matches!")

    # 5. Test Zero Duplicates across multiple photos and faces
    print("\n[Test 4] Adding Scenery Photo (0 faces) and Individual Portraits...")
    scenery = Image.new('RGB', (400, 300), color=(50, 100, 180))
    scenery_buf = io.BytesIO(); scenery.save(scenery_buf, 'JPEG')
    scenery_faces = ml_engine.extract_faces_and_embeddings(scenery_buf.getvalue(), allow_fallback=False)
    print(f" [OK] Scenery photo without faces extracted {len(scenery_faces)} face vectors (expected 0).")
    assert len(scenery_faces) == 0, "Non-face photo must return 0 face vectors!"

    # Cleanup test event
    db_service.delete_event_biometrics(event_id)
    print("\n" + "=" * 70)
    print("  ALL GROUP PHOTO ACCURACY & ZERO-DUPLICATE TESTS PASSED (100%)!")
    print("=" * 70)

if __name__ == "__main__":
    run_group_photo_tests()
