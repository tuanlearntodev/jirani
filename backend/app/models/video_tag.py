from app.database import Base
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint

class VideoTag(Base):
    __tablename__ = "video_tags"
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("video.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint('video_id', 'tag_id'),)