"""
Tests to verify that the Supabase-mode production fixes are correct.

These tests are designed to run without actual Supabase credentials.
They verify structural correctness of the fix, not end-to-end DB connectivity.

Run: python test_supabase_mode_fixes.py
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# make sure we can import from the `app` package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestFaceClusteringEngineInit(unittest.TestCase):
    """FaceClusteringEngine must accept db_path=None (Supabase mode)."""

    def _import_engine(self):
        from app.clustering import FaceClusteringEngine
        return FaceClusteringEngine

    def test_init_with_none(self):
        """db_path=None must not raise (Supabase / production mode)."""
        FaceClusteringEngine = self._import_engine()
        engine = FaceClusteringEngine(db_path=None)
        self.assertIsNone(engine.db_path)

    def test_init_with_string(self):
        """db_path as string must still work (SQLite / local mode)."""
        FaceClusteringEngine = self._import_engine()
        engine = FaceClusteringEngine(db_path="/tmp/test.db")
        self.assertEqual(engine.db_path, "/tmp/test.db")

    def test_init_default_is_none(self):
        """Default constructor (no arguments) must use None."""
        FaceClusteringEngine = self._import_engine()
        engine = FaceClusteringEngine()
        self.assertIsNone(engine.db_path)


class TestDatabaseServiceSupabaseHasNoDbPath(unittest.TestCase):
    """DatabaseService must NOT set self.db_path in the supabase branch."""

    def test_db_path_not_in_supabase_branch(self):
        import inspect
        from app.database import DatabaseService
        src = inspect.getsource(DatabaseService.__init__)
        lines = src.splitlines()
        in_supabase_branch = False
        supabase_sets_db_path = False
        for line in lines:
            stripped = line.strip()
            if 'if settings.DB_MODE == "supabase"' in stripped:
                in_supabase_branch = True
            elif stripped.startswith("else:") and in_supabase_branch:
                in_supabase_branch = False
            if in_supabase_branch and "self.db_path" in stripped:
                supabase_sets_db_path = True
        self.assertFalse(
            supabase_sets_db_path,
            "DatabaseService.__init__ must NOT set self.db_path in the supabase branch"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Running Supabase-mode fix verification tests")
    print("=" * 60)
    unittest.main(verbosity=2)
