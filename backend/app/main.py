import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
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

class CachingStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        return response

# Mount local storage directory for static image serving with high-speed browser caching
if os.path.exists(settings.LOCAL_STORAGE_DIR):
    app.mount("/static", CachingStaticFiles(directory=settings.LOCAL_STORAGE_DIR), name="static")

# Include API Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(photos.router, prefix=settings.API_PREFIX)
app.include_router(admin_sync.router, prefix=settings.API_PREFIX)
app.include_router(search_face.router, prefix=settings.API_PREFIX)
app.include_router(clusters.router, prefix=settings.API_PREFIX)
app.include_router(sharing.router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "message": "Welcome to EventLens AI Facial Recognition & Photo Distribution API",
        "docs": "/docs",
        "health": "/api/health",
        "endpoints": {
            "admin_sync_drive": "/api/admin/sync-drive",
            "admin_index_faces": "/api/admin/index-faces",
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
        "supabase_configured": bool(settings.SUPABASE_URL)
    }
