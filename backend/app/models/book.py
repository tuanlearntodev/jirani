from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.author import Author
from app.models.base import TimestampMixin
from app.models.genre import Genre
from app.models.level import Level
from app.models.tag import Tag


class Book(TimestampMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_metadata_gin", "metadata", postgresql_using="gin"),
    )

    if TYPE_CHECKING:

        def __init__(
            self,
            uid: str,
            title: str,
            author: Author | None = None,
            level: Level | None = None,
            genre: Genre | None = None,
            id: int | None = None,
            language: str | None = None,
            cover_path: str | None = None,
            file_path: str | None = None,
            extension: str | None = None,
            metadata_: dict[str, str] | None = None,
        ) -> None: ...

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("authors.id", ondelete="SET NULL"), nullable=True
    )
    level_id: Mapped[int | None] = mapped_column(
        ForeignKey("levels.id", ondelete="SET NULL"), nullable=True
    )
    genre_id: Mapped[int | None] = mapped_column(
        ForeignKey("genres.id", ondelete="SET NULL"), nullable=True
    )
    language: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    cover_path: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=True,
    )

    author: Mapped[Author | None] = relationship(back_populates="books")
    level: Mapped[Level | None] = relationship(back_populates="books")
    genre: Mapped[Genre | None] = relationship(back_populates="books")

    @property
    def author_name(self) -> str | None:
        return self.author.name if self.author else None

    @property
    def level_name(self) -> str | None:
        return self.level.name if self.level else None

    @property
    def genre_name(self) -> str | None:
        return self.genre.name if self.genre else None

    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="book_tags", back_populates="books"
    )
