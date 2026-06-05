from pydantic import BaseModel, Field
from app.models import RoleEnum
from datetime import datetime

class AccountBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=50)
    
class AccountCreate(AccountBase):
    role: RoleEnum
    
class AccountRead(AccountBase):
    model_config = {"from_attributes":True}
    id: int
    role: RoleEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
class CreateUserResponse(AccountRead):
    credentials: str | None = None

class BulkCreateRequest(BaseModel):
    count: int = Field(..., ge=1, le=100)
    role: RoleEnum
    prefix: str = Field(default="student", min_length=1, max_length=20)
    first_name: str = Field(default="Student", min_length=1, max_length=50)
    last_name: str = Field(default="Account", min_length=1, max_length=50)

class BulkCredentialItem(BaseModel):
    username: str
    password: str
    role: RoleEnum

class BulkCreateResponse(BaseModel):
    created: int
    accounts: list[BulkCredentialItem]