from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Set
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SECRET_FILE = DATA_DIR / ".secret"

def get_secret_key() -> str:
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    key = secrets.token_urlsafe(32)
    SECRET_FILE.write_text(key)
    return key

class Settings(BaseSettings):
    # App metadata
    APP_NAME: str = "Jirani Offline Library"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Offline library management system"
    
    # App settings
    DEBUG: bool = True
    
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/jirani_library"
    
    # Security settings
    SECRET_KEY: str = get_secret_key()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # File upload settings
    DATA_DIR: Path = BASE_DIR / "data"
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
        case_sensitive=True
    )
    
    def __init__(self, **kwargs):
      super().__init__(**kwargs)
      if not self.SECRET_KEY:
          self.SECRET_KEY = get_secret_key()


settings = Settings()