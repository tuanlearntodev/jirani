from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.config import settings
from app.models import Account, RoleEnum
from app.schemas import AccountCreate, BulkCreateRequest, BulkCredentialItem, BulkCreateResponse
from app.repositories import AuthRepo
import random, secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_MINUTES = 120

class AuthService:
    def __init__(self, auth_repo: AuthRepo):
        self.auth_repo = auth_repo

    @staticmethod
    def generate_student_password() -> str:
        return str(random.randint(100000, 999999))
    
    @staticmethod
    def generate_teacher_password() -> str:
        return secrets.token_urlsafe(8)

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

    def create_user(self, metadata: AccountCreate) -> tuple[Account, str]:
        existing_user = self.get_user_by_username(metadata.username)
        if existing_user:
            raise ValueError(f"Username '{metadata.username}' is already taken.")
        if metadata.role == RoleEnum.student:
            password = self.generate_student_password()
            first_login = False
        elif metadata.role == RoleEnum.teacher:
            password = self.generate_teacher_password()
            first_login = True
        else:
            raise ValueError("Only student and teacher accounts can be created via this endpoint.")

        hashed_password = self.get_password_hash(password)
        new_account = Account(
            username=metadata.username,
            hashed_password=hashed_password,
            role=metadata.role,
            first_name=metadata.first_name,
            last_name=metadata.last_name,
            first_login=first_login
        )
        self.auth_repo.create_account(new_account)
        return new_account, password

    def change_password(self, username: str, new_password: str) -> Account:
        user = self.get_user_by_username(username)
        if not user:
            raise ValueError(f"User '{username}' not found.")
        user.hashed_password = self.get_password_hash(new_password)
        self.auth_repo.change_password(user, user.hashed_password)
        return user
    
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
    
    def reset_password(self, account_id: int) -> tuple[Account, str]:
        user = self.auth_repo.get_by_id(account_id)
        if not user:
            raise ValueError(f"User with ID '{account_id}' not found.")
        if user.role != RoleEnum.student and user.role != RoleEnum.teacher:
            raise ValueError("Password reset is only allowed for students or teachers accounts.")
        if user.role == RoleEnum.student:
            password = self.generate_student_password()
            hashed_password = self.get_password_hash(password)
        elif user.role == RoleEnum.teacher:
            password = self.generate_teacher_password()
            hashed_password = self.get_password_hash(password)
        user.hashed_password = hashed_password
        self.auth_repo.change_password(user, user.hashed_password)
        return user, password
    
    def setup_admin_account(self, password: str) -> Account:
        admin_user = self.get_user_by_username("admin")
        if admin_user:
            raise ValueError("Admin account already exists.")
        hashed_password = self.get_password_hash(password)
        new_admin = Account(
            username="admin",
            hashed_password=hashed_password,
            role=RoleEnum.admin,
            first_name="Admin",
            last_name="User"
        )
        self.auth_repo.create_account(new_admin)
        return new_admin
    
    def bulk_create_users(self, bulk_data: BulkCreateRequest) -> BulkCreateResponse:
        if bulk_data.role == RoleEnum.admin:
            raise ValueError("Cannot create admin accounts via bulk endpoint")
        
        created_accounts = []
        number = self.auth_repo.get_next_prefix_number(bulk_data.prefix)
        
        for i in range(bulk_data.count):
            username = f"{bulk_data.prefix}{number}"
            number +=1
            if self.get_user_by_username(username):
                continue
            
            if bulk_data.role == RoleEnum.student:
                password = self.generate_student_password()
                first_login = False
            elif bulk_data.role == RoleEnum.teacher:
                password = self.generate_teacher_password()
                first_login = True
            else:
                raise ValueError("Bulk creation is only allowed for students or teachers.")
            hashed_password = self.get_password_hash(password)
            new_account = Account(
                username=username,
                hashed_password=hashed_password,
                role=bulk_data.role,
                first_name=bulk_data.first_name,
                last_name=bulk_data.last_name, 
                first_login=first_login
            )
            self.auth_repo.create_account(new_account)
            created_accounts.append(BulkCredentialItem(username=username, password=password, role=bulk_data.role))
        return BulkCreateResponse(created=len(created_accounts), accounts=created_accounts)