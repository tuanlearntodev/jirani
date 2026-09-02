from pydantic import BaseModel, ConfigDict

from app.schemas.tag_schema import TagRead


class Video_Create(BaseModel):
    title: str
    description: str | None = None
    file_path: str


class Video_View(BaseModel):
    id: int
    title: str
    description: str | None = None
    video_url: str
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)


class Video_Delete(BaseModel):
    title: str
    description: str | None = None
