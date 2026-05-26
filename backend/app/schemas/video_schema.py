from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from app.schemas.tag_schema import TagRead, TagCreate

class Video_Create(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str

class Video_View(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    video_url: str
    tags: List[TagRead] = []
    model_config = ConfigDict(from_attributes=True)

class Video_Delete(BaseModel):
    title: str
    description: Optional[str] = None