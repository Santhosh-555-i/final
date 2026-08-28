import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict
from app.database import db_service
from app.config import settings

class SyncTaskTracker:
    def __init__(self):
        # In-memory fast cache for real-time live polling
        self._memory_tasks: Dict[str, Dict] = {}

    def create_task(self, event_id: str) -> str:
        task_id = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        
        task_record = {
            "task_id": task_id,
            "event_id": event_id,
            "status": "pending",
            "total": 0,
            "current": 0,
            "faces_detected": 0,
            "progress_message": "Task queued...",
            "error": None,
            "created_at": now_str,
            "updated_at": now_str
        }
        self._memory_tasks[task_id] = task_record

        if settings.DB_MODE == "supabase":
            try:
                db_service.supabase.table("sync_jobs").insert({
                    "id": task_id,
                    "status": "pending",
                    "total_files": 0,
                    "processed_files": 0,
                    "created_at": now_str,
                    "updated_at": now_str
                }).execute()
            except Exception as e:
                print(f"[SyncTaskTracker Error] Supabase insert failed: {e}")
        else:
            try:
                conn = sqlite3.connect(db_service.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_jobs (id, status, total_files, processed_files, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (task_id, "pending", 0, 0, now_str, now_str))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[SyncTaskTracker Error] SQLite insert failed: {e}")

        return task_id

    def update_task(self, task_id: str, **kwargs):
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Update in-memory record first
        if task_id in self._memory_tasks:
            rec = self._memory_tasks[task_id]
            rec["updated_at"] = now_str
            if "status" in kwargs:
                rec["status"] = kwargs["status"]
            if "total" in kwargs:
                rec["total"] = kwargs["total"]
            if "current" in kwargs:
                rec["current"] = kwargs["current"]
            if "faces_detected" in kwargs:
                rec["faces_detected"] = kwargs["faces_detected"]
            if "progress_message" in kwargs:
                rec["progress_message"] = kwargs["progress_message"]
            if "error" in kwargs:
                rec["error"] = str(kwargs["error"])
        else:
            self._memory_tasks[task_id] = {
                "task_id": task_id,
                "status": kwargs.get("status", "in_progress"),
                "total": kwargs.get("total", 0),
                "current": kwargs.get("current", 0),
                "faces_detected": kwargs.get("faces_detected", 0),
                "progress_message": kwargs.get("progress_message", ""),
                "error": str(kwargs["error"]) if "error" in kwargs else None,
                "created_at": now_str,
                "updated_at": now_str
            }

        # Sync with database
        update_data = {"updated_at": now_str}
        if "status" in kwargs:
            update_data["status"] = kwargs["status"]
        if "total" in kwargs:
            update_data["total_files"] = kwargs["total"]
        if "current" in kwargs:
            update_data["processed_files"] = kwargs["current"]
        if "error" in kwargs:
            update_data["error"] = str(kwargs["error"])

        if settings.DB_MODE == "supabase":
            try:
                db_service.supabase.table("sync_jobs").update(update_data).eq("id", task_id).execute()
            except Exception as e:
                print(f"[SyncTaskTracker Error] Supabase update failed: {e}")
        else:
            try:
                conn = sqlite3.connect(db_service.db_path)
                cursor = conn.cursor()
                set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
                values = list(update_data.values()) + [task_id]
                cursor.execute(f"UPDATE sync_jobs SET {set_clause} WHERE id = ?", tuple(values))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[SyncTaskTracker Error] SQLite update failed: {e}")

    def get_task(self, task_id: str) -> Optional[Dict]:
        # Fast memory lookup
        if task_id in self._memory_tasks:
            return self._memory_tasks[task_id]

        if settings.DB_MODE == "supabase":
            try:
                res = db_service.supabase.table("sync_jobs").select("*").eq("id", task_id).single().execute()
                if res.data:
                    d = res.data
                    return {
                        "task_id": d["id"],
                        "status": d.get("status", "unknown"),
                        "total": d.get("total_files", 0),
                        "current": d.get("processed_files", 0),
                        "faces_detected": d.get("faces_detected", 0),
                        "progress_message": f"Processing {d.get('processed_files', 0)}/{d.get('total_files', 0)} files...",
                        "error": d.get("error"),
                        "created_at": d.get("created_at"),
                        "updated_at": d.get("updated_at")
                    }
            except Exception:
                return None
        else:
            try:
                conn = sqlite3.connect(db_service.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sync_jobs WHERE id = ?", (task_id,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return {
                        "task_id": row["id"],
                        "status": row["status"],
                        "total": row["total_files"],
                        "current": row["processed_files"],
                        "faces_detected": 0,
                        "progress_message": f"Processing {row['processed_files']}/{row['total_files']} files...",
                        "error": row["error"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"]
                    }
            except Exception:
                return None
        return None

task_tracker = SyncTaskTracker()
