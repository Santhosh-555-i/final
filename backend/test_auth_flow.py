"""
Authentication flow integration tests.

Tests:
1. Backend login endpoint validates email and password
2. JWT token is created and returned
3. Authenticated endpoints reject requests without token
4. Authenticated endpoints reject requests with invalid token
5. Authenticated endpoints accept valid JWT

Run: python -m unittest test_auth_flow -v
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Patch Supabase before importing anything that touches database ──────────
mock_supabase = MagicMock()
with patch.dict(os.environ, {
    "DB_MODE": "sqlite",
    "ADMIN_EMAIL": "test_admin@example.com",
    "ADMIN_PASSWORD": "test_pass_123",
    "ADMIN_JWT_SECRET": "test-jwt-secret-for-unit-tests-only-32chars",
}):
    from fastapi.testclient import TestClient
    from app.main import app

client = TestClient(app)

ADMIN_EMAIL = "test_admin@example.com"
ADMIN_PASSWORD = "test_pass_123"
JWT_SECRET = "test-jwt-secret-for-unit-tests-only-32chars"


class TestAdminLoginEndpoint(unittest.TestCase):
    """Backend /api/auth/login endpoint tests."""

    def _patch_settings(self):
        return patch.multiple(
            "app.routers.auth.settings",
            ADMIN_EMAIL=ADMIN_EMAIL,
            ADMIN_PASSWORD=ADMIN_PASSWORD,
            ADMIN_JWT_SECRET=JWT_SECRET,
        )

    def test_login_success_returns_token(self):
        """Valid credentials produce a JWT token in the response."""
        with self._patch_settings():
            resp = client.post("/api/auth/login", json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            })
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertIsInstance(data["token"], str)
        self.assertGreater(len(data["token"]), 20)
        self.assertEqual(data["email"], ADMIN_EMAIL)

    def test_login_wrong_password_returns_401(self):
        """Wrong password is rejected with 401."""
        with self._patch_settings():
            resp = client.post("/api/auth/login", json={
                "email": ADMIN_EMAIL,
                "password": "wrong_password",
            })
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_login_wrong_email_returns_403(self):
        """Wrong email is rejected with 403."""
        with self._patch_settings():
            resp = client.post("/api/auth/login", json={
                "email": "wrong@example.com",
                "password": ADMIN_PASSWORD,
            })
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_login_email_case_insensitive(self):
        """Email comparison must be case-insensitive (matches backend behavior)."""
        with self._patch_settings():
            resp = client.post("/api/auth/login", json={
                "email": ADMIN_EMAIL.upper(),
                "password": ADMIN_PASSWORD,
            })
        # Backend does .lower() on both sides, so this should succeed
        self.assertEqual(resp.status_code, 200, resp.text)


class TestAuthenticatedEndpoints(unittest.TestCase):
    """JWT-protected endpoints must reject unauthenticated requests."""

    def _patch_settings(self):
        return patch.multiple(
            "app.routers.auth.settings",
            ADMIN_EMAIL=ADMIN_EMAIL,
            ADMIN_PASSWORD=ADMIN_PASSWORD,
            ADMIN_JWT_SECRET=JWT_SECRET,
        )

    def _get_valid_token(self) -> str:
        with self._patch_settings():
            resp = client.post("/api/auth/login", json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            })
        return resp.json()["token"]

    def test_profile_without_token_returns_401(self):
        """GET /api/auth/profile without token → 401."""
        resp = client.get("/api/auth/profile")
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_profile_with_invalid_token_returns_401(self):
        """GET /api/auth/profile with garbage token → 401."""
        resp = client.get("/api/auth/profile", headers={
            "Authorization": "Bearer this.is.not.a.valid.jwt"
        })
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_profile_with_valid_token_returns_200(self):
        """GET /api/auth/profile with valid Bearer token → 200."""
        token = self._get_valid_token()
        with self._patch_settings():
            resp = client.get("/api/auth/profile", headers={
                "Authorization": f"Bearer {token}"
            })
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["admin_email"].lower(), ADMIN_EMAIL.lower())

    def test_create_event_without_token_returns_401(self):
        """POST /api/events/create without token → 401."""
        resp = client.post("/api/events/create", json={
            "title": "Test Event"
        })
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_create_event_with_valid_token_returns_201(self):
        """POST /api/events/create with valid Bearer token → 201."""
        token = self._get_valid_token()
        with self._patch_settings():
            resp = client.post("/api/events/create", json={
                "title": "Unit Test Event",
                "event_code": "TEST-EVT-01"
            }, headers={
                "Authorization": f"Bearer {token}"
            })
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self.assertEqual(data["title"], "Unit Test Event")
        self.assertEqual(data["event_code"], "TEST-EVT-01")


class TestNextConfig(unittest.TestCase):
    """
    Verify next.config.ts has trailingSlash: false to avoid 308 redirects on API requests.
    """

    def test_trailing_slash_is_disabled(self):
        base = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.normpath(os.path.join(base, "..", "frontend", "next.config.ts"))
        if not os.path.exists(config_path):
            self.skipTest("next.config.ts not found")
        with open(config_path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("trailingSlash: false", src,
            "next.config.ts must have trailingSlash: false so API rewrites do not trigger 308 redirects")


class TestTokenStorage(unittest.TestCase):
    """
    Verify the contract between api.ts and admin/page.tsx regarding
    where the JWT token is stored.

    These tests inspect the source code to catch future mismatches.
    """

    def _read_file(self, rel_path: str) -> str:
        base = os.path.dirname(os.path.abspath(__file__))
        # Try frontend path relative to backend dir
        frontend_path = os.path.normpath(os.path.join(base, "..", "frontend", rel_path))
        if os.path.exists(frontend_path):
            with open(frontend_path, encoding="utf-8") as f:
                return f.read()
        return ""

    def test_adminfetch_reads_sessionStorage_eventlens_admin_token(self):
        """api.ts adminFetch must read from sessionStorage key 'eventlens_admin_token'."""
        src = self._read_file("src/lib/api.ts")
        if not src:
            self.skipTest("Frontend src not found alongside backend")
        self.assertIn("sessionStorage.getItem('eventlens_admin_token')", src,
            "adminFetch must read token from sessionStorage key 'eventlens_admin_token'")
        self.assertNotIn("localStorage.getItem('admin_token')", src,
            "adminFetch must NOT use the old localStorage key 'admin_token'")

    def test_admin_page_writes_to_sessionStorage_eventlens_admin_token(self):
        """admin/page.tsx must store token in sessionStorage under 'eventlens_admin_token'."""
        src = self._read_file("src/app/admin/page.tsx")
        if not src:
            self.skipTest("Frontend src not found alongside backend")
        self.assertIn('sessionStorage.setItem("eventlens_admin_token"', src,
            "admin/page.tsx must write the JWT to sessionStorage key 'eventlens_admin_token'")

    def test_token_storage_keys_are_consistent(self):
        """The key used to write the token must match the key used to read it."""
        api_src = self._read_file("src/lib/api.ts")
        page_src = self._read_file("src/app/admin/page.tsx")
        if not api_src or not page_src:
            self.skipTest("Frontend src not found alongside backend")

        # Extract the key adminFetch reads
        import re
        read_match = re.search(r"sessionStorage\.getItem\(['\"](\w+)['\"]", api_src)
        write_match = re.search(r'sessionStorage\.setItem\(["\']([\w]+)["\'],\s*res\.token', page_src)

        self.assertIsNotNone(read_match, "Could not find sessionStorage.getItem in api.ts")
        self.assertIsNotNone(write_match, "Could not find sessionStorage.setItem for token in admin/page.tsx")

        read_key = read_match.group(1)
        write_key = write_match.group(1)
        self.assertEqual(read_key, write_key,
            f"MISMATCH: adminFetch reads key '{read_key}' but admin/page.tsx writes key '{write_key}'")


if __name__ == "__main__":
    print("=" * 60)
    print("Running authentication flow tests")
    print("=" * 60)
    unittest.main(verbosity=2)
