from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from app.schemas.tag_schema import TagRead

class Audio_Create(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str  # no tags here — tags handled separately in router

class Audio_View(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    audio_url: str
    tags: List[TagRead] = []
    model_config = ConfigDict(from_attributes=True)