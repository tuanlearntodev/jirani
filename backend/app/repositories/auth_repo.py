from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, RoleEnum


class AuthRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_username(self, username: str) -> Account | None:
        return self.db_session.scalars(
            select(Account).where(Account.username == username)
        ).first()

    def get_by_id(self, account_id: int) -> Account | None:
        return self.db_session.scalars(
            select(Account).where(Account.id == account_id)
        ).first()

    def create_account(self, account: Account) -> Account:
        self.db_session.add(account)
        self.db_session.commit()
        self.db_session.refresh(account)
        return account

    def get_all_users(self, role: RoleEnum | None = None) -> list[Account]:
        stmt = select(Account)
        if role is not None:
            stmt = stmt.where(Account.role == role)
        return list(self.db_session.scalars(stmt))

    def has_admin(self) -> bool:
        return (
            self.db_session.scalars(
                select(Account).where(Account.role == RoleEnum.admin).limit(1)
            ).first()
            is not None
        )

    def change_password(self, account: Account, new_hashed_password: str) -> Account:
        account.hashed_password = new_hashed_password
        account.first_login = False
        self.db_session.commit()
        self.db_session.refresh(account)
        return account

    def get_next_prefix_number(self, prefix: str) -> int:
        accounts = list(
            self.db_session.scalars(
                select(Account).where(Account.username.like(f"{prefix}%"))
            )
        )
        numbers = []
        for account in accounts:
            suffix = account.username.removeprefix(prefix)
            if suffix.isdigit():
                numbers.append(int(suffix))
        return max(numbers) + 1 if numbers else 1
