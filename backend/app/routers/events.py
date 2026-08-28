from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from typing import List, Optional
from app.schemas import (
    EventCreate, EventOut, VerifyPasswordRequest, 
    VerifyPasswordResponse, DriveImportRequest, DriveImportResponse, PhotoOut
)
from app.database import db_service
from app.drive_importer import drive_importer
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("/create", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(event_in: EventCreate, background_tasks: BackgroundTasks, admin_email: str = Depends(get_current_admin)):
    """
    Creates a new event record with optional password protection and Google Drive link.
    """
    if event_in.event_code:
        existing = db_service.get_event_by_code(event_in.event_code)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Event code '{event_in.event_code}' already exists. Please choose a different code."
            )
            
    created = db_service.create_event(
        title=event_in.title,
        event_code=event_in.event_code,
        password=event_in.password,
        drive_link=event_in.drive_link
    )

    # If drive link is specified, trigger drive import in background
    if event_in.drive_link and event_in.drive_link.strip():
        background_tasks.add_task(drive_importer.import_from_drive_link, created["id"], event_in.drive_link.strip())

    return created

@router.post("/verify-password", response_model=VerifyPasswordResponse)
def verify_password(req: VerifyPasswordRequest):
    """
    Verifies attendee access password for protected events.
    """
    event = db_service.get_event_by_code(req.event_code)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    if not event.get("is_protected"):
        return VerifyPasswordResponse(success=True, message="Event is public and does not require a password.")

    is_valid = db_service.verify_event_password(req.event_code, req.password)
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Incorrect event password. Please check and try again."
        )

    return VerifyPasswordResponse(success=True, message="Event access unlocked successfully.")

@router.post("/import-drive", response_model=DriveImportResponse)
def import_google_drive(req: DriveImportRequest, admin_email: str = Depends(get_current_admin)):
    """
    Imports all images from a Google Drive folder/files link, generates embeddings, and saves to event gallery.
    """
    event = db_service.get_event_by_id(req.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Target event not found.")

    res = drive_importer.import_from_drive_link(req.event_id, req.drive_link)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Failed to import from Google Drive."))

    return DriveImportResponse(**res)

@router.get("", response_model=List[EventOut])
def list_events():
    """
    Lists all public active events.
    """
    return db_service.get_all_events()

@router.get("/{code}", response_model=EventOut)
def get_event(code: str):
    """
    Retrieves event details by event_code.
    """
    event = db_service.get_event_by_code(code)
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Event with code '{code}' not found."
        )
    return event

@router.get("/{code}/photos", response_model=List[PhotoOut])
def get_event_photos(code: str, limit: int = 100, offset: int = 0):
    """
    Retrieves all photos for the event gallery.
    """
    event = db_service.get_event_by_code(code)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    
    photos = db_service.get_event_photos(event["id"], limit=limit, offset=offset)
    return photos

@router.delete("/{event_id_or_code}")
def delete_event(event_id_or_code: str, admin_email: str = Depends(get_current_admin)):
    """
    Permanently deletes an event, all its photos, face embeddings, clusters, and data.
    """
    success = db_service.delete_event(event_id_or_code)
    return {"success": success, "message": f"Event '{event_id_or_code}' and all associated photos/embeddings were deleted successfully."}

