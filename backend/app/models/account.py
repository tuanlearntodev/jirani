from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.role_enum import RoleEnum
from app.models.base import TimestampMixin
from sqlalchemy import Enum as SqlEnum


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    role: Mapped[RoleEnum] = mapped_column(SqlEnum(RoleEnum), nullable=False)
    username: Mapped[str] = mapped_column(unique=True, index=True, nullable=False, max_length=50)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    first_name: Mapped[str] = mapped_column(nullable=False, max_length=50)
    last_name: Mapped[str] = mapped_column(nullable=False, max_length=50)
    is_active: Mapped[bool] = mapped_column(default=True)
