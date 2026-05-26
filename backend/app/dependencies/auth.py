# app/dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.account import Account
from app.services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Account:

    token = credentials.credentials  
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="couldn't validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
    
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")  
        
        if username is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
   
    user = AuthService.get_user_by_username(db, username)
    
    if user is None:
        raise credentials_exception
        
    return user


class RoleChecker:
    
    def __init__ (self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Account = Depends(get_current_user)):
        user_roles=[]
        for role in current_user.roles:
            user_roles.append(role.name)
        
        has_permission = False

        for role in user_roles:
            if role in self.allowed_roles:
                has_permission = True
                break
        
        if not has_permission:
            raise HTTPException(status_code=403)
    
        return current_user