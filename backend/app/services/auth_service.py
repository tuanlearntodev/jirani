from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import settings
from app.models.account import Account
from app.schemas.auth_schema import SignUpRequest

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_MINUTES = 120

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[Account]:
        return db.query(Account).filter(Account.username == username).first()

    @staticmethod
    def create_user(db: Session, signup_data: SignUpRequest) -> Account:
        hashed_password = AuthService.get_password_hash(signup_data.password)
        new_account = Account(
            username=signup_data.username,
            hashed_password=hashed_password,
            first_name=signup_data.first_name,
            last_name=signup_data.last_name,
            is_active=True
        )
        db.add(new_account)
        db.commit()
        db.refresh(new_account)
        return new_account

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[Account]:
        account = db.query(Account).filter(
            Account.username == username,
            Account.is_active == True
        ).first()
        if not account:
            return None
        if not AuthService.verify_password(password, account.hashed_password):
            return None
        return account

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_token_for_user(account: Account) -> str:
        role_names = [role.name for role in account.roles]
        token_data = {
            "sub": account.username,
            "user_id": account.id,
            "roles": role_names
        }
        return AuthService.create_access_token(token_data)

    @staticmethod
    def reset_password(db: Session, username: str, new_password: str) -> Account:
        user = db.query(Account).filter(Account.username == username).one_or_none()
        if not user:
            raise ValueError("User not found")
        user.hashed_password = AuthService.get_password_hash(new_password)
        db.commit()
        db.refresh(user)
        return user