import os
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.storage import storage_service
from app.routers import events, photos, auth, clusters, sharing, admin_sync, search_face

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for Vercel frontends, localhost, Railway, Render, and configured origins
cors_origins = list(dict.fromkeys(
    settings.CORS_ORIGINS + [
        "https://photo-lake-six.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.up\.railway\.app|https://.*\.onrender\.com|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

from fastapi.middleware.gzip import GZipMiddleware

# Configure High-Speed GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=800)

# Legacy /static route fallback to ensure zero 404s for old database paths
@app.get("/static/raw/{filename:path}")
@app.get("/static/thumbnails/{filename:path}")
@app.get("/static/{folder}/{filename:path}")
async def serve_static_or_supabase_fallback(filename: str, folder: str = "raw"):
    clean_name = storage_service.extract_clean_filename(filename)
    sub = "thumbnails" if (folder == "thumbnails" or clean_name.startswith("thumb_")) else "raw"
    
    # 1. Local filesystem check
    local_path = os.path.join(settings.LOCAL_STORAGE_DIR, sub, clean_name)
    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800, immutable"}
            )
        except Exception:
            pass

    # 2. Supabase storage fallback
    photo_bytes = storage_service.get_photo_bytes(clean_name)
    if photo_bytes:
        return Response(
            content=photo_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800, immutable"}
        )

    raise HTTPException(status_code=404, detail=f"Image {clean_name} not found")

# Mount local storage directory for static image serving when available
if os.path.exists(settings.LOCAL_STORAGE_DIR):
    app.mount("/static", StaticFiles(directory=settings.LOCAL_STORAGE_DIR), name="static")

# Include API Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(photos.router, prefix=settings.API_PREFIX)
app.include_router(admin_sync.router, prefix=settings.API_PREFIX)
app.include_router(search_face.router, prefix=settings.API_PREFIX)
app.include_router(clusters.router, prefix=settings.API_PREFIX)
app.include_router(sharing.router, prefix=settings.API_PREFIX)

@app.on_event("startup")
async def on_startup_auto_backfill():
    """
    Spawns background task on startup to scan photos with missing embeddings
    and automatically index them without blocking the server.
    """
    import threading
    import time
    from app.database import db_service

    def _run_backfill():
        time.sleep(3)  # Wait for server to bind ports
        try:
            print("[Startup] Triggering automatic face embedding verification & backfill...")
            db_service.backfill_missing_embeddings()
        except Exception as e:
            print(f"[Startup Backfill Notice] {e}")

    threading.Thread(target=_run_backfill, daemon=True, name="startup_face_backfill").start()

@app.get("/")
def root():
    return {
        "message": "Welcome to EventLens AI Facial Recognition & Photo Distribution API",
        "docs": "/docs",
        "health": "/api/health",
        "endpoints": {
            "admin_sync_drive": "/api/admin/sync-drive",
            "admin_index_faces": "/api/admin/index-faces",
            "admin_backfill_embeddings": "/api/admin/backfill-embeddings",
            "search_face": "/api/search-face",
            "events": "/api/events",
            "photos": "/api/photos/upload-batch"
        }
    }

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "supabase_configured": bool(settings.SUPABASE_URL),
        "db_mode": settings.DB_MODE
    }
