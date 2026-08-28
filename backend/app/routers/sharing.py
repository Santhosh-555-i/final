from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.database import db_service
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/sharing", tags=["Temporary Sharing & Privacy"])

class CreateShareLinkRequest(BaseModel):
    event_id: str
    photo_ids: List[str]
    expiry_hours: Optional[int] = 48

class UpdateSettingsRequest(BaseModel):
    similarity_threshold: float
    retention_days: int
    selfie_search_enabled: bool
    downloads_enabled: bool

@router.post("/create")
def create_share_link(req: CreateShareLinkRequest):
    """
    Generates a secure temporary sharing token without exposing raw biometric data.
    """
    if not req.photo_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one photo ID")
    token = db_service.create_share_token(req.event_id, req.photo_ids, req.expiry_hours or 48)
    db_service.log_audit_action(req.event_id, "CREATE_SHARE_LINK", {"photo_count": len(req.photo_ids), "expiry_hours": req.expiry_hours})
    return {
        "success": True,
        "token": token,
        "share_url": f"/my-photos/{token}",
        "expires_in_hours": req.expiry_hours or 48
    }

@router.get("/{token}")
def get_shared_photos(token: str):
    """
    Retrieves photos associated with a valid temporary share token.
    """
    data = db_service.get_share_token_photos(token)
    if not data:
        raise HTTPException(status_code=404, detail="This sharing link is invalid, expired, or has been revoked.")
    return data

@router.delete("/{token}")
def revoke_share_link(token: str, admin_email: str = Depends(get_current_admin)):
    """
    Revokes a temporary sharing token immediately.
    """
    success = db_service.revoke_share_token(token)
    db_service.log_audit_action(None, "REVOKE_SHARE_LINK", {"token_prefix": token[:8]})
    return {"success": success, "message": "Share link revoked successfully."}

@router.delete("/event/{event_id}/biometrics")
def delete_event_biometrics(event_id: str, admin_email: str = Depends(get_current_admin)):
    """
    Deletes all biometric face vectors for an event (GDPR / Privacy Compliance).
    """
    success = db_service.delete_event_biometrics(event_id)
    db_service.log_audit_action(event_id, "DELETE_EVENT_BIOMETRICS", {"event_id": event_id})
    return {"success": success, "message": "All biometric face vectors for this event have been permanently deleted."}

@router.get("/audit-logs/{event_id}")
def get_audit_logs(event_id: str, limit: int = 50, admin_email: str = Depends(get_current_admin)):
    """
    Returns audit logs for an event.
    """
    logs = db_service.get_audit_logs(event_id, limit=limit)
    return {"success": True, "logs": logs}

@router.get("/settings/{event_id}")
def get_event_settings(event_id: str):
    """
    Returns custom privacy & search settings for an event.
    """
    return db_service.get_event_settings(event_id)

@router.post("/settings/{event_id}")
def update_event_settings(event_id: str, req: UpdateSettingsRequest, admin_email: str = Depends(get_current_admin)):
    """
    Updates event privacy, search, and retention settings.
    """
    res = db_service.update_event_settings(
        event_id,
        req.similarity_threshold,
        req.retention_days,
        req.selfie_search_enabled,
        req.downloads_enabled
    )
    db_service.log_audit_action(event_id, "UPDATE_SETTINGS", req.model_dump())
    return {"success": True, "settings": res}
