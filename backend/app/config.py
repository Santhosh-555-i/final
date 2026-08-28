import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "EventLens AI API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # CORS
    @property
    def CORS_ORIGINS(self) -> List[str]:
        env_origins = os.getenv("CORS_ORIGINS", "")
        if env_origins:
            return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
        return [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "*"
        ]
    
    # Supabase / Database
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Local Storage fallback directory
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE_DIR: str = os.path.join(BASE_DIR, "storage_data")
    
    # Vector Search Threshold (FaceNet VGGFace2 Standard: 0.68 for zero-false-positive identity verification)
    SIMILARITY_THRESHOLD: float = 0.68

    # Admin Authentication
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "santosh2005th@gmail.com")
    ALLOWED_ADMIN_EMAILS: List[str] = [
        "santosh2005th@gmail.com",
        "satosh2005th@gmail.com"
    ]
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "element2018")

settings = Settings()

os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "raw"), exist_ok=True)
os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails"), exist_ok=True)
