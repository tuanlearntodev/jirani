from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Set

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App metadata
    APP_NAME: str = "Jirani Offline Library"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Offline library management system"
    
    # App settings
    DEBUG: bool = True
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./data/jirani_library.db"
    
    # Security settings
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS settings
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    
    # File upload settings
    UPLOAD_DIR: Path = BASE_DIR / "uploads" / "books"
    COVER_DIR: Path = BASE_DIR / "uploads" / "covers"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_COVER_SIZE: int = 5 * 1024 * 1024  # 5MB

    @property
    def ALLOWED_EXTENSIONS(self) -> Set[str]:
        return {"pdf", "epub"}
    
    @property
    def ALLOWED_IMAGE_EXTENSIONS(self) -> Set[str]:
        return {"jpg", "jpeg", "png", "webp"}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()