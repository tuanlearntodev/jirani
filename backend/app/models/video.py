from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Video(Base):
    __tablename__ = "video"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    deleted_at = Column(DateTime, nullable=True, default=None)
    tags = relationship("Tag", secondary="video_tags", back_populates="videos")
