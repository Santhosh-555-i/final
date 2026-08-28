import uuid
from datetime import datetime
from typing import Optional, Dict
from app.database import db_service
from app.config import settings
import sqlite3

class SyncTaskTracker:
    def create_task(self, event_id: str) -> str:
        task_id = str(uuid.uuid4())
        now_str = datetime.utcnow().isoformat()
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
            conn = sqlite3.connect(db_service.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_jobs (id, status, total_files, processed_files, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, "pending", 0, 0, now_str, now_str))
            conn.commit()
            conn.close()
        return task_id

    def update_task(self, task_id: str, **kwargs):
        now_str = datetime.utcnow().isoformat()
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
            conn = sqlite3.connect(db_service.db_path)
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [task_id]
            cursor.execute(f"UPDATE sync_jobs SET {set_clause} WHERE id = ?", tuple(values))
            conn.commit()
            conn.close()

    def get_task(self, task_id: str) -> Optional[Dict]:
        if settings.DB_MODE == "supabase":
            try:
                res = db_service.supabase.table("sync_jobs").select("*").eq("id", task_id).single().execute()
                if res.data:
                    d = res.data
                    return {
                        "task_id": d["id"],
                        "status": d["status"],
                        "total": d["total_files"],
                        "current": d["processed_files"],
                        "error": d["error"],
                        "created_at": d["created_at"]
                    }
            except Exception:
                return None
        else:
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
                    "error": row["error"],
                    "created_at": row["created_at"]
                }
        return None

task_tracker = SyncTaskTracker()
