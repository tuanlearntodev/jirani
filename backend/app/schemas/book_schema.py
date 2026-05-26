from pydantic import BaseModel, ConfigDict, field_validator, Field, computed_field
from typing import List, Optional
from app.schemas.tag_schema import TagRead, TagCreate
import re

class BookBase(BaseModel):
    title: str
    uid: str
    file_type: str
    extension: str
    tags: List[TagRead] = []
    cover_path: Optional[str] = Field(None)    
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    @computed_field
    @property
    def cover_url(self) -> Optional[str]:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"

class BookCreate(BookBase):
    # These are only used internally by the Service/Repo 
    # after the file is saved to the disk.
    file_path: str 
    tags: List[TagCreate] = []

class BookRead(BookBase):
    cover_path: Optional[str] = Field(None) 
    @computed_field
    @property
    def cover_url(self) -> Optional[str]:
        if not self.cover_path:
            return None
        # This builds the public URL that uses the 'static' bridge
        return f"/static/covers/{self.cover_path}"

class BookDetail(BookRead):
    tags: List[TagRead] = []
    
class BookUpload(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    tags: List[TagCreate] = Field(default_factory=list, max_length=20)
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None # Return None so the Service knows to use the filename
        
        # Clean up existing title
        v = ' '.join(v.split())
        
        # Check for invalid characters (Keep this for security!)
        if re.search(r'[<>:"/\\|?*]', v):
            raise ValueError('Title contains invalid characters')
        
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[TagCreate]) -> List[TagCreate]:
        """Validate tags list"""
        if len(v) > 20:
            raise ValueError('Maximum 20 tags allowed per book')
        
        # Check for duplicate tag names
        tag_names = [tag.name.lower() for tag in v]
        if len(tag_names) != len(set(tag_names)):
            raise ValueError('Duplicate tags are not allowed')
        
        return v
    

    