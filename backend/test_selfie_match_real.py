import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from app.database import db_service
from app.config import settings

client = TestClient(app)

def test_real_match():
    # 1. Fetch user event
    event = db_service.get_event_by_code("SATOSH2005TH@GMAIL.COM")
    if not event:
        event = db_service.get_event_by_code("SANTOSH2005TH@GMAIL.COM")
    if not event:
        event = db_service.get_all_events()[0]

    print(f"Testing Face Match on Event: {event['title']} (Code: {event['event_code']}, ID: {event['id']})")

    # 2. Get photos in this event
    photos = db_service.get_event_photos(event["id"])
    print(f"Total photos in event: {len(photos)}")
    assert len(photos) > 0, "No photos found in event!"

    test_photo = photos[0]
    rel_path = test_photo["image_url"].replace("/static/", "")
    full_path = os.path.join(settings.LOCAL_STORAGE_DIR, rel_path)

    print(f"Using photo {test_photo['id']} ({full_path}) as simulated selfie input...")
    with open(full_path, "rb") as f:
        img_bytes = f.read()

    # 3. Call /api/photos/match with event code
    res_code = client.post(
        "/api/photos/match",
        data={"event_id": event["event_code"]},
        files={"selfie": ("selfie.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Match Response with Event Code ({event['event_code']}): Status={res_code.status_code}")
    assert res_code.status_code == 200
    data_code = res_code.json()
    print(f"Found {data_code['count']} matched photos!")
    print(f"Top match similarity: {data_code['matches'][0]['similarity'] if data_code['matches'] else 'None'}")
    assert data_code["count"] >= 1, "Expected at least 1 match!"

    # 4. Call /api/photos/match with event UUID
    res_id = client.post(
        "/api/photos/match",
        data={"event_id": event["id"]},
        files={"selfie": ("selfie.jpg", img_bytes, "image/jpeg")}
    )
    print(f"\nMatch Response with Event UUID ({event['id']}): Status={res_id.status_code}")
    assert res_id.status_code == 200
    data_id = res_id.json()
    print(f"Found {data_id['count']} matched photos!")
    assert data_id["count"] >= 1, "Expected at least 1 match!"

    print("\n>>> ALL REAL-WORLD SELFIE FACE MATCHING TESTS PASSED! <<<")

if __name__ == "__main__":
    test_real_match()
