import base64
import io
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, status, Query
from pydantic import BaseModel, Field

from app.database import db_service
from app.drive_importer import drive_importer, task_tracker
from app.ml_engine import ml_engine
from app.storage import storage_service
from app.config import settings

# Dedicated background worker thread pool to keep FastAPI main event loop free (<50ms response)
sync_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="drive_sync_worker")

def _run_drive_sync_worker(target_event_id: str, drive_link: str, task_id: str):
    try:
        drive_importer.import_from_drive_link(
            target_event_id,
            drive_link,
            task_id
        )
    except Exception as e:
        task_tracker.update_task(task_id, status="failed", error=str(e))

router = APIRouter(prefix="/admin", tags=["Admin Drive & Indexing"])

class SyncDriveRequest(BaseModel):
    drive_link: str = Field(..., json_schema_extra={"example": "https://drive.google.com/drive/folders/1abcxyz..."})
    event_id: Optional[str] = None
    event_code: Optional[str] = None

class IndexFacesRequest(BaseModel):
    event_id: str
    force_reindex: Optional[bool] = False

class IndexFacesBatchRequest(BaseModel):
    event_id: str
    images_base64: List[str] = []

@router.post("/sync-drive", status_code=status.HTTP_202_ACCEPTED)
def sync_google_drive(req: SyncDriveRequest, background_tasks: BackgroundTasks):
    """
    Downloads Google Drive folder files using Google Drive API / public CDN stream
    and enqueues face detection and 512-d vector indexing in the background.
    Returns a tracking task_id for real-time progress monitoring.
    """
    target_event = None
    if req.event_id:
        target_event = db_service.get_event_by_id(req.event_id) or db_service.get_event_by_code(req.event_id)
    if not target_event and req.event_code:
        target_event = db_service.get_event_by_code(req.event_code) or db_service.get_event_by_id(req.event_code)

    if not target_event:
        events = db_service.get_all_events()
        if events:
            target_event = events[0]
        else:
            target_event = db_service.create_event(
                title="Event Gallery",
                event_code=req.event_code or "EVENT2026",
                drive_link=req.drive_link
            )

    target_event_id = target_event["id"]

    # Create tracking task
    task_id = task_tracker.create_task(target_event_id)

    # Launch in non-blocking dedicated threadpool worker
    sync_executor.submit(_run_drive_sync_worker, target_event_id, req.drive_link.strip(), task_id)

    db_service.log_audit_action(target_event_id, "ADMIN_SYNC_DRIVE_STARTED", {
        "task_id": task_id,
        "drive_link": req.drive_link
    })

    return {
        "success": True,
        "task_id": task_id,
        "event_id": target_event_id,
        "status": "started",
        "message": "Google Drive download and face indexing task started in the background."
    }

@router.post("/index-faces")
def index_faces(req: IndexFacesRequest):
    """
    Runs face detection, extracts 512-d FaceNet embeddings for all photos in an event,
    and writes the vector embeddings to public.face_embeddings.
    """
    event = db_service.get_event_by_id(req.event_id)
    if not event:
        ev_code = db_service.get_event_by_code(req.event_id)
        if ev_code:
            event = ev_code
        else:
            raise HTTPException(status_code=404, detail="Event not found.")

    res = db_service.backfill_missing_embeddings(event_id=event["id"])

    db_service.log_audit_action(event["id"], "ADMIN_INDEX_FACES", {
        "photos_processed": res.get("photos_processed", 0),
        "faces_detected": res.get("faces_detected", 0)
    })

    return {
        "success": True,
        "event_id": event["id"],
        "total_scanned": res.get("total_scanned", 0),
        "photos_processed": res.get("photos_processed", 0),
        "faces_detected": res.get("faces_detected", 0),
        "embeddings_created": res.get("embeddings_created", 0),
        "photos_skipped": res.get("photos_skipped", 0),
        "message": f"Successfully processed {res.get('photos_processed', 0)} photos and created {res.get('embeddings_created', 0)} face embeddings."
    }

@router.post("/backfill-embeddings")
def backfill_all_embeddings(event_id: Optional[str] = Query(None)):
    """
    Scans all photos across all events (or single event) with 0 embeddings
    and generates 512-d FaceNet embeddings in the database.
    """
    res = db_service.backfill_missing_embeddings(event_id=event_id)
    return {
        "success": True,
        "summary": res,
        "message": f"Backfill complete: {res.get('embeddings_created', 0)} embeddings created across {res.get('photos_processed', 0)} photos."
    }

@router.get("/sync-status/{task_id}")
def get_sync_status(task_id: str):
    """
    Returns real-time progress indicator for Google Drive sync & photo indexing
    (e.g., 'Indexing 45/200 photos...').
    """
    task = task_tracker.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task

@router.get("/stats/{event_id}")
def get_event_stats(event_id: str):
    """
    Returns aggregate event statistics: total photos, total unique faces detected, clusters, etc.
    """
    event = db_service.get_event_by_id(event_id)
    if not event:
        ev_code = db_service.get_event_by_code(event_id)
        if ev_code:
            event = ev_code
            event_id = ev_code["id"]
        else:
            raise HTTPException(status_code=404, detail="Event not found.")

    photos = db_service.get_event_photos(event_id, limit=1000)
    clusters = db_service.get_event_clusters(event_id) if hasattr(db_service, "get_event_clusters") else []

    total_faces = 0
    # Query total faces from the correct DB backend
    try:
        if settings.DB_MODE == "supabase":
            fe_res = db_service.supabase.table("face_embeddings").select("id", count="exact").eq("event_id", event_id).execute()
            total_faces = fe_res.count if fe_res.count is not None else len(fe_res.data or [])
        else:
            import sqlite3
            conn = sqlite3.connect(db_service.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM face_embeddings WHERE event_id = ?", (event_id,))
            total_faces = cursor.fetchone()[0]
            conn.close()
    except Exception:
        total_faces = len(photos)

    return {
        "event_id": event_id,
        "event_code": event.get("event_code"),
        "title": event.get("title"),
        "total_photos": len(photos),
        "total_faces_detected": total_faces,
        "total_clusters": len(clusters),
        "is_protected": event.get("is_protected", False),
        "drive_link": event.get("drive_link")
    }
