import io
import zipfile
import requests
import os
import tempfile
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Response, Depends
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from app.schemas import PhotoOut, MatchResponse, PhotoMatchResult
from app.database import db_service
from app.storage import storage_service
from app.ml_engine import ml_engine
from app.config import settings
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/photos", tags=["Photos"])

@router.post("/upload-batch", response_model=List[PhotoOut], status_code=status.HTTP_201_CREATED)
async def upload_photos_batch(
    event_id: str = Form(...),
    files: List[UploadFile] = File(...),
    admin_email: str = Depends(get_current_admin)
):
    """
    Accepts bulk event photos + event_id.
    Processes each photo: saves raw & thumbnail, detects all faces, extracts 512-d vector embeddings,
    and indexes them in database.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No photo files uploaded.")

    processed_photos = []

    for file in files:
        try:
            content = await file.read()
            if not content or len(content) < 100:
                continue

            # 1. Save raw image & thumbnail
            image_url, thumbnail_url = storage_service.save_photo_and_thumbnail(content, file.filename or "photo.jpg")

            # 2. Extract faces and 512-d embeddings
            faces = ml_engine.extract_faces_and_embeddings(content)

            # 3. Store in DB
            photo_record = db_service.insert_photo_and_embeddings(
                event_id=event_id,
                image_url=image_url,
                thumbnail_url=thumbnail_url,
                faces=faces
            )
            processed_photos.append(photo_record)

        except Exception as e:
            print(f"[Upload Error] Failed to process photo {file.filename}: {e}")

    return processed_photos


@router.post("/match", response_model=MatchResponse)
async def match_attendee_selfie(
    event_id: str = Form(...),
    selfie: UploadFile = File(...)
):
    """
    Accepts selfie image + event_id.
    Extracts 512-d embedding in-memory, DOES NOT save selfie to disk or DB,
    and performs Cosine Similarity Vector Search in database.
    """
    content = await selfie.read()
    if not content or len(content) < 100:
        raise HTTPException(status_code=400, detail="Invalid image file provided.")

    # Extract 512-d embedding from selfie
    selfie_vector = ml_engine.extract_single_selfie_embedding(content)
    if not selfie_vector:
        raise HTTPException(
            status_code=400,
            detail="No face detected in your selfie. Please ensure good lighting, face the camera directly, and try again."
        )

    # Perform vector similarity search
    matches_raw = db_service.match_selfie_vector(
        event_id=event_id,
        selfie_vector=selfie_vector,
        threshold=settings.SIMILARITY_THRESHOLD
    )

    matches = [PhotoMatchResult(**m) for m in matches_raw]

    message = f"Found {len(matches)} matching photo(s) of you!" if matches else "No photos matched your selfie in this event gallery."
    return MatchResponse(
        count=len(matches),
        matches=matches,
        message=message
    )


@router.post("/download-zip")
async def download_photos_zip(
    photo_urls: List[str]
):
    """
    Downloads photos and streams a .zip archive without holding it entirely in RAM.
    """
    if not photo_urls:
        raise HTTPException(status_code=400, detail="No photo URLs provided for download.")
    
    if len(photo_urls) > 500:
        raise HTTPException(status_code=400, detail="Too many photos requested. Max 500.")

    # Use SpooledTemporaryFile to spill to disk if > 10MB
    zip_buffer = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, url in enumerate(photo_urls, 1):
            try:
                if url.startswith("/static/"):
                    # Local storage file path
                    rel_path = url.replace("/static/", "")
                    full_path = os.path.join(settings.LOCAL_STORAGE_DIR, rel_path)
                    if os.path.exists(full_path):
                        with open(full_path, "rb") as f:
                            zf.writestr(f"event_photo_{idx}.jpg", f.read())
                else:
                    # Remote HTTP URL
                    resp = requests.get(url, timeout=10, stream=True)
                    if resp.status_code == 200:
                        zf.writestr(f"event_photo_{idx}.jpg", resp.content)
            except Exception as e:
                print(f"[ZIP Download Error] Failed to include photo {url}: {e}")

    zip_buffer.seek(0)
    
    def file_iterator():
        try:
            while True:
                chunk = zip_buffer.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            zip_buffer.close()
            
    return StreamingResponse(
        file_iterator(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=EventLens_My_Photos.zip"}
    )

class DeleteBatchRequest(BaseModel):
    photo_ids: List[str]

@router.delete("/{photo_id}")
def delete_photo(photo_id: str, admin_email: str = Depends(get_current_admin)):
    """
    Deletes a photo and its associated face embeddings.
    """
    success = db_service.delete_photo(photo_id)
    return {"success": success, "message": f"Photo {photo_id} deleted successfully."}

@router.post("/delete-batch")
def delete_photos_batch(req: DeleteBatchRequest, admin_email: str = Depends(get_current_admin)):
    """
    Deletes a batch of photos and their associated face embeddings in bulk.
    """
    count = db_service.delete_photos_batch(req.photo_ids)
    return {"success": True, "count": count, "message": f"Successfully deleted {count} photo(s)."}
