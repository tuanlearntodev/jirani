import re
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.tag_schema import TagCreate, TagRead

T = TypeVar("T")


class BookBase(BaseModel):
    uid: str
    title: str
    author: str | None = None
    level: str | None = None
    book_type: str | None = None
    language: str | None = None
    extension: str
    tags: list[TagRead] = []
    cover_path: str | None = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    @computed_field
    @property
    def cover_url(self) -> str | None:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"


class BookCreate(BookBase):
    file_path: str
    cover_path: str | None = None
    tags: list[TagCreate] = []


class BookRead(BookBase):
    id: int
    created_at: datetime
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    level: str | None = None
    book_type: str | None = None
    language: str | None = None
    tags: list[TagCreate] | None = None
    metadata_: dict[str, Any] | None = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class BookUpload(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    author: str | None = Field(None, max_length=255)
    level: str | None = Field(None, max_length=50)
    book_type: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=50)
    tags: list[TagCreate] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = " ".join(v.split())
        if re.search(r'[<>:"/\\|?*]', v):
            raise ValueError("Title contains invalid characters")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[TagCreate]) -> list[TagCreate]:
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed per book")
        tag_names = [tag.name.lower() for tag in v]
        if len(tag_names) != len(set(tag_names)):
            raise ValueError("Duplicate tags are not allowed")
        return v


class BookSearchCriteria(BaseModel):
    q: str | None = None
    level: str | None = None
    book_type: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    extension: str | None = None
    metadata_: dict[str, Any] | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
