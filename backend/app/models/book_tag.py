from app.database import Base
from sqlalchemy import Column, Integer, ForeignKey,UniqueConstraint, Boolean

class BookTag(Base):
    __tablename__ = "book_tags"
    
    id = Column(Integer, primary_key=True) 
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (UniqueConstraint('book_id', 'tag_id'),)