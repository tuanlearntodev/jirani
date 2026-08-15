from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.tag import Tag


class Book(TimestampMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_metadata_gin", "metadata", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    book_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    language: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    cover_path: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=True,
    )

    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="book_tags", back_populates="books"
    )
