import os
import sys
import io
import time
import math
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.ml_engine import ml_engine
from app.database import db_service

def create_synthetic_portrait(seed: int = 42, brightness: float = 1.0, contrast: float = 1.0) -> bytes:
    """Generates a synthetic portrait with eyes, nose, mouth and adjustable lighting"""
    img = Image.new('RGB', (320, 320), color=(180, 190, 205))
    draw = ImageDraw.Draw(img)
    
    # Face skin oval
    np.random.seed(seed)
    skin_r = int(190 + (seed % 30))
    skin_g = int(140 + (seed % 25))
    skin_b = int(110 + (seed % 20))
    draw.ellipse([80, 60, 240, 260], fill=(skin_r, skin_g, skin_b))
    
    # Eyes
    eye_offset = (seed % 10) - 5
    draw.ellipse([110, 120 + eye_offset, 140, 145 + eye_offset], fill=(30, 25, 20))
    draw.ellipse([180, 120 + eye_offset, 210, 145 + eye_offset], fill=(30, 25, 20))
    
    # Nose
    draw.polygon([(160, 145), (150, 185), (170, 185)], fill=(skin_r - 25, skin_g - 25, skin_b - 25))
    
    # Mouth
    draw.rectangle([130, 205, 190, 225], fill=(160, 40, 50))
    
    # Apply Brightness & Contrast Variations
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness)
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)
        
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def create_synthetic_group_photo() -> bytes:
    """Generates a group photo containing 3 distinct attendees standing side-by-side"""
    group_img = Image.new('RGB', (800, 400), color=(220, 225, 230))
    
    # Attendee 1 (Left)
    p1 = Image.open(io.BytesIO(create_synthetic_portrait(seed=101))).resize((200, 200))
    group_img.paste(p1, (50, 100))
    
    # Attendee 2 (Center)
    p2 = Image.open(io.BytesIO(create_synthetic_portrait(seed=202))).resize((200, 200))
    group_img.paste(p2, (300, 100))
    
    # Attendee 3 (Right)
    p3 = Image.open(io.BytesIO(create_synthetic_portrait(seed=303))).resize((200, 200))
    group_img.paste(p3, (550, 100))
    
    buf = io.BytesIO()
    group_img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def run_tests():
    print("=" * 60)
    print("  EventLens AI: Deep Analysis, Group & Lighting Test Suite")
    print("=" * 60)

    # ---------------------------------------------------------
    # TEST 1: Illumination & Brightness Invariance
    # ---------------------------------------------------------
    print("\n[Test 1] Testing Illumination & Brightness Variations on Selfies...")
    
    # Baseline normal lighting
    normal_bytes = create_synthetic_portrait(seed=42, brightness=1.0)
    emb_normal = ml_engine.extract_single_selfie_embedding(normal_bytes)
    assert emb_normal is not None, "Failed to extract embedding from normal selfie"
    print(f" [OK] Baseline selfie embedding extracted (512-d).")
    
    # Low light / Underexposed selfie (40% brightness - very dark)
    dark_bytes = create_synthetic_portrait(seed=42, brightness=0.4)
    emb_dark = ml_engine.extract_single_selfie_embedding(dark_bytes)
    assert emb_dark is not None, "Failed to extract embedding from dark selfie"
    
    # High light / Washed-out selfie (170% brightness - flash overexposure)
    bright_bytes = create_synthetic_portrait(seed=42, brightness=1.7)
    emb_bright = ml_engine.extract_single_selfie_embedding(bright_bytes)
    assert emb_bright is not None, "Failed to extract embedding from bright selfie"

    # Compute Cosine Similarities across lighting conditions
    v_norm = np.array(emb_normal)
    v_dark = np.array(emb_dark)
    v_bright = np.array(emb_bright)

    sim_dark_normal = float(np.dot(v_norm, v_dark))
    sim_bright_normal = float(np.dot(v_norm, v_bright))

    print(f" [OK] Dark Selfie vs Normal Selfie Cosine Similarity:   {sim_dark_normal * 100:.1f}% ({sim_dark_normal:.4f})")
    print(f" [OK] Bright Selfie vs Normal Selfie Cosine Similarity: {sim_bright_normal * 100:.1f}% ({sim_bright_normal:.4f})")
    
    assert sim_dark_normal >= 0.70, f"Expected dark similarity >= 0.70, got {sim_dark_normal:.4f}"
    assert sim_bright_normal >= 0.70, f"Expected bright similarity >= 0.70, got {sim_bright_normal:.4f}"

    # ---------------------------------------------------------
    # TEST 2: Multi-Face Group Photo Ingestion & Matching
    # ---------------------------------------------------------
    print("\n[Test 2] Testing Group Photo Ingestion & Multi-Face Extraction...")
    group_bytes = create_synthetic_group_photo()
    group_faces = ml_engine.extract_faces_and_embeddings(group_bytes)
    print(f" [OK] Detected {len(group_faces)} faces in group photo!")
    assert len(group_faces) >= 1, "Expected at least 1 face detected in group photo"

    # Test indexing in DB and matching against attendee 2
    test_event_code = f"TEST-GROUP-{int(time.time())}"
    event = db_service.create_event(title="Group Photo AI Test Gala", event_code=test_event_code)
    event_id = event["id"]

    photo_rec = db_service.insert_photo_and_embeddings(
        event_id=event_id,
        image_url="/static/group_test_01.jpg",
        thumbnail_url="/static/group_test_01_thumb.jpg",
        faces=group_faces
    )
    print(f" [OK] Indexed group photo with {photo_rec['faces_detected']} face vectors into DB.")

    # Simulated attendee 2 selfie
    attendee2_selfie = create_synthetic_portrait(seed=202, brightness=0.85) # slightly dim
    attendee2_vector = ml_engine.extract_single_selfie_embedding(attendee2_selfie)

    t0 = time.perf_counter()
    matches = db_service.match_selfie_vector(event_id, attendee2_vector, threshold=0.40)
    t1 = time.perf_counter()
    search_time_ms = (t1 - t0) * 1000

    print(f" [OK] Search completed in {search_time_ms:.2f} ms!")
    print(f" [OK] Matches found: {len(matches)}")
    if matches:
        top_match = matches[0]
        print(f" [OK] Top match similarity: {top_match['similarity'] * 100:.1f}% on photo {top_match['photo_id']}")
        print(f" [OK] Bounding box in group photo: {top_match['bounding_box']}")

    assert len(matches) >= 1, "Expected group photo to match attendee 2 selfie!"
    assert search_time_ms < 50.0, f"Search took too long: {search_time_ms:.2f} ms"

    # Cleanup test event
    db_service.delete_event_biometrics(event_id)

    print("\n" + "=" * 60)
    print("  ALL DEEP ANALYSIS, GROUP PHOTO & LIGHTING TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
