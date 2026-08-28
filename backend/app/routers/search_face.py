import base64
import io
import re
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query, Body, Request
from pydantic import BaseModel, Field

from app.schemas import MatchResponse, PhotoMatchResult
from app.database import db_service
from app.ml_engine import ml_engine
from app.config import settings

router = APIRouter(tags=["Facial Search & Matching"])

class SearchFaceJsonRequest(BaseModel):
    event_id: Optional[str] = Field(None, json_schema_extra={"example": "EVENT2026"})
    event_code: Optional[str] = Field(None, json_schema_extra={"example": "EVENT2026"})
    selfie_base64: Optional[str] = Field(None, description="Base64 encoded selfie image data")
    image_base64: Optional[str] = Field(None, description="Alias for selfie_base64")
    threshold: Optional[float] = Field(0.6, description="Cosine similarity threshold (default: 0.6)")

from starlette.concurrency import run_in_threadpool

@router.post("/search-face", response_model=MatchResponse)
async def search_face_api(
    request: Request,
    event_id: Optional[str] = Form(None),
    event_code: Optional[str] = Form(None),
    threshold: Optional[float] = Form(None),
    selfie: Optional[UploadFile] = File(None)
):
    """
    Core High-Performance Facial Search Endpoint.
    Accepts selfie as multipart/form-data OR application/json base64 payload.
    Uses multi-threaded worker threadpool to handle 50+ simultaneous users seamlessly.
    """
    content_type = request.headers.get("content-type", "")
    target_event = event_id or event_code
    target_threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD
    image_bytes = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            target_event = body.get("event_id") or body.get("event_code") or target_event
            if body.get("threshold") is not None:
                target_threshold = float(body.get("threshold"))
            
            b64_str = body.get("selfie_base64") or body.get("image_base64") or ""
            if b64_str:
                if "base64," in b64_str:
                    b64_str = b64_str.split("base64,")[1]
                image_bytes = base64.b64decode(b64_str)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")
    else:
        if selfie:
            image_bytes = await selfie.read()

    if not target_event:
        events = await run_in_threadpool(db_service.get_all_events)
        if events:
            target_event = events[0]["id"]
        else:
            raise HTTPException(status_code=400, detail="Missing required event_id or event_code.")

    if not image_bytes or len(image_bytes) < 100:
        raise HTTPException(status_code=400, detail="No selfie image data provided.")

    # 1. Non-blocking Multi-Threaded Face Detection & 512-d Vector Extraction
    selfie_vector = await run_in_threadpool(ml_engine.extract_single_selfie_embedding, image_bytes)
    if not selfie_vector:
        raise HTTPException(
            status_code=400,
            detail="No face detected in your selfie. Please ensure good lighting, face the camera directly, and try again."
        )

    # 2. Sub-millisecond Vector Matrix Similarity Search
    matches_raw = await run_in_threadpool(
        db_service.match_selfie_vector,
        event_id=target_event,
        selfie_vector=selfie_vector,
        threshold=target_threshold
    )

    matches = [PhotoMatchResult(**m) for m in matches_raw]
    count = len(matches)
    message = f"Found {count} matching photo(s) of you!" if count > 0 else "No photos matched your selfie in this event gallery."

    return MatchResponse(
        count=count,
        matches=matches,
        message=message
    )
