from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func


class TimestampMixin:
    created_at : Mapped[datetime] = mapped_column(default=func.now())
    updated_at : Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())