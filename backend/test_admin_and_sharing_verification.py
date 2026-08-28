import os, sys
from fastapi.testclient import TestClient
sys.path.insert(0, 'backend')
from app.main import app
from app.database import db_service
from app.config import settings

client = TestClient(app)

def test_admin_auth():
    print("=== Testing Admin Authentication with 'element2018' ===")
    
    # 1. Correct login with designated admin email & element2018
    res = client.post("/api/auth/login", json={
        "email": "santosh2005th@gmail.com",
        "password": "element2018"
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    assert "token" in data
    print(" [OK] Admin Login with santosh2005th@gmail.com & element2018 passed!")

    # 2. Wrong password rejected
    res_wrong = client.post("/api/auth/login", json={
        "email": "santosh2005th@gmail.com",
        "password": "wrongpassword"
    })
    assert res_wrong.status_code == 401
    print(" [OK] Wrong admin password properly rejected with 401!")

def test_event_visibility_and_access():
    print("\n=== Testing Global Event Visibility & Guest Access ===")
    
    # 1. Fetch all events
    res = client.get("/api/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1
    print(f" [OK] /api/events successfully returned {len(events)} real events for all users:")
    for ev in events:
        print(f"      * Title: '{ev['title']}' | Code: '{ev['event_code']}' | Protected: {ev.get('is_protected')} | Photos: {ev.get('photo_count')}")

    # 2. Test accessing first event by Title and Code
    test_ev = events[0]
    res_by_code = client.get(f"/api/events/{test_ev['event_code']}")
    assert res_by_code.status_code == 200
    assert res_by_code.json()["id"] == test_ev["id"]
    print(f" [OK] Guest access by Event Code '{test_ev['event_code']}' passed!")

    res_by_title = client.get(f"/api/events/{test_ev['title']}")
    assert res_by_title.status_code == 200
    assert res_by_title.json()["id"] == test_ev["id"]
    print(f" [OK] Guest access by Event Name '{test_ev['title']}' passed!")

if __name__ == "__main__":
    test_admin_auth()
    test_event_visibility_and_access()
    print("\n [SUCCESS] ALL COMPREHENSIVE VERIFICATION TESTS PASSED!")
