from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.config import settings
from app.models import Account, RoleEnum
from app.schemas import AccountCreate
from app.repositories import AuthRepo
import random

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_MINUTES = 120

class AuthService:
    def __init__(self, auth_repo: AuthRepo):
        self.auth_repo = auth_repo

    @staticmethod
    def generate_student_password() -> str:
        return str(random.randint(100000, 999999))
    
    @staticmethod
    def validate_credentials(role: RoleEnum, password:str, context: str = "create") -> None:
        if context == "create" and role == RoleEnum.student:
            pass
        elif context == "self_change" and role == RoleEnum.student:
            if not password.isdigit() or len(password) < 4:
                raise ValueError("Password must be a 4-digit number for students.")
        elif context == "create" and role in [RoleEnum.teacher, RoleEnum.admin]:
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters long for teachers and admins.")
        elif context == "self_change" and role in [RoleEnum.teacher, RoleEnum.admin]:
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters long for teachers and admins.")
        elif context == "reset":
            pass
        else:           
            raise ValueError("Invalid role or context for password validation.")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)


    def get_user_by_username(self, username: str) -> Optional[Account]:
        return self.auth_repo.get_by_username(username)


    def authenticate_user(self, username: str, password: str) -> Optional[Account]:
        account = self.auth_repo.get_by_username(username)
        if not account:
            return None
        if not AuthService.verify_password(password, account.hashed_password):
            return None
        return account

    def create_user(self, metadata: AccountCreate) -> Account:
        existing_user = self.get_user_by_username(metadata.username)
        if existing_user:
            raise ValueError(f"Username '{metadata.username}' is already taken.")
        if metadata.role == RoleEnum.student and not metadata.password:
            password = self.generate_student_password()
            
        hashed_password = self.get_password_hash(password)
        new_account = Account(
            username=metadata.username,
            hashed_password=hashed_password,
            role=metadata.role,
            first_name=metadata.first_name,
            last_name=metadata.last_name
        )
        self.auth_repo.create_account(new_account)
        return new_account

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_token_for_user(account: Account) -> str:
        token_data = {
            "sub": account.username,
            "user_id": account.id,
            "role": account.role.value
        }
        return AuthService.create_access_token(token_data)