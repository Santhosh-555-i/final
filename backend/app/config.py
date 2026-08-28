import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "EventLens AI API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # DB Mode
    DB_MODE: str = os.getenv("DB_MODE", "sqlite")
    
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
        ]
    
    # Supabase / Database
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    
    # Local Storage fallback directory (Only for local/sqlite)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE_DIR: str = os.path.join(BASE_DIR, "storage_data")
    
    # Vector Search Threshold
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.68"))

    # Admin Authentication
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_JWT_SECRET: str = os.getenv("ADMIN_JWT_SECRET", "") or os.getenv("JWT_SECRET", "")
    
    def validate_production(self):
        if self.DB_MODE == "supabase":
            if not self.SUPABASE_URL or not self.SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in supabase mode.")
            if not self.ADMIN_EMAIL or not self.ADMIN_PASSWORD or not self.ADMIN_JWT_SECRET:
                raise ValueError("ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_JWT_SECRET must be set in production mode.")
        elif self.DB_MODE == "sqlite":
            if not self.ADMIN_EMAIL:
                self.ADMIN_EMAIL = "admin@example.com"
            if not self.ADMIN_PASSWORD:
                self.ADMIN_PASSWORD = "admin"
            if not self.ADMIN_JWT_SECRET:
                self.ADMIN_JWT_SECRET = "local-dev-secret-do-not-use-in-prod"

settings = Settings()
settings.validate_production()

if settings.DB_MODE == "sqlite":
    os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "raw"), exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails"), exist_ok=True)
