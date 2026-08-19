from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.audio import Audio
    from app.models.book import Book
    from app.models.video import Video


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    books: Mapped[list["Book"]] = relationship(
        "Book", secondary="book_tags", back_populates="tags"
    )
    audio_tracks: Mapped[list["Audio"]] = relationship(
        "Audio", secondary="audio_tags", back_populates="tags"
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video", secondary="video_tags", back_populates="tags"
    )
