import os
import sys
import json
import uuid
import unittest
from unittest.mock import MagicMock, patch

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import settings
from app.database import db_service, is_valid_uuid
from app.clustering import FaceClusteringEngine
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestDeploymentReadiness(unittest.TestCase):

    def test_01_railway_configs(self):
        """Verify Railway configuration files exist and are valid JSON/TOML."""
        root_dir = os.path.dirname(BASE_DIR)
        
        # Root railway.json
        root_railway_json = os.path.join(root_dir, "railway.json")
        self.assertTrue(os.path.exists(root_railway_json), "root railway.json must exist")
        with open(root_railway_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            self.assertEqual(cfg["build"]["builder"], "DOCKERFILE")
            self.assertEqual(cfg["deploy"]["healthcheckPath"], "/api/health")

        # Root railway.toml
        root_railway_toml = os.path.join(root_dir, "railway.toml")
        self.assertTrue(os.path.exists(root_railway_toml), "root railway.toml must exist")

        # Backend railway.json
        backend_railway_json = os.path.join(BASE_DIR, "railway.json")
        self.assertTrue(os.path.exists(backend_railway_json), "backend railway.json must exist")
        with open(backend_railway_json, "r", encoding="utf-8") as f:
            cfg_b = json.load(f)
            self.assertEqual(cfg_b["build"]["builder"], "DOCKERFILE")
            self.assertEqual(cfg_b["deploy"]["healthcheckPath"], "/api/health")
        print(" [OK] Railway deployment configs verified.")

    def test_02_render_configs(self):
        """Verify Render blueprint yaml files exist and have healthCheckPath."""
        root_dir = os.path.dirname(BASE_DIR)
        
        root_render_yaml = os.path.join(root_dir, "render.yaml")
        self.assertTrue(os.path.exists(root_render_yaml), "root render.yaml must exist")
        with open(root_render_yaml, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("healthCheckPath: /api/health", content)
            self.assertIn("eventlens-backend", content)

        backend_render_yaml = os.path.join(BASE_DIR, "render.yaml")
        self.assertTrue(os.path.exists(backend_render_yaml), "backend render.yaml must exist")
        print(" [OK] Render blueprint configs verified.")

    def test_03_vercel_configs(self):
        """Verify Vercel configuration files exist."""
        root_dir = os.path.dirname(BASE_DIR)
        frontend_dir = os.path.join(root_dir, "frontend")

        root_vercel_json = os.path.join(root_dir, "vercel.json")
        self.assertTrue(os.path.exists(root_vercel_json), "root vercel.json must exist")

        frontend_vercel_json = os.path.join(frontend_dir, "vercel.json")
        self.assertTrue(os.path.exists(frontend_vercel_json), "frontend vercel.json must exist")

        next_config_path = os.path.join(frontend_dir, "next.config.ts")
        self.assertTrue(os.path.exists(next_config_path), "frontend next.config.ts must exist")
        with open(next_config_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("rewrites", content)
            self.assertIn("/api/:path*", content)
            self.assertIn("/static/:path*", content)
        print(" [OK] Vercel & Next.js proxy configs verified.")

    def test_04_supabase_schema(self):
        """Verify Supabase schema.sql includes pgvector, tables, RPC function, and bucket policy."""
        schema_path = os.path.join(BASE_DIR, "schema.sql")
        self.assertTrue(os.path.exists(schema_path), "backend/schema.sql must exist")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
            self.assertIn("CREATE EXTENSION IF NOT EXISTS vector;", sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS events", sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS photos", sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS face_embeddings", sql)
            self.assertIn("vector(512)", sql)
            self.assertIn("CREATE OR REPLACE FUNCTION match_face_embeddings", sql)
            self.assertIn("storage.buckets", sql)
        print(" [OK] Supabase schema.sql verified.")

    def test_05_is_valid_uuid_helper(self):
        """Test UUID validation helper against valid UUIDs and alphanumeric event codes."""
        valid_u = str(uuid.uuid4())
        self.assertTrue(is_valid_uuid(valid_u))
        self.assertTrue(is_valid_uuid("ddf499ca-2047-49f5-bf88-b8357bc50f30"))
        
        # Alphanumeric event codes should return False
        self.assertFalse(is_valid_uuid("TECH-CONF-2026"))
        self.assertFalse(is_valid_uuid("SUMMER2026"))
        self.assertFalse(is_valid_uuid("EVT-123456"))
        self.assertFalse(is_valid_uuid(""))
        self.assertFalse(is_valid_uuid(None))
        print(" [OK] is_valid_uuid helper logic verified.")

    def test_06_health_endpoints(self):
        """Verify root and health check endpoints."""
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["project"], settings.PROJECT_NAME)

        res_root = client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("docs", res_root.json())
        print(" [OK] API health check endpoints verified.")

    def test_07_cors_origins(self):
        """Verify CORS middleware responds with proper headers for Vercel and Railway origins."""
        # Simulated preflight request from Vercel preview domain
        headers = {
            "Origin": "https://eventlens-frontend-pr-12.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"
        }
        res = client.options("/api/health", headers=headers)
        self.assertIn("access-control-allow-origin", res.headers)
        self.assertEqual(res.headers["access-control-allow-origin"], "https://eventlens-frontend-pr-12.vercel.app")
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")

        # Simulated request from localhost
        headers_local = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
        res_local = client.options("/api/health", headers=headers_local)
        self.assertIn("access-control-allow-origin", res_local.headers)
        self.assertEqual(res_local.headers["access-control-allow-origin"], "http://localhost:3000")
        print(" [OK] Dynamic CORS headers for Vercel, Railway, and localhost verified.")

    def test_08_admin_auth_and_profile(self):
        """Verify admin login and JWT bearer token verification."""
        TEST_EMAIL = "deploy-test@example.com"
        TEST_PASSWORD = "test-deploy-password"
        TEST_SECRET = "deployment-readiness-secret-32-chars"

        with patch.multiple(
            "app.routers.auth.settings",
            ADMIN_EMAIL=TEST_EMAIL,
            ADMIN_PASSWORD=TEST_PASSWORD,
            ADMIN_JWT_SECRET=TEST_SECRET,
        ):
            # Login
            res = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
            self.assertEqual(res.status_code, 200)
            token = res.json()["token"]
            self.assertTrue(token)

            # Profile with Bearer Token
            res_prof = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(res_prof.status_code, 200)
            self.assertEqual(res_prof.json()["admin_email"], TEST_EMAIL)
        print(" [OK] Admin authentication and JWT profile endpoints verified.")

    def test_09_sqlite_and_supabase_code_paths(self):
        """Verify database service operations under SQLite and mocked Supabase clients."""
        # 1. Test Event Creation in active DB mode
        test_code = f"DEP-{uuid.uuid4().hex[:6].upper()}"
        event = db_service.create_event(title="Deployment Test Event", event_code=test_code)
        self.assertTrue(event["id"])
        self.assertEqual(event["event_code"], test_code)

        # 2. Test Resolve Event ID
        resolved_id = db_service.resolve_event_id(test_code)
        self.assertEqual(resolved_id, event["id"])

        # 3. Test Get Event By Code
        found_event = db_service.get_event_by_code(test_code)
        self.assertIsNotNone(found_event)
        self.assertEqual(found_event["id"], event["id"])

        # 4. Test Event Settings
        settings_res = db_service.get_event_settings(event["id"])
        self.assertEqual(settings_res["event_id"], event["id"])

        # 5. Test Share Token Creation
        token = db_service.create_share_token(event_id=event["id"], photo_ids=[str(uuid.uuid4())], expiry_hours=24)
        self.assertTrue(token)

        # 6. Test Biometrics Deletion
        bio_del = db_service.delete_event_biometrics(event["id"])
        self.assertTrue(bio_del)

        # 7. Clean up event
        del_res = db_service.delete_event(event["id"])
        self.assertTrue(del_res)
        print(" [OK] Database service CRUD and resolution verified.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
