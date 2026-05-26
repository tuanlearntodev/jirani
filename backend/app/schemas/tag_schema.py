from pydantic import BaseModel, ConfigDict, field_validator, Field
import re

class TagBase(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
    
class TagRead(TagBase):
    id: int
  
class TagCreate(TagBase):
    name: str = Field(..., min_length=1, max_length=50)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate tag name"""
        if not v or not v.strip():
            raise ValueError('Tag name cannot be empty or whitespace only')
        
        # Remove extra whitespace
        v = ' '.join(v.split())
        
        # Check length after stripping
        if len(v) < 1 or len(v) > 50:
            raise ValueError('Tag name must be between 1 and 50 characters')
        
        # Check for invalid characters (allow letters, numbers, spaces, hyphens, underscores)
        if not re.match(r'^[\w\s-]+$', v):
            raise ValueError('Tag name can only contain letters, numbers, spaces, hyphens, and underscores')
        
        return v