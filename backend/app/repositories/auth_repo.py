from sqlalchemy.orm import Session
from app.models import Account, RoleEnum
from typing import Optional

class AuthRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_username(self, username: str) -> Optional[Account]:
        return self.db_session.query(Account).filter(Account.username == username).first()
    
    def get_by_id(self, account_id: int) -> Optional[Account]:
        return self.db_session.query(Account).filter(Account.id == account_id).first()
      
    def create_account(self, account: Account) -> Account:
        self.db_session.add(account)
        self.db_session.commit()
        self.db_session.refresh(account)
        return account
      
    def list_all(self, role: Optional[RoleEnum] = None) -> list[Account]:
        query = self.db_session.query(Account)
        if role is not None:
            query = query.filter(Account.role == role)
        return query.all()
      
    def has_admin(self) -> bool:
        return self.db_session.query(Account).filter(Account.role == RoleEnum.admin).first() is not None
    
    def change_password(self, account: Account, new_hashed_password: str) -> Account:
        account.hashed_password = new_hashed_password
        self.db_session.commit()
        self.db_session.refresh(account)
        return account
    
    def get_next_prefix_number(self, prefix: str) -> int:
        accounts = self.db_session.query(Account).filter(Account.username.like(f"{prefix}%")).all()
        numbers = []
        for account in accounts:
            suffix = account.username.removeprefix(prefix)
            if suffix.isdigit():
                numbers.append(int(suffix))
        return max(numbers) + 1 if numbers else 1