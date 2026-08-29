import os
import json
import uuid
import sqlite3
import hashlib
import urllib.parse
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any
from passlib.context import CryptContext
from app.config import settings

pwd_context = None  # passlib replaced by direct bcrypt calls below

def is_valid_uuid(val) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val).strip())
        return True
    except (ValueError, AttributeError, TypeError):
        return False

class DatabaseService:
    def __init__(self):
        if settings.DB_MODE == "supabase":
            try:
                from supabase import create_client
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
                print("[Database] Connected to Supabase PostgreSQL database")
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase client init failed: {e}")
        else:
            self.supabase = None
            self.db_path = os.path.join(settings.BASE_DIR, "eventlens.db")
            self._vector_cache = {}  # event_id -> {"matrix": np.ndarray, "metadata": List[Dict]}
            self._init_sqlite()
            print("[Database] Connected to SQLite database")

    def invalidate_event_cache(self, event_id: Optional[str] = None):
        """Invalidates in-memory vector cache for an event or all events"""
        if settings.DB_MODE != "sqlite":
            return
        if event_id:
            actual_id = self.resolve_event_id(event_id) or event_id
            self._vector_cache.pop(actual_id, None)
            self._vector_cache.pop(event_id, None)
        else:
            self._vector_cache.clear()

    def _init_sqlite(self):
        """Creates SQLite tables if not exists and auto-migrates columns for local vector matching"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                event_code TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                is_protected INTEGER DEFAULT 0,
                drive_link TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                image_url TEXT NOT NULL,
                thumbnail_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                cluster_id TEXT,
                embedding_json TEXT NOT NULL,
                bounding_box_json TEXT NOT NULL,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_clusters (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                name TEXT NOT NULL,
                thumbnail_url TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS share_tokens (
                token TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                photo_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_revoked INTEGER DEFAULT 0,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                event_id TEXT,
                action TEXT NOT NULL,
                details_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_settings (
                event_id TEXT PRIMARY KEY,
                similarity_threshold REAL DEFAULT 0.35,
                retention_days INTEGER DEFAULT 90,
                selfie_search_enabled INTEGER DEFAULT 1,
                downloads_enabled INTEGER DEFAULT 1,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                total_files INTEGER DEFAULT 0,
                processed_files INTEGER DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

        cursor.execute("PRAGMA table_info(events)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "password_hash" not in existing_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN password_hash TEXT")
        if "is_protected" not in existing_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN is_protected INTEGER DEFAULT 0")
        if "drive_link" not in existing_cols:
            cursor.execute("ALTER TABLE events ADD COLUMN drive_link TEXT")

        cursor.execute("PRAGMA table_info(face_embeddings)")
        fe_cols = [row[1] for row in cursor.fetchall()]
        if "cluster_id" not in fe_cols:
            cursor.execute("ALTER TABLE face_embeddings ADD COLUMN cluster_id TEXT")

        conn.commit()
        conn.close()

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt directly (compatible with bcrypt 4.x+)."""
        import bcrypt
        pw = password.strip().encode("utf-8")
        if len(pw) > 72:
            pw = pw[:72]
        return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")
        
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt directly, with SHA-256 fallback for legacy hashes."""
        import bcrypt
        try:
            pw = plain_password.strip().encode("utf-8")
            if len(pw) > 72:
                pw = pw[:72]
            return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))
        except Exception:
            # Legacy SHA-256 fallback for old hashes
            old_hash = hashlib.sha256(plain_password.strip().encode("utf-8")).hexdigest()
            return old_hash == hashed_password

    def create_event(
        self,
        title: str,
        event_code: Optional[str] = None,
        password: Optional[str] = None,
        drive_link: Optional[str] = None
    ) -> Dict:
        event_id = str(uuid.uuid4())
        if not event_code:
            code_suffix = uuid.uuid4().hex[:6].upper()
            event_code = f"EVT-{code_suffix}"
        else:
            event_code = event_code.strip().upper()

        created_at = datetime.now(timezone.utc).isoformat()
        is_protected = bool(password and password.strip())
        password_hash = self._hash_password(password) if is_protected else None
        clean_drive_link = drive_link.strip() if drive_link and drive_link.strip() else None

        if settings.DB_MODE == "supabase":
            payload = {
                "id": event_id,
                "title": title,
                "event_code": event_code,
                "password_hash": password_hash,
                "is_protected": is_protected,
                "drive_link": clean_drive_link,
                "created_at": created_at
            }
            try:
                res = self.supabase.table("events").insert(payload).execute()
                if res.data:
                    item = res.data[0]
                    item["photo_count"] = 0
                    item.pop("password_hash", None)
                    return item
                raise RuntimeError("Supabase returned empty data for event creation.")
            except Exception as e:
                err_str = str(e)
                if "drive_link" in err_str or "PGRST204" in err_str:
                    payload.pop("drive_link", None)
                    try:
                        res = self.supabase.table("events").insert(payload).execute()
                        if res.data:
                            item = res.data[0]
                            item["photo_count"] = 0
                            item["drive_link"] = clean_drive_link
                            item.pop("password_hash", None)
                            return item
                    except Exception as ex:
                        raise RuntimeError(f"[Database Error] Supabase create_event failed: {ex}")
                raise RuntimeError(f"[Database Error] Supabase create_event failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO events 
                   (id, title, event_code, password_hash, is_protected, drive_link, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, title, event_code, password_hash, 1 if is_protected else 0, clean_drive_link, created_at)
            )
            conn.commit()
            conn.close()

            return {
                "id": event_id,
                "title": title,
                "event_code": event_code,
                "is_protected": is_protected,
                "drive_link": clean_drive_link,
                "created_at": created_at,
                "photo_count": 0
            }

    def update_event_drive_link(self, event_id: str, drive_link: str) -> bool:
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("events").update({"drive_link": drive_link}).eq("id", event_id).execute()
                return True
            except Exception as e:
                print(f"[Database Warning] Supabase update_event_drive_link notice: {e}")
                return False
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE events SET drive_link = ? WHERE id = ?", (drive_link, event_id))
            conn.commit()
            conn.close()
            return True

    def resolve_event_id(self, event_id_or_code_or_title: str) -> Optional[str]:
        if not event_id_or_code_or_title:
            return None
        raw = str(event_id_or_code_or_title).strip()
        unquoted = urllib.parse.unquote(raw).strip()
        
        if raw.startswith("mock-"):
            raw = raw.replace("mock-", "")
        if unquoted.startswith("mock-"):
            unquoted = unquoted.replace("mock-", "")

        if settings.DB_MODE == "supabase":
            try:
                or_filters = [
                    f"event_code.ilike.{raw}",
                    f"event_code.ilike.{unquoted}",
                    f"title.ilike.{raw}",
                    f"title.ilike.{unquoted}",
                ]
                if is_valid_uuid(raw):
                    or_filters.append(f"id.eq.{raw}")
                if is_valid_uuid(unquoted) and unquoted != raw:
                    or_filters.append(f"id.eq.{unquoted}")

                res = self.supabase.table("events").select("id").or_(",".join(or_filters)).limit(1).execute()
                if res.data:
                    return res.data[0]["id"]
                
                res2 = self.supabase.table("events").select("id").ilike("title", f"%{unquoted}%").order("created_at", desc=True).limit(1).execute()
                if res2.data:
                    return res2.data[0]["id"]
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase resolve_event_id failed: {e}")
            return raw
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM events 
                WHERE UPPER(id) = UPPER(?) 
                   OR UPPER(id) = UPPER(?)
                   OR UPPER(event_code) = UPPER(?) 
                   OR UPPER(event_code) = UPPER(?)
                   OR UPPER(title) = UPPER(?)
                   OR UPPER(title) = UPPER(?)
                LIMIT 1
            """, (raw, unquoted, raw, unquoted, raw, unquoted))
            row = cursor.fetchone()
            
            if not row:
                cursor.execute("""
                    SELECT id FROM events 
                    WHERE UPPER(title) LIKE '%' || UPPER(?) || '%'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (unquoted,))
                row = cursor.fetchone()

            conn.close()
            if row:
                return row["id"]
            return raw

    def verify_event_password(self, event_code_or_title: str, password: str) -> bool:
        event = self.get_event_by_code(event_code_or_title)
        if not event:
            return False
        if not event.get("is_protected"):
            return True

        actual_id = event["id"]
        if settings.DB_MODE == "supabase":
            res = self.supabase.table("events").select("password_hash").eq("id", actual_id).execute()
            if res.data and res.data[0].get("password_hash"):
                return self._verify_password(password, res.data[0]["password_hash"])
            return True
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM events WHERE id = ?", (actual_id,))
            row = cursor.fetchone()
            conn.close()

            if not row or not row["password_hash"]:
                return True

            return self._verify_password(password, row["password_hash"])

    def get_event_by_code(self, event_code_or_title: str) -> Optional[Dict]:
        raw = str(event_code_or_title).strip()
        unquoted = urllib.parse.unquote(raw).strip()
        if raw.startswith("mock-"):
            raw = raw.replace("mock-", "")
        if unquoted.startswith("mock-"):
            unquoted = unquoted.replace("mock-", "")

        if settings.DB_MODE == "supabase":
            try:
                or_filters = [
                    f"event_code.ilike.{raw}",
                    f"event_code.ilike.{unquoted}",
                    f"title.ilike.{raw}",
                    f"title.ilike.{unquoted}",
                ]
                if is_valid_uuid(raw):
                    or_filters.append(f"id.eq.{raw}")
                if is_valid_uuid(unquoted) and unquoted != raw:
                    or_filters.append(f"id.eq.{unquoted}")

                res = self.supabase.table("events").select("*").or_(",".join(or_filters)).execute()
                if res.data:
                    event = res.data[0]
                    p_res = self.supabase.table("photos").select("id", count="exact").eq("event_id", event["id"]).execute()
                    event["photo_count"] = p_res.count if p_res.count is not None else len(p_res.data or [])
                    event.pop("password_hash", None)
                    event["is_protected"] = bool(event.get("is_protected"))
                    return event
                
                res2 = self.supabase.table("events").select("*").ilike("title", f"%{unquoted}%").order("created_at", desc=True).limit(1).execute()
                if res2.data:
                    event = res2.data[0]
                    p_res = self.supabase.table("photos").select("id", count="exact").eq("event_id", event["id"]).execute()
                    event["photo_count"] = p_res.count if p_res.count is not None else len(p_res.data or [])
                    event.pop("password_hash", None)
                    event["is_protected"] = bool(event.get("is_protected"))
                    return event
                return None
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase get_event_by_code failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM events 
                WHERE UPPER(event_code) = UPPER(?) 
                   OR UPPER(event_code) = UPPER(?) 
                   OR UPPER(title) = UPPER(?) 
                   OR UPPER(title) = UPPER(?)
                   OR UPPER(id) = UPPER(?) 
                   OR UPPER(id) = UPPER(?)
                LIMIT 1
            """, (raw, unquoted, raw, unquoted, raw, unquoted))
            row = cursor.fetchone()
            
            if not row:
                cursor.execute("""
                    SELECT * FROM events 
                    WHERE UPPER(title) LIKE '%' || UPPER(?) || '%'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (unquoted,))
                row = cursor.fetchone()

            if not row:
                conn.close()
                return None

            event = dict(row)
            cursor.execute("SELECT COUNT(*) FROM photos WHERE event_id = ?", (event["id"],))
            event["photo_count"] = cursor.fetchone()[0]
            conn.close()

            event.pop("password_hash", None)
            event["is_protected"] = bool(event.get("is_protected", 0))
            return event

    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        return self.get_event_by_code(event_id)

    def get_all_events(self) -> List[Dict]:
        if settings.DB_MODE == "supabase":
            try:
                res = self.supabase.table("events").select("*").order("created_at", desc=True).execute()
                if res.data:
                    events = res.data
                    for ev in events:
                        p_res = self.supabase.table("photos").select("id", count="exact").eq("event_id", ev["id"]).execute()
                        ev["photo_count"] = p_res.count if p_res.count is not None else len(p_res.data or [])
                        ev.pop("password_hash", None)
                        ev["is_protected"] = bool(ev.get("is_protected"))
                    return events
                return []
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase get_all_events failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.id, e.title, e.event_code, e.created_at, e.is_protected, e.drive_link,
                       COUNT(p.id) as photo_count
                FROM events e
                LEFT JOIN photos p ON e.id = p.event_id
                GROUP BY e.id
                ORDER BY e.created_at DESC
            """)
            rows = cursor.fetchall()
            events = []
            for r in rows:
                ev = dict(r)
                ev["is_protected"] = bool(ev.get("is_protected", 0))
                events.append(ev)
            conn.close()
            return events

    def _format_photo_record(self, p: Dict) -> Dict:
        if not p:
            return p
        from app.storage import storage_service
        raw_img = p.get("image_url", "")
        raw_thumb = p.get("thumbnail_url", "")
        p["image_url"] = storage_service.resolve_image_url(raw_img, is_thumbnail=False)
        p["thumbnail_url"] = storage_service.resolve_image_url(raw_thumb or raw_img, is_thumbnail=True)
        return p

    def get_event_photos(self, event_id: str, limit: int = 200, offset: int = 0) -> List[Dict]:
        actual_event_id = self.resolve_event_id(event_id) or event_id

        if settings.DB_MODE == "supabase":
            try:
                res = self.supabase.table("photos").select("*").eq("event_id", actual_event_id).order("created_at", desc=True).range(offset, offset+limit-1).execute()
                photos = res.data or []
                return [self._format_photo_record(p) for p in photos]
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase get_event_photos failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, event_id, image_url, thumbnail_url, created_at 
                   FROM photos 
                   WHERE event_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (actual_event_id, limit, offset)
            )
            rows = cursor.fetchall()
            conn.close()
            return [self._format_photo_record(dict(r)) for r in rows]

    def insert_face_embeddings_for_photo(
        self, photo_id: str, event_id: str, faces: List[Dict], image_url: str = ""
    ) -> int:
        """
        Inserts 512-d facial embeddings for a photo with schema resilience.
        Supports both modern schema (photo_id, event_id, embedding, bounding_box)
        and legacy schema (image_name, image_url, embedding).
        """
        if not faces:
            return 0

        actual_event_id = self.resolve_event_id(event_id) or event_id
        clean_img_name = os.path.basename(image_url) if image_url else f"photo_{photo_id}.jpg"

        if settings.DB_MODE == "supabase":
            embedding_rows = []
            for face in faces:
                emb = face.get("embedding")
                if not emb or len(emb) != 512:
                    continue
                emb_id = str(uuid.uuid4())
                row = {
                    "id": emb_id,
                    "photo_id": photo_id,
                    "event_id": actual_event_id,
                    "embedding": emb,
                    "bounding_box": face.get("bounding_box")
                }
                embedding_rows.append(row)

            if not embedding_rows:
                return 0

            # Attempt 1: Full modern schema (id, photo_id, event_id, embedding, bounding_box)
            try:
                self.supabase.table("face_embeddings").insert(embedding_rows).execute()
                print(f"[Face Indexing Pipeline] Inserted {len(embedding_rows)} face embedding(s) into Supabase for photo {photo_id}")
                return len(embedding_rows)
            except Exception as e1:
                print(f"[Face Indexing Notice] Full schema insert attempt: {e1}. Retrying with adapted schema...")

            # Attempt 2: Minimal modern schema (photo_id, event_id, embedding)
            try:
                minimal_rows = [
                    {"photo_id": r["photo_id"], "event_id": r["event_id"], "embedding": r["embedding"]}
                    for r in embedding_rows
                ]
                self.supabase.table("face_embeddings").insert(minimal_rows).execute()
                print(f"[Face Indexing Pipeline] Inserted {len(minimal_rows)} face embedding(s) (minimal modern) for photo {photo_id}")
                return len(minimal_rows)
            except Exception as e2:
                print(f"[Face Indexing Notice] Minimal modern schema insert attempt: {e2}")

            # Attempt 3: Legacy schema with image_name / image_url
            try:
                legacy_rows = [
                    {
                        "image_name": clean_img_name,
                        "image_url": image_url or clean_img_name,
                        "embedding": r["embedding"]
                    }
                    for r in embedding_rows
                ]
                self.supabase.table("face_embeddings").insert(legacy_rows).execute()
                print(f"[Face Indexing Pipeline] Inserted {len(legacy_rows)} face embedding(s) (legacy format) for photo {photo_id}")
                return len(legacy_rows)
            except Exception as e3:
                print(f"[Face Indexing Error] All Supabase face_embeddings insert attempts failed: {e3}")
                return 0
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            count = 0
            for face in faces:
                emb = face.get("embedding")
                if not emb or len(emb) != 512:
                    continue
                emb_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO face_embeddings (id, photo_id, event_id, embedding_json, bounding_box_json) VALUES (?, ?, ?, ?, ?)",
                    (emb_id, photo_id, actual_event_id, json.dumps(emb), json.dumps(face.get("bounding_box")))
                )
                count += 1
            conn.commit()
            conn.close()
            self.invalidate_event_cache(actual_event_id)
            return count

    def backfill_missing_embeddings(self, event_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans all photos (or photos in a specific event), detects photos that lack
        face embeddings in public.face_embeddings, downloads their image bytes,
        extracts 512-d FaceNet embeddings, and stores them in public.face_embeddings.
        """
        from app.storage import storage_service
        from app.ml_engine import ml_engine

        print(f"[Face Backfill] Starting face embedding audit and backfill (event_id={event_id})...")
        actual_event_id = self.resolve_event_id(event_id) if event_id else None

        photos_to_process = []
        if settings.DB_MODE == "supabase":
            try:
                # 1. Fetch all photos
                query = self.supabase.table("photos").select("id, event_id, image_url, thumbnail_url")
                if actual_event_id:
                    query = query.eq("event_id", actual_event_id)
                p_res = query.order("created_at", desc=True).limit(500).execute()
                all_photos = p_res.data or []

                # 2. Fetch existing photo_ids from face_embeddings
                fe_query = self.supabase.table("face_embeddings").select("photo_id")
                if actual_event_id:
                    fe_query = fe_query.eq("event_id", actual_event_id)
                fe_res = fe_query.execute()
                existing_pids = {r["photo_id"] for r in (fe_res.data or []) if r.get("photo_id")}

                # Filter photos that need embeddings
                for p in all_photos:
                    if p["id"] not in existing_pids:
                        photos_to_process.append(p)
            except Exception as e:
                print(f"[Face Backfill Error] Supabase photo scan failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if actual_event_id:
                cursor.execute("""
                    SELECT p.id, p.event_id, p.image_url, p.thumbnail_url
                    FROM photos p
                    LEFT JOIN face_embeddings fe ON p.id = fe.photo_id
                    WHERE p.event_id = ? AND fe.id IS NULL
                """, (actual_event_id,))
            else:
                cursor.execute("""
                    SELECT p.id, p.event_id, p.image_url, p.thumbnail_url
                    FROM photos p
                    LEFT JOIN face_embeddings fe ON p.id = fe.photo_id
                    WHERE fe.id IS NULL
                """)
            photos_to_process = [dict(r) for r in cursor.fetchall()]
            conn.close()

        total_scanned = len(photos_to_process)
        print(f"[Face Backfill] Found {total_scanned} photo(s) without face embeddings. Beginning processing...")

        processed_count = 0
        total_faces_detected = 0
        total_embeddings_stored = 0
        skipped_count = 0
        errors = []

        for idx, p in enumerate(photos_to_process, 1):
            pid = p["id"]
            pevt = p["event_id"]
            pimg = p["image_url"]
            try:
                img_bytes = storage_service.get_photo_bytes(pimg)
                if not img_bytes or len(img_bytes) < 100:
                    skipped_count += 1
                    print(f"[Face Backfill] Skipped photo {pid} ({idx}/{total_scanned}): could not load image bytes.")
                    continue

                faces = ml_engine.extract_faces_and_embeddings(img_bytes, allow_fallback=True)
                total_faces_detected += len(faces)

                stored = self.insert_face_embeddings_for_photo(
                    photo_id=pid,
                    event_id=pevt,
                    faces=faces,
                    image_url=pimg
                )
                total_embeddings_stored += stored
                processed_count += 1
                print(f"[Face Backfill] ({idx}/{total_scanned}) Photo {pid}: {len(faces)} face(s) detected, {stored} embedding(s) stored.")

            except Exception as proc_err:
                errors.append(f"Photo {pid}: {proc_err}")
                print(f"[Face Backfill Error] Failed processing photo {pid}: {proc_err}")

        summary = {
            "success": True,
            "total_scanned": total_scanned,
            "photos_processed": processed_count,
            "faces_detected": total_faces_detected,
            "embeddings_created": total_embeddings_stored,
            "photos_skipped": skipped_count,
            "errors": errors
        }
        print(f"[Face Backfill Completed] Summary: {summary}")
        return summary

    def insert_photo_and_embeddings(
        self, event_id: str, image_url: str, thumbnail_url: str, faces: List[Dict]
    ) -> Dict:
        actual_event_id = self.resolve_event_id(event_id) or event_id
        photo_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("photos").insert({
                    "id": photo_id,
                    "event_id": actual_event_id,
                    "image_url": image_url,
                    "thumbnail_url": thumbnail_url,
                    "created_at": created_at
                }).execute()

                # Insert facial embeddings using multi-schema resilient pipeline
                self.insert_face_embeddings_for_photo(
                    photo_id=photo_id,
                    event_id=actual_event_id,
                    faces=faces,
                    image_url=image_url
                )

                record = {
                    "id": photo_id,
                    "event_id": actual_event_id,
                    "image_url": image_url,
                    "thumbnail_url": thumbnail_url,
                    "created_at": created_at,
                    "faces_detected": len(faces)
                }
                return self._format_photo_record(record)
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase insert photo failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO photos (id, event_id, image_url, thumbnail_url, created_at) VALUES (?, ?, ?, ?, ?)",
                (photo_id, actual_event_id, image_url, thumbnail_url, created_at)
            )
            for face in faces:
                emb = face.get("embedding")
                if not emb or len(emb) != 512:
                    continue
                emb_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO face_embeddings (id, photo_id, event_id, embedding_json, bounding_box_json) VALUES (?, ?, ?, ?, ?)",
                    (emb_id, photo_id, actual_event_id, json.dumps(emb), json.dumps(face.get("bounding_box")))
                )
            conn.commit()
            conn.close()

            self.invalidate_event_cache(actual_event_id)

            return {
                "id": photo_id,
                "event_id": actual_event_id,
                "image_url": image_url,
                "thumbnail_url": thumbnail_url,
                "created_at": created_at,
                "faces_detected": len(faces)
            }

    def _get_or_load_event_vector_matrix(self, actual_event_id: str) -> Optional[Dict]:
        if actual_event_id in self._vector_cache:
            return self._vector_cache[actual_event_id]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fe.id as emb_id, fe.photo_id, fe.embedding_json, fe.bounding_box_json, p.image_url, p.thumbnail_url
            FROM face_embeddings fe
            JOIN photos p ON fe.photo_id = p.id
            WHERE fe.event_id = ?
        """, (actual_event_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        vectors = []
        metas = []

        for r in rows:
            try:
                emb = np.array(json.loads(r["embedding_json"]), dtype=np.float32)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                vectors.append(emb)
                metas.append({
                    "photo_id": r["photo_id"],
                    "image_url": r["image_url"],
                    "thumbnail_url": r["thumbnail_url"],
                    "bounding_box": json.loads(r["bounding_box_json"]) if r["bounding_box_json"] else None
                })
            except Exception:
                pass

        if not vectors:
            return None

        cache_entry = {
            "matrix": np.vstack(vectors),
            "metas": metas
        }
        self._vector_cache[actual_event_id] = cache_entry
        return cache_entry

    def match_selfie_vector(
        self, event_id: str, selfie_vector: List[float], threshold: float = 0.55
    ) -> List[Dict]:
        from app.storage import storage_service
        actual_event_id = self.resolve_event_id(event_id) or event_id

        # Normalize selfie vector
        v_selfie = np.array(selfie_vector, dtype=np.float32)
        norm_selfie = np.linalg.norm(v_selfie)
        if norm_selfie > 0:
            v_selfie = v_selfie / norm_selfie
        selfie_list = v_selfie.tolist()

        if settings.DB_MODE == "supabase":
            matches = []
            rpc_success = False

            # 1. Try match_faces RPC (existing function in Supabase)
            try:
                rpc_res = self.supabase.rpc("match_faces", {
                    "query_embedding": selfie_list,
                    "match_threshold": float(threshold),
                    "match_count": 50
                }).execute()
                if rpc_res.data:
                    rpc_success = True
                    for row in rpc_res.data:
                        sim_val = round(float(row.get("similarity", 0.0)), 4)
                        pid = row.get("photo_id")
                        candidate_id = row.get("id")
                        
                        # Find matching photo record belonging to target event
                        p_res = None
                        if pid:
                            p_res = self.supabase.table("photos").select("*").eq("id", pid).eq("event_id", actual_event_id).maybe_single().execute()
                        
                        if not (p_res and p_res.data) and candidate_id:
                            # Try candidate_id as photo_id first
                            p_res = self.supabase.table("photos").select("*").eq("id", candidate_id).eq("event_id", actual_event_id).maybe_single().execute()
                            # If not found, candidate_id may be the face_embeddings row id
                            if not (p_res and p_res.data):
                                fe_row = self.supabase.table("face_embeddings").select("photo_id, event_id").eq("id", candidate_id).maybe_single().execute()
                                if fe_row and fe_row.data and fe_row.data.get("photo_id"):
                                    real_pid = fe_row.data["photo_id"]
                                    p_res = self.supabase.table("photos").select("*").eq("id", real_pid).eq("event_id", actual_event_id).maybe_single().execute()
                        
                        if not (p_res and p_res.data) and (row.get("image_url") or row.get("image_name")):
                            img_ref = row.get("image_url") or row.get("image_name")
                            p_res = self.supabase.table("photos").select("*").eq("event_id", actual_event_id).ilike("image_url", f"%{img_ref}%").maybe_single().execute()

                        if p_res and p_res.data:
                            p_formatted = self._format_photo_record(p_res.data)
                            matches.append({
                                "photo_id": p_res.data["id"],
                                "image_url": p_formatted["image_url"],
                                "thumbnail_url": p_formatted["thumbnail_url"],
                                "similarity": sim_val,
                                "bounding_box": row.get("bounding_box")
                            })
            except Exception as e:
                print(f"[Vector Search Notice] match_faces RPC attempt: {e}")

            # 2. Try match_face_embeddings RPC (if target_event_id version is available)
            if not rpc_success:
                try:
                    rpc_res = self.supabase.rpc("match_face_embeddings", {
                        "target_event_id": actual_event_id,
                        "query_embedding": selfie_list,
                        "match_threshold": float(threshold),
                        "match_count": 50
                    }).execute()
                    if rpc_res.data:
                        rpc_success = True
                        for row in rpc_res.data:
                            p_res = self.supabase.table("photos").select("*").eq("id", row["photo_id"]).maybe_single().execute()
                            if p_res and p_res.data:
                                p_formatted = self._format_photo_record(p_res.data)
                                matches.append({
                                    "photo_id": row["photo_id"],
                                    "image_url": p_formatted["image_url"],
                                    "thumbnail_url": p_formatted["thumbnail_url"],
                                    "similarity": round(float(row["similarity"]), 4),
                                    "bounding_box": row.get("bounding_box")
                                })
                except Exception as e:
                    print(f"[Vector Search Notice] match_face_embeddings RPC attempt: {e}")

            # 3. Direct Event Vector Search Fallback (Zero RPC dependency, guarantees 100% event isolation)
            if not matches:
                try:
                    # Query all face embeddings for this specific event
                    fe_res = self.supabase.table("face_embeddings").select("id, photo_id, embedding, bounding_box").eq("event_id", actual_event_id).execute()
                    fe_data = fe_res.data or []
                    
                    if fe_data:
                        # Collect unique photo IDs
                        p_ids = list({f["photo_id"] for f in fe_data if f.get("photo_id")})
                        photo_map = {}
                        if p_ids:
                            p_res = self.supabase.table("photos").select("*").in_("id", p_ids).execute()
                            for p in (p_res.data or []):
                                photo_map[p["id"]] = self._format_photo_record(p)

                        best_matches_by_photo = {}
                        for fe in fe_data:
                            raw_emb = fe.get("embedding")
                            if not raw_emb:
                                continue
                            if isinstance(raw_emb, str):
                                try:
                                    raw_emb = json.loads(raw_emb)
                                except Exception:
                                    continue
                            
                            v_emb = np.array(raw_emb, dtype=np.float32)
                            norm_emb = np.linalg.norm(v_emb)
                            if norm_emb > 0:
                                v_emb = v_emb / norm_emb

                            sim_score = float(np.dot(v_selfie, v_emb))
                            if sim_score >= threshold:
                                pid = fe.get("photo_id")
                                p_info = photo_map.get(pid)
                                if p_info:
                                    if pid not in best_matches_by_photo or sim_score > best_matches_by_photo[pid]["similarity"]:
                                        bbox = fe.get("bounding_box")
                                        if isinstance(bbox, str):
                                            try:
                                                bbox = json.loads(bbox)
                                            except Exception:
                                                pass
                                        best_matches_by_photo[pid] = {
                                            "photo_id": pid,
                                            "image_url": p_info["image_url"],
                                            "thumbnail_url": p_info["thumbnail_url"],
                                            "similarity": round(sim_score, 4),
                                            "bounding_box": bbox
                                        }

                        matches = list(best_matches_by_photo.values())
                except Exception as fallback_err:
                    print(f"[Vector Search Error] Direct Supabase fallback error: {fallback_err}")

            # Deduplicate by photo_id taking highest similarity
            unique_matches = {}
            for m in matches:
                key = m["photo_id"]
                if key not in unique_matches or m["similarity"] > unique_matches[key]["similarity"]:
                    unique_matches[key] = m

            return sorted(unique_matches.values(), key=lambda x: x["similarity"], reverse=True)
        else:
            actual_event_id = self.resolve_event_id(event_id) or event_id
            cache_entry = self._get_or_load_event_vector_matrix(actual_event_id)

            if not cache_entry:
                return []

            matrix = cache_entry["matrix"]
            metas = cache_entry["metas"]

            sims = np.dot(matrix, v_selfie)
            strict_matches_by_photo = {}

            for idx, similarity in enumerate(sims):
                sim_val = float(similarity)
                m = metas[idx]
                pid = m["photo_id"]
                resolved_img = storage_service.resolve_image_url(m["image_url"], is_thumbnail=False)
                resolved_thumb = storage_service.resolve_image_url(m["thumbnail_url"] or m["image_url"], is_thumbnail=True)
                photo_key = os.path.basename(resolved_img).lower().strip() if resolved_img else pid

                if sim_val >= threshold:
                    if photo_key not in strict_matches_by_photo or sim_val > strict_matches_by_photo[photo_key]["similarity"]:
                        strict_matches_by_photo[photo_key] = {
                            "photo_id": pid,
                            "image_url": resolved_img,
                            "thumbnail_url": resolved_thumb,
                            "similarity": round(sim_val, 4),
                            "bounding_box": m["bounding_box"]
                        }

            sorted_matches = sorted(strict_matches_by_photo.values(), key=lambda x: x["similarity"], reverse=True)
            return sorted_matches

    def delete_photo(self, photo_id: str) -> bool:
        self.invalidate_event_cache()
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("face_embeddings").delete().eq("photo_id", photo_id).execute()
                self.supabase.table("photos").delete().eq("id", photo_id).execute()
                return True
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase delete_photo failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM face_embeddings WHERE photo_id = ?", (photo_id,))
            cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
            conn.commit()
            conn.close()
            return True

    def delete_photos_batch(self, photo_ids: List[str]) -> int:
        if not photo_ids:
            return 0
        self.invalidate_event_cache()

        if settings.DB_MODE == "supabase":
            try:
                for pid in photo_ids:
                    self.supabase.table("face_embeddings").delete().eq("photo_id", pid).execute()
                    self.supabase.table("photos").delete().eq("id", pid).execute()
                return len(photo_ids)
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase delete_photos_batch failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for pid in photo_ids:
                cursor.execute("DELETE FROM face_embeddings WHERE photo_id = ?", (pid,))
                cursor.execute("DELETE FROM photos WHERE id = ?", (pid,))
            conn.commit()
            conn.close()
            return len(photo_ids)

    def delete_event(self, event_id_or_code: str) -> bool:
        actual_id = self.resolve_event_id(event_id_or_code) or event_id_or_code
        self.invalidate_event_cache(actual_id)
        
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("face_embeddings").delete().eq("event_id", actual_id).execute()
                self.supabase.table("photos").delete().eq("event_id", actual_id).execute()
                self.supabase.table("person_clusters").delete().eq("event_id", actual_id).execute()
                self.supabase.table("share_tokens").delete().eq("event_id", actual_id).execute()
                self.supabase.table("audit_logs").delete().eq("event_id", actual_id).execute()
                self.supabase.table("event_settings").delete().eq("event_id", actual_id).execute()
                self.supabase.table("events").delete().eq("id", actual_id).execute()
                return True
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase delete_event failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM face_embeddings WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM photos WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM person_clusters WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM share_tokens WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM audit_logs WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM event_settings WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM events WHERE id = ? OR UPPER(event_code) = UPPER(?)", (actual_id, actual_id))
            conn.commit()
            conn.close()
            return True

    # --- PERSON CLUSTERS (Safe Fallback Methods) ---
    def get_clusters_for_event(self, event_id: str) -> List[Dict]:
        actual_id = self.resolve_event_id(event_id) or event_id
        if settings.DB_MODE == "supabase":
            try:
                res = self.supabase.table("person_clusters").select("*").eq("event_id", actual_id).execute()
                return res.data or []
            except Exception:
                return []
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM person_clusters WHERE event_id = ?", (actual_id,))
                rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception:
                return []

    def get_event_clusters(self, event_id: str) -> List[Dict]:
        return self.get_clusters_for_event(event_id)

    # --- SECURE TEMPORARY SHARING TOKENS ---
    def create_share_token(self, event_id: str, photo_ids: List[str], expiry_hours: int = 48) -> str:
        import secrets
        from datetime import timedelta
        token = secrets.token_urlsafe(32)
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=expiry_hours)
        actual_event_id = self.resolve_event_id(event_id) or event_id

        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("share_tokens").insert({
                    "token": token,
                    "event_id": actual_event_id,
                    "photo_ids_json": json.dumps(photo_ids),
                    "created_at": created_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "is_revoked": 0
                }).execute()
                return token
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase create_share_token failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO share_tokens (token, event_id, photo_ids_json, created_at, expires_at, is_revoked)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (token, actual_event_id, json.dumps(photo_ids), created_at.isoformat(), expires_at.isoformat()))
            conn.commit()
            conn.close()
            return token

    def get_share_token_photos(self, token: str) -> Optional[Dict]:
        if settings.DB_MODE == "supabase":
            try:
                res = self.supabase.table("share_tokens").select("*").eq("token", token).maybe_single().execute()
                if not res.data or res.data.get("is_revoked"):
                    return None
                
                row = res.data
                expires_at = datetime.fromisoformat(row["expires_at"])
                if datetime.now(timezone.utc) > expires_at:
                    return None

                ev_res = self.supabase.table("events").select("id, title, event_code").eq("id", row["event_id"]).maybe_single().execute()
                ev_row = ev_res.data

                photo_ids = json.loads(row["photo_ids_json"]) if isinstance(row["photo_ids_json"], str) else row["photo_ids_json"]
                
                photos = []
                for pid in photo_ids:
                    p_res = self.supabase.table("photos").select("id, image_url, thumbnail_url, created_at").eq("id", pid).maybe_single().execute()
                    if p_res.data:
                        photos.append(self._format_photo_record(p_res.data))

                return {
                    "token": token,
                    "event_id": row["event_id"],
                    "event_title": ev_row["title"] if ev_row else "Event Gallery",
                    "event_code": ev_row["event_code"] if ev_row else "",
                    "expires_at": row["expires_at"],
                    "photos": photos
                }
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase get_share_token_photos failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM share_tokens WHERE token = ?", (token,))
            row = cursor.fetchone()
            if not row or row["is_revoked"]:
                conn.close()
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                conn.close()
                return None

            cursor.execute("SELECT id, title, event_code FROM events WHERE id = ?", (row["event_id"],))
            ev_row = cursor.fetchone()

            photo_ids = json.loads(row["photo_ids_json"])
            photos = []
            for pid in photo_ids:
                cursor.execute("SELECT id, image_url, thumbnail_url, created_at FROM photos WHERE id = ?", (pid,))
                p = cursor.fetchone()
                if p:
                    photos.append(self._format_photo_record(dict(p)))

            conn.close()
            return {
                "token": token,
                "event_id": row["event_id"],
                "event_title": ev_row["title"] if ev_row else "Event Gallery",
                "event_code": ev_row["event_code"] if ev_row else "",
                "expires_at": row["expires_at"],
                "photos": photos
            }

    def revoke_share_token(self, token: str) -> bool:
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("share_tokens").update({"is_revoked": 1}).eq("token", token).execute()
                return True
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase revoke_share_token failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE share_tokens SET is_revoked = 1 WHERE token = ?", (token,))
            conn.commit()
            conn.close()
            return True

    # --- PRIVACY & BIOMETRIC DELETION ---
    def delete_event_biometrics(self, event_id: str) -> bool:
        actual_id = self.resolve_event_id(event_id) or event_id
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("face_embeddings").delete().eq("event_id", actual_id).execute()
                self.supabase.table("person_clusters").delete().eq("event_id", actual_id).execute()
                return True
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase delete_event_biometrics failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM face_embeddings WHERE event_id = ?", (actual_id,))
            cursor.execute("DELETE FROM person_clusters WHERE event_id = ?", (actual_id,))
            conn.commit()
            conn.close()
            return True

    # --- AUDIT LOGS ---
    def log_audit_action(self, event_id: Optional[str], action: str, details: Optional[Dict] = None):
        log_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        details_str = json.dumps(details or {})
        
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("audit_logs").insert({
                    "id": log_id,
                    "event_id": event_id,
                    "action": action,
                    "details_json": details_str,
                    "timestamp": ts
                }).execute()
            except Exception as e:
                print(f"[Audit Log Error] {e}")
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_logs (id, event_id, action, details_json, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (log_id, event_id, action, details_str, ts))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Audit Log Error] {e}")

    def get_audit_logs(self, event_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        if settings.DB_MODE == "supabase":
            try:
                q = self.supabase.table("audit_logs").select("*")
                if event_id:
                    q = q.eq("event_id", event_id)
                res = q.order("timestamp", desc=True).limit(limit).execute()
                
                logs = []
                for d in (res.data or []):
                    details_str = d.get("details_json")
                    d["details"] = json.loads(details_str) if isinstance(details_str, str) else details_str
                    logs.append(d)
                return logs
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase get_audit_logs failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if event_id:
                cursor.execute("""
                    SELECT * FROM audit_logs 
                    WHERE event_id = ? 
                    ORDER BY timestamp DESC LIMIT ?
                """, (event_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM audit_logs 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            logs = []
            for r in rows:
                d = dict(r)
                d["details"] = json.loads(d["details_json"]) if d.get("details_json") else {}
                logs.append(d)
            return logs

    # --- EVENT SETTINGS (PGRST116 Safe Fallback) ---
    def get_event_settings(self, event_id: str) -> Dict:
        actual_event_id = self.resolve_event_id(event_id) or event_id
        default_settings = {
            "event_id": actual_event_id,
            "similarity_threshold": 0.35,
            "retention_days": 90,
            "selfie_search_enabled": 1,
            "downloads_enabled": 1
        }
        if settings.DB_MODE == "supabase":
            try:
                res = self.supabase.table("event_settings").select("*").eq("event_id", actual_event_id).maybe_single().execute()
                if res.data:
                    return res.data
                return default_settings
            except Exception:
                return default_settings
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM event_settings WHERE event_id = ?", (actual_event_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return dict(row)
                return default_settings
            except Exception:
                return default_settings

    def update_event_settings(self, event_id: str, similarity_threshold: float, retention_days: int, selfie_search_enabled: bool, downloads_enabled: bool) -> Dict:
        actual_event_id = self.resolve_event_id(event_id) or event_id
        if settings.DB_MODE == "supabase":
            try:
                self.supabase.table("event_settings").upsert({
                    "event_id": actual_event_id,
                    "similarity_threshold": similarity_threshold,
                    "retention_days": retention_days,
                    "selfie_search_enabled": int(selfie_search_enabled),
                    "downloads_enabled": int(downloads_enabled)
                }).execute()
                return self.get_event_settings(actual_event_id)
            except Exception as e:
                raise RuntimeError(f"[Database Error] Supabase update_event_settings failed: {e}")
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO event_settings (event_id, similarity_threshold, retention_days, selfie_search_enabled, downloads_enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    similarity_threshold = excluded.similarity_threshold,
                    retention_days = excluded.retention_days,
                    selfie_search_enabled = excluded.selfie_search_enabled,
                    downloads_enabled = excluded.downloads_enabled
            """, (actual_event_id, similarity_threshold, retention_days, int(selfie_search_enabled), int(downloads_enabled)))
            conn.commit()
            conn.close()
            return self.get_event_settings(actual_event_id)

db_service = DatabaseService()