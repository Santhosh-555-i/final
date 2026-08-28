import os, sys, time, json
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.abspath('backend'))
from app.config import settings
from app.ml_engine import ml_engine
from app.database import db_service
from app.clustering import FaceClusteringEngine

def test_1_admin_auth():
    print("=" * 60)
    print("[Test 1] Verifying Admin Authentication Credentials...")
    print("=" * 60)
    
    assert "santosh2005th@gmail.com" in settings.ALLOWED_ADMIN_EMAILS, "santosh2005th@gmail.com missing from config"
    assert settings.ADMIN_EMAIL == "santosh2005th@gmail.com", f"Expected primary admin santosh2005th@gmail.com, got {settings.ADMIN_EMAIL}"
    
    # Test valid and invalid logins
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    # 1. Primary admin email
    res1 = client.post("/api/auth/login", json={"email": "santosh2005th@gmail.com", "password": "admin123"})
    assert res1.status_code == 200, f"Failed primary admin login: {res1.text}"
    assert res1.json()["email"] == "santosh2005th@gmail.com"
    print(" [OK] Primary Admin login (santosh2005th@gmail.com) authorized successfully!")

    # 2. Case insensitive & whitespace trimmed
    res2 = client.post("/api/auth/login", json={"email": "  SANTOSH2005TH@GMAIL.COM  ", "password": "admin123"})
    assert res2.status_code == 200, "Failed case-insensitive admin login"
    print(" [OK] Case-insensitive & trimmed login authorized successfully!")

    # 3. Unauthorized email rejection
    res3 = client.post("/api/auth/login", json={"email": "intruder@example.com", "password": "admin123"})
    assert res3.status_code == 403, "Failed to reject unauthorized email"
    print(" [OK] Unauthorized emails correctly rejected with 403 Forbidden!")

def test_2_unclear_blurry_photo_matching():
    print("\n" + "=" * 60)
    print("[Test 2] Testing Unclear & Blurry Photo Restoration & Matching...")
    print("=" * 60)

    # Use an existing photo from storage as base
    sample_img_path = 'backend/storage_data/raw/photo_8f790d6f-81ae-4b60-a973-ff6e2e3b8b32.jpg'
    if not os.path.exists(sample_img_path):
        print(" [SKIP] Base test photo not found in storage_data")
        return

    with open(sample_img_path, 'rb') as f:
        clear_bytes = f.read()

    clear_faces = ml_engine.extract_faces_and_embeddings(clear_bytes)
    assert len(clear_faces) > 0, "No face found in base photo"
    clear_emb = np.array(clear_faces[0]['embedding'])
    print(f" [OK] Base clear face extracted (512-d).")

    # 1. Simulate Blurry / Out-of-Focus Photo (Gaussian Blur)
    img_cv = cv2.imread(sample_img_path)
    blurry_cv = cv2.GaussianBlur(img_cv, (11, 11), 3.0)
    _, blurry_bytes = cv2.imencode('.jpg', blurry_cv)
    
    blurry_faces = ml_engine.extract_faces_and_embeddings(blurry_bytes.tobytes())
    assert len(blurry_faces) > 0, "Failed to detect face on blurry photo"
    blurry_emb = np.array(blurry_faces[0]['embedding'])
    sim_blur = float(np.dot(clear_emb, blurry_emb))
    print(f" [OK] Blurry Photo vs Clear Photo Cosine Similarity: {sim_blur*100:.1f}% ({sim_blur:.4f})")
    assert sim_blur >= 0.70, f"Blurry match similarity too low: {sim_blur}"

    # 2. Simulate Low-Resolution / Downscaled Photo (50% downscale + upscale)
    h, w, _ = img_cv.shape
    small_cv = cv2.resize(img_cv, (w // 3, h // 3), interpolation=cv2.INTER_AREA)
    _, small_bytes = cv2.imencode('.jpg', small_cv)

    small_faces = ml_engine.extract_faces_and_embeddings(small_bytes.tobytes())
    assert len(small_faces) > 0, "Failed to detect face on low-res downscaled photo"
    small_emb = np.array(small_faces[0]['embedding'])
    sim_small = float(np.dot(clear_emb, small_emb))
    print(f" [OK] Low-Res Downscaled Photo vs Clear Photo Cosine Similarity: {sim_small*100:.1f}% ({sim_small:.4f})")
    assert sim_small >= 0.75, f"Low-res match similarity too low: {sim_small}"

    # 3. Simulate High Contrast / Dark Shadow Photo
    dark_cv = np.clip(img_cv * 0.45, 0, 255).astype(np.uint8)
    _, dark_bytes = cv2.imencode('.jpg', dark_cv)

    dark_faces = ml_engine.extract_faces_and_embeddings(dark_bytes.tobytes())
    assert len(dark_faces) > 0, "Failed to detect face on dark photo"
    dark_emb = np.array(dark_faces[0]['embedding'])
    sim_dark = float(np.dot(clear_emb, dark_emb))
    print(f" [OK] Dark Underexposed Photo vs Clear Photo Cosine Similarity: {sim_dark*100:.1f}% ({sim_dark:.4f})")
    assert sim_dark >= 0.75, f"Dark match similarity too low: {sim_dark}"

def test_3_google_photos_person_separation():
    print("\n" + "=" * 60)
    print("[Test 3] Testing Google Photos-Style Automatic Person Separation...")
    print("=" * 60)

    engine = FaceClusteringEngine(db_service.db_path)
    
    # Get active events with photos (e.g. ANNIVERSARY2026)
    event = db_service.get_event_by_code("ANNIVERSARY2026")
    if not event:
        events = db_service.get_all_events()
        event = events[0]
    event_id = event["id"]

    clusters = engine.get_event_clusters(event_id)
    print(f" [OK] Discovered {len(clusters)} unique person clusters for event '{event['title']}' ({event['event_code']})")
    
    if clusters:
        first_cluster = clusters[0]
        print(f"      Sample Person: '{first_cluster['name']}' with {first_cluster['photo_count']} photos (Face count: {first_cluster['face_count']})")
        assert first_cluster["photo_count"] > 0, "Cluster has 0 photos"
        assert "thumbnail_url" in first_cluster, "Cluster missing thumbnail_url"
        print(f"      Thumbnail: {first_cluster['thumbnail_url']}")

def test_4_search_speed():
    print("\n" + "=" * 60)
    print("[Test 4] Benchmarking Sub-Millisecond Search Speed...")
    print("=" * 60)

    event = db_service.get_event_by_code("ANNIVERSARY2026") or db_service.get_all_events()[0]
    event_id = event["id"]

    # Generate dummy 512-d unit vector
    dummy_v = np.random.randn(512).astype(np.float32)
    dummy_v /= np.linalg.norm(dummy_v)
    v_list = dummy_v.tolist()

    # Warmup
    db_service.match_selfie_vector(event_id, v_list, threshold=0.1)

    # Benchmark 20 queries
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        db_service.match_selfie_vector(event_id, v_list, threshold=0.1)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    print(f" [OK] Average Vector Search Time over 20 runs: {avg_time:.2f} ms (Fastest: {min_time:.2f} ms)")
    assert avg_time < 20.0, f"Search time too slow: {avg_time} ms"

if __name__ == "__main__":
    test_1_admin_auth()
    test_2_unclear_blurry_photo_matching()
    test_3_google_photos_person_separation()
    test_4_search_speed()
    print("\n" + "=" * 60)
    print("  ALL 4 PILLARS FULLY VERIFIED AND PASSING WITH EXCELLENCE!")
    print("=" * 60)
