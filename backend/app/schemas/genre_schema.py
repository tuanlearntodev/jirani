from pydantic import BaseModel, ConfigDict, Field


class GenreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class GenreRead(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
