from app.database import Base
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint

class AudioTag(Base):
    __tablename__ = "audio_tags"
    id = Column(Integer, primary_key=True)
    audio_id = Column(Integer, ForeignKey("audio.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint('audio_id', 'tag_id'),)