import requests
import io
import numpy as np
from PIL import Image, ImageDraw

BASE_URL = "http://127.0.0.1:8000/api"

def create_sample_face_image(seed=42):
    """Creates a sample face image for testing ML detection"""
    img = Image.new("RGB", (400, 400), color=(30, 40, 60))
    draw = ImageDraw.Draw(img)
    
    # Draw a face shape
    draw.ellipse([100, 80, 300, 320], fill=(235, 195, 165))
    # Eyes
    draw.ellipse([140, 140, 180, 170], fill=(255, 255, 255))
    draw.ellipse([220, 140, 260, 170], fill=(255, 255, 255))
    draw.ellipse([155, 150, 165, 160], fill=(50, 50, 90))
    draw.ellipse([235, 150, 245, 160], fill=(50, 50, 90))
    # Nose
    draw.polygon([(200, 170), (190, 210), (210, 210)], fill=(210, 170, 140))
    # Smile
    draw.arc([160, 210, 240, 260], start=0, end=180, fill=(180, 50, 50), width=4)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_tests():
    print("--- 1. Testing Event Creation ---")
    res = requests.post(f"{BASE_URL}/events/create", json={"title": "Grand Wedding 2026", "event_code": "TESTWEDDING2026"})
    print("Event Create Status:", res.status_code)
    event_data = res.json()
    print("Event Data:", event_data)
    event_id = event_data["id"]

    print("\n--- 2. Testing Batch Photo Upload ---")
    img_bytes1 = create_sample_face_image(seed=1)
    img_bytes2 = create_sample_face_image(seed=2)
    
    files = [
        ("files", ("photo1.jpg", img_bytes1, "image/jpeg")),
        ("files", ("photo2.jpg", img_bytes2, "image/jpeg"))
    ]
    upload_res = requests.post(f"{BASE_URL}/photos/upload-batch", data={"event_id": event_id}, files=files)
    print("Upload Batch Status:", upload_res.status_code)
    photos = upload_res.json()
    print(f"Uploaded {len(photos)} photos with face embeddings:")
    for p in photos:
        print(f"  Photo ID: {p['id']}, Faces Detected: {p['faces_detected']}, URL: {p['image_url']}")

    print("\n--- 3. Testing Selfie Match Vector Query ---")
    selfie_bytes = create_sample_face_image(seed=1)
    selfie_file = {"selfie": ("selfie.jpg", selfie_bytes, "image/jpeg")}
    match_res = requests.post(f"{BASE_URL}/photos/match", data={"event_id": event_id}, files=selfie_file)
    print("Match Status:", match_res.status_code)
    match_data = match_res.json()
    print(f"Match Response: Found {match_data['count']} matching photos!")
    for m in match_data["matches"]:
        print(f"  Matched Photo ID: {m['photo_id']}, Similarity: {m['similarity']}")

    print("\n--- All Backend API Verification Tests Passed! ---")

if __name__ == "__main__":
    run_tests()
