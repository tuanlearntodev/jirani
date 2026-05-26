from app.database import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    books = relationship("Book", secondary="book_tags", back_populates="tags")
    audio_tracks = relationship("Audio", secondary="audio_tags", back_populates="tags")
    videos = relationship("Video", secondary="video_tags", back_populates="tags")