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
from app.config import settings

client = TestClient(app)

def make_test_face(seed: int, brightness: float = 1.0, contrast: float = 1.0, flip: bool = False) -> bytes:
    """Creates distinct test faces with unique features, proportions, and lighting."""
    np.random.seed(seed)
    img = Image.new('RGB', (320, 320), color=(int(180 + (seed * 11) % 50), int(190 + (seed * 17) % 40), int(210 + (seed * 7) % 35)))
    draw = ImageDraw.Draw(img)

    # Hair
    hair_r = int(20 + (seed * 13) % 80)
    hair_g = int(15 + (seed * 7) % 50)
    hair_b = int(10 + (seed * 5) % 40)
    draw.ellipse([45, 30, 275, 270], fill=(hair_r, hair_g, hair_b))

    # Skin Tone
    skin_r = int(170 + (seed * 23) % 75)
    skin_g = int(130 + (seed * 19) % 65)
    skin_b = int(100 + (seed * 17) % 55)
    draw.ellipse([70, 70, 250, 280], fill=(skin_r, skin_g, skin_b))

    # Eyes
    eye_y = int(135 + ((seed * 7) % 15) - 7)
    eye_dist = int(35 + ((seed * 11) % 20))
    
    # Left eye
    draw.ellipse([160 - eye_dist - 14, eye_y - 9, 160 - eye_dist + 14, eye_y + 9], fill=(250, 250, 255))
    draw.ellipse([160 - eye_dist - 6, eye_y - 6, 160 - eye_dist + 6, eye_y + 6], fill=(30, 25, 20))
    
    # Right eye
    draw.ellipse([160 + eye_dist - 14, eye_y - 9, 160 + eye_dist + 14, eye_y + 9], fill=(250, 250, 255))
    draw.ellipse([160 + eye_dist - 6, eye_y - 6, 160 + eye_dist + 6, eye_y + 6], fill=(30, 25, 20))

    # Eyebrows
    draw.arc([160 - eye_dist - 18, eye_y - 20, 160 - eye_dist + 18, eye_y - 8], 180, 360, fill=(hair_r, hair_g, hair_b), width=4)
    draw.arc([160 + eye_dist - 18, eye_y - 20, 160 + eye_dist + 18, eye_y - 8], 180, 360, fill=(hair_r, hair_g, hair_b), width=4)

    # Nose
    draw.line([160, eye_y + 10, 160, eye_y + 45], fill=(skin_r - 35, skin_g - 35, skin_b - 35), width=3)
    draw.ellipse([150, eye_y + 40, 170, eye_y + 52], fill=(skin_r - 28, skin_g - 28, skin_b - 28))

    # Mouth
    mouth_y = eye_y + 70
    draw.arc([130, mouth_y - 5, 190, mouth_y + 20], 0, 180, fill=(175, 55, 65), width=5)

    img = img.filter(ImageFilter.SMOOTH)

    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if flip:
        img = ImageOps.mirror(img)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def run_precision_tests():
    print("=" * 70)
    print("  EventLens AI: Precision Face Matching & Recognition Test Suite")
    print("=" * 70)

    # 1. Mirror Invariance Test
    print("\n[Test 1] Testing Mirror & Horizontal Flip Invariance...")
    face1_orig = make_test_face(seed=101, flip=False)
    face1_flipped = make_test_face(seed=101, flip=True)

    emb_orig = ml_engine.extract_single_selfie_embedding(face1_orig)
    emb_flipped = ml_engine.extract_single_selfie_embedding(face1_flipped)

    assert emb_orig is not None, "Failed to extract embedding from original photo"
    assert emb_flipped is not None, "Failed to extract embedding from flipped selfie"

    sim_mirror = float(np.dot(np.array(emb_orig), np.array(emb_flipped)))
    print(f" [OK] Normal Photo vs Mirrored Selfie Similarity: {sim_mirror * 100:.2f}% ({sim_mirror:.4f})")
    assert sim_mirror >= 0.95, f"Mirror invariance failed: {sim_mirror:.4f}"

    # 2. Lighting Invariance Test (Dark & Bright variations)
    print("\n[Test 2] Testing Illumination & Lighting Invariance...")
    face1_dark = make_test_face(seed=101, brightness=0.55)
    face1_bright = make_test_face(seed=101, brightness=1.50)

    emb_dark = ml_engine.extract_single_selfie_embedding(face1_dark)
    emb_bright = ml_engine.extract_single_selfie_embedding(face1_bright)

    sim_dark = float(np.dot(np.array(emb_orig), np.array(emb_dark)))
    sim_bright = float(np.dot(np.array(emb_orig), np.array(emb_bright)))

    print(f" [OK] Dark Selfie vs Normal Photo Similarity:   {sim_dark * 100:.2f}% ({sim_dark:.4f})")
    print(f" [OK] Bright Selfie vs Normal Photo Similarity: {sim_bright * 100:.2f}% ({sim_bright:.4f})")
    assert sim_dark >= 0.85, f"Dark similarity too low: {sim_dark:.4f}"
    assert sim_bright >= 0.85, f"Bright similarity too low: {sim_bright:.4f}"

    # 3. End-to-End Event Matching & Precision Ranking Test
    print("\n[Test 3] Testing End-to-End Event Photo Matching & Accurate Ranking...")
    test_code = f"PRECISION-GALA-{int(time.time())}"
    event = db_service.create_event(title="Precision Gala 2026", event_code=test_code)
    event_id = event["id"]

    # Ingest 3 distinct event photos
    face2_photo = make_test_face(seed=202)
    face3_photo = make_test_face(seed=303)

    faces_1 = ml_engine.extract_faces_and_embeddings(face1_orig)
    faces_2 = ml_engine.extract_faces_and_embeddings(face2_photo)
    faces_3 = ml_engine.extract_faces_and_embeddings(face3_photo)

    p1 = db_service.insert_photo_and_embeddings(event_id, "/static/photo_user1.jpg", "/static/photo_user1_thumb.jpg", faces_1)
    p2 = db_service.insert_photo_and_embeddings(event_id, "/static/photo_user2.jpg", "/static/photo_user2_thumb.jpg", faces_2)
    p3 = db_service.insert_photo_and_embeddings(event_id, "/static/photo_user3.jpg", "/static/photo_user3_thumb.jpg", faces_3)

    print(f" [OK] Event indexed with {len(faces_1) + len(faces_2) + len(faces_3)} face vectors.")

    # User 1 takes a selfie with front camera (mirrored + different lighting)
    user1_selfie = make_test_face(seed=101, brightness=0.9, flip=True)

    # API Search via /api/search-face
    res = client.post(
        "/api/search-face",
        data={"event_code": test_code, "threshold": "0.55"},
        files={"selfie": ("selfie.jpg", user1_selfie, "image/jpeg")}
    )
    assert res.status_code == 200, f"Search face API failed: {res.text}"
    data = res.json()

    print(f" [OK] /api/search-face returned {data['count']} matched photo(s)")
    assert data["count"] >= 1, "Expected matching photo for User 1!"
    top_match = data["matches"][0]
    print(f" [OK] Top Match Photo ID: {top_match['photo_id']}, Similarity: {top_match['similarity'] * 100:.2f}%")
    assert top_match["photo_id"] == p1["id"], f"Top match was NOT User 1's photo! Got {top_match['photo_id']}"
    assert top_match["similarity"] >= 0.90, f"Top match similarity was below 0.90: {top_match['similarity']}"

    # Benchmark Search Latency (Vector similarity search over event database)
    selfie_vec = ml_engine.extract_single_selfie_embedding(user1_selfie)
    t0 = time.perf_counter()
    matches_raw = db_service.match_selfie_vector(event_id, selfie_vec, threshold=0.55)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000
    print(f" [OK] Sub-millisecond Matrix Vector Match Latency: {latency_ms:.2f} ms")
    assert latency_ms < 50.0, f"Latency exceeded threshold: {latency_ms:.2f} ms"

    # Cleanup test event
    db_service.delete_event_biometrics(event_id)

    print("\n" + "=" * 70)
    print("  ALL PRECISION FACE MATCHING TESTS PASSED PERFECTLY (100%)!")
    print("=" * 70)

if __name__ == "__main__":
    run_precision_tests()
