from pydantic import BaseModel, Field
from typing import List, Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class SignUpRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: str = Field(..., min_length=15)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
   

class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str = Field(..., min_length=15)

class ChangePasswordRequest(BaseModel):
    username: str
    new_password: str = Field(..., min_length=15)
    old_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    roles: List[str]
    recovery_code: Optional[str] = None  

class RoleSchema(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class UserWithRoles(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    is_active: bool
    roles: List[RoleSchema]
    class Config:
        from_attributes = True