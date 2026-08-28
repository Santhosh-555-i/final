from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class EventCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Grand Wedding 2026"})
    event_code: Optional[str] = Field(None, json_schema_extra={"example": "WEDDING2026"})
    password: Optional[str] = Field(None, description="Optional passcode required to view/download photos", json_schema_extra={"example": "123456"})
    drive_link: Optional[str] = Field(None, description="Optional Google Drive folder or files link", json_schema_extra={"example": "https://drive.google.com/drive/folders/..."})

class EventOut(BaseModel):
    id: str
    title: str
    event_code: str
    created_at: str
    photo_count: int = 0
    is_protected: bool = False
    drive_link: Optional[str] = None

class VerifyPasswordRequest(BaseModel):
    event_code: str
    password: str

class VerifyPasswordResponse(BaseModel):
    success: bool
    message: str

class DriveImportRequest(BaseModel):
    event_id: str
    drive_link: str

class DriveImportResponse(BaseModel):
    success: bool
    imported_count: int
    total_faces: int
    message: str

class PhotoOut(BaseModel):
    id: str
    event_id: str
    image_url: str
    thumbnail_url: str
    created_at: str
    faces_detected: int = 0

class PhotoMatchResult(BaseModel):
    photo_id: str
    image_url: str
    thumbnail_url: str
    similarity: float
    bounding_box: Optional[Dict[str, float]] = None

class MatchResponse(BaseModel):
    count: int
    matches: List[PhotoMatchResult]
    message: str

class AdminLoginRequest(BaseModel):
    email: str = Field(..., json_schema_extra={"example": "admin@example.com"})
    password: Optional[str] = Field("admin123", json_schema_extra={"example": "admin123"})

class AdminLoginResponse(BaseModel):
    success: bool
    email: str
    role: str = "Super Admin"
    token: str
    message: str


