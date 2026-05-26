from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from app.models import Book, Tag
from app.schemas.book_schema import BookCreate
from typing import Optional

class BookRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_book_by_uid(self, book_uid: str) -> Book:
        return self.db_session.query(Book).options(joinedload(Book.tags)).filter(Book.uid == book_uid).first()

    def create_book(self, book_create: BookCreate) -> Book:
        tag_data = book_create.tags
        book_dict = book_create.model_dump(exclude={"tags", "cover_url"})
        
        existing = self.db_session.query(Book).filter(Book.uid == book_create.uid).first()
        if existing:
            raise ValueError(f"Book with UID {book_create.uid} already exists")
        
        new_book = Book(**book_dict)
        
        if tag_data:
            for tag_in in tag_data:
                tag = self.db_session.query(Tag).filter(Tag.name.ilike(tag_in.name)).first()
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                new_book.tags.append(tag)

        try:
            self.db_session.add(new_book)
            self.db_session.commit()
            self.db_session.refresh(new_book)
            return new_book
        except Exception as e:
            self.db_session.rollback()
            raise Exception(f"Failed to create book in database: {str(e)}")
    
    def get_all_books(self) -> list[Book]:
        return self.db_session.query(Book).options(joinedload(Book.tags)).all()
    
    def cleanup_orphan_tags(self) -> None:
        """Delete tags that are no longer attached to any book."""
        orphans = self.db_session.query(Tag).filter(~Tag.books.any()).all()
        for tag in orphans:
            self.db_session.delete(tag)
        self.db_session.commit()

    def delete_book(self, book_uid: str) -> None:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise ValueError(f"Book with UID {book_uid} does not exist")
        self.db_session.delete(book)
        self.db_session.commit()
        self.cleanup_orphan_tags()
        
    def update_book(self, book_uid: str, book_update: BookCreate) -> Book:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise ValueError(f"Book with UID {book_uid} does not exist")
        
        tag_data = book_update.tags
        book_dict = book_update.model_dump(exclude={"tags", "cover_url"})
        
        for key, value in book_dict.items():
            setattr(book, key, value)
        
        if tag_data is not None:
            book.tags.clear()
            for tag_in in tag_data:
                tag = self.db_session.query(Tag).filter(Tag.name.ilike(tag_in.name)).first()
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                book.tags.append(tag)
        
        try:
            self.db_session.commit()
            self.db_session.refresh(book)
            self.cleanup_orphan_tags()
            return book
        except Exception as e:
            self.db_session.rollback()
            raise Exception(f"Failed to update book in database: {str(e)}")
    
    def search_books(
        self,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        file_type: Optional[str] = None,
        extension: Optional[str] = None
    ) -> list[Book]:
        """
        Dynamic search with multiple optional filters.
        Filters are combined using AND logic.
        """
        query = self.db_session.query(Book).options(joinedload(Book.tags))
        
        # Apply filters dynamically
        filters = []
        
        if title:
            filters.append(Book.title.ilike(f"%{title}%"))
        
        if file_type:
            filters.append(Book.file_type.ilike(f"%{file_type}%"))
        
        if extension:
            filters.append(Book.extension.ilike(extension))
        
        # Apply all non-tag filters
        if filters:
            query = query.filter(and_(*filters))
        
        # Handle tag filtering separately (requires join)
        if tags:
            # Normalize tag names
            normalized_tags = [tag.strip().lower() for tag in tags]
            query = query.join(Book.tags).filter(Tag.name.in_(normalized_tags))
        
        return query.all()