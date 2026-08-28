import os, sys
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0, 'backend')

TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "admin123"
TEST_JWT_SECRET = "test-jwt-secret-admin-sharing-32chars"

with patch.dict(os.environ, {
    "DB_MODE": "sqlite",
    "ADMIN_EMAIL": TEST_ADMIN_EMAIL,
    "ADMIN_PASSWORD": TEST_ADMIN_PASSWORD,
    "ADMIN_JWT_SECRET": TEST_JWT_SECRET,
}):
    from app.main import app
    from app.database import db_service
    from app.config import settings

client = TestClient(app)

def get_token():
    with patch.multiple(
        "app.routers.auth.settings",
        ADMIN_EMAIL=TEST_ADMIN_EMAIL,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_JWT_SECRET=TEST_JWT_SECRET,
    ):
        res = client.post("/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD,
        })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["token"]

def test_admin_auth():
    print("=== Testing Admin Authentication ===")

    # 1. Correct login
    with patch.multiple(
        "app.routers.auth.settings",
        ADMIN_EMAIL=TEST_ADMIN_EMAIL,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_JWT_SECRET=TEST_JWT_SECRET,
    ):
        res = client.post("/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD,
        })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    assert "token" in data
    print(f" [OK] Admin Login with {TEST_ADMIN_EMAIL} passed!")

    # 2. Wrong password rejected
    with patch.multiple(
        "app.routers.auth.settings",
        ADMIN_EMAIL=TEST_ADMIN_EMAIL,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_JWT_SECRET=TEST_JWT_SECRET,
    ):
        res_wrong = client.post("/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "wrongpassword",
        })
    assert res_wrong.status_code == 401
    print(" [OK] Wrong admin password properly rejected with 401!")

def test_event_visibility_and_access():
    print("\n=== Testing Global Event Visibility & Guest Access ===")
    token = get_token()
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create a test event first to ensure at least one exists
    with patch.multiple(
        "app.routers.auth.settings",
        ADMIN_EMAIL=TEST_ADMIN_EMAIL,
        ADMIN_PASSWORD=TEST_ADMIN_PASSWORD,
        ADMIN_JWT_SECRET=TEST_JWT_SECRET,
    ):
        create_res = client.post("/api/events/create", json={
            "title": "Sharing Test Event",
            "event_code": "SHARINGTEST",
        }, headers=auth_headers)

    # 1. Fetch all events
    res = client.get("/api/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1
    print(f" [OK] /api/events successfully returned {len(events)} event(s).")
    for ev in events:
        print(f"      * Title: '{ev['title']}' | Code: '{ev['event_code']}' | Protected: {ev.get('is_protected')} | Photos: {ev.get('photo_count')}")

    # 2. Test accessing first event by Code (the backend supports lookup by code only)
    test_ev = events[0]
    res_by_code = client.get(f"/api/events/{test_ev['event_code']}")
    assert res_by_code.status_code == 200
    assert res_by_code.json()["id"] == test_ev["id"]
    print(f" [OK] Guest access by Event Code '{test_ev['event_code']}' passed!")

if __name__ == "__main__":
    test_admin_auth()
    test_event_visibility_and_access()
    print("\n [SUCCESS] ALL COMPREHENSIVE VERIFICATION TESTS PASSED!")
