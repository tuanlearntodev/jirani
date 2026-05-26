from app.database import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(36), unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    cover_path = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    extension = Column(String, nullable=False)

    tags = relationship("Tag", secondary="book_tags", back_populates="books")