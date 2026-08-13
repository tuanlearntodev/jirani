from pydantic import BaseModel, ConfigDict

from app.schemas.tag_schema import TagRead


class Audio_Create(BaseModel):
    title: str
    description: str | None = None
    file_path: str  # no tags here — tags handled separately in router


class Audio_View(BaseModel):
    id: int
    title: str
    description: str | None = None
    audio_url: str
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)
