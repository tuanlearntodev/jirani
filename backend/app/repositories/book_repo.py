from sqlalchemy import false, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Book, Tag
from app.repositories.author_repo import AuthorRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.schemas.book_schema import BookCreate, BookRead, BookSearchCriteria, Page
from app.services.book_errors import BookNotFound


class BookRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_book_by_uid(self, book_uid: str) -> Book | None:
        stmt = (
            select(Book)
            .options(
                selectinload(Book.author),
                selectinload(Book.level),
                selectinload(Book.genre),
                selectinload(Book.tags),
            )
            .where(Book.uid == book_uid)
        )
        return self.db_session.execute(stmt).scalar_one_or_none()

    def create_book(self, book_create: BookCreate) -> Book:
        tag_data = book_create.tags
        book_dict = book_create.model_dump(exclude={"tags"})

        existing = self.get_book_by_uid(book_create.uid)
        if existing:
            raise ValueError(f"Book with UID {book_create.uid} already exists")

        new_book = Book(**book_dict)

        if tag_data:
            for tag_in in tag_data:
                tag = self.db_session.scalar(
                    select(Tag).where(Tag.name.ilike(tag_in.name))
                )
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                new_book.tags.append(tag)

        try:
            self.db_session.add(new_book)
            self.db_session.commit()
            self.db_session.refresh(new_book)
            return new_book
        except IntegrityError:
            self.db_session.rollback()
            raise

    def get_all_books(self) -> list[Book]:
        return list(
            self.db_session.scalars(select(Book).options(selectinload(Book.tags))).all()
        )

    def _delete_orphan_tags(self) -> None:
        orphans = self.db_session.scalars(select(Tag).where(~Tag.books.any())).all()
        for tag in orphans:
            self.db_session.delete(tag)

    def cleanup_orphan_tags(self) -> None:
        try:
            self._delete_orphan_tags()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise

    def delete_book(self, book_uid: str) -> None:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        try:
            self.db_session.delete(book)
            self.db_session.flush()
            self._delete_orphan_tags()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise

    def update_book(self, book_uid: str, book_update: BookCreate) -> Book:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")

        tag_data = book_update.tags
        book_dict = book_update.model_dump(exclude={"tags", "cover_url"})

        for key, value in book_dict.items():
            setattr(book, key, value)

        if tag_data is not None:
            book.tags.clear()
            for tag_in in tag_data:
                tag = self.db_session.scalar(
                    select(Tag).where(Tag.name.ilike(tag_in.name))
                )
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                book.tags.append(tag)

        try:
            self.db_session.commit()
            self.db_session.refresh(book)
            self.cleanup_orphan_tags()
            return book
        except IntegrityError:
            self.db_session.rollback()
            raise

    def search(
        self, criteria: BookSearchCriteria, *, limit: int, offset: int
    ) -> Page[BookRead]:
        stmt = select(Book).options(
            selectinload(Book.tags),
            selectinload(Book.author),
            selectinload(Book.level),
            selectinload(Book.genre),
        )

        if criteria.title is not None:
            stmt = stmt.where(Book.title.ilike(f"%{criteria.title}%"))
        if criteria.language is not None:
            stmt = stmt.where(Book.language == criteria.language)
        if criteria.extension is not None:
            stmt = stmt.where(Book.extension == criteria.extension)
        if criteria.tags:
            names = [t.lower() for t in criteria.tags]
            stmt = stmt.where(Book.tags.any(Tag.name.in_(names)))
        if criteria.metadata_:
            stmt = stmt.where(Book.metadata_.contains(criteria.metadata_))

        for repo, value, column in (
            (AuthorRepo, criteria.author, Book.author_id),
            (LevelRepo, criteria.level, Book.level_id),
            (GenreRepo, criteria.genre, Book.genre_id),
        ):
            if value is not None:
                entity = repo(self.db_session).get_by_name(value)
                stmt = stmt.where(column == entity.id if entity else false())

        total = self.db_session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Book.created_at.desc(), Book.id.desc())
            .limit(limit)
            .offset(offset)
        )
        books = list(self.db_session.execute(stmt).scalars().all())
        items: list[BookRead] = [BookRead.model_validate(book) for book in books]
        return Page[BookRead](items=items, total=total, limit=limit, offset=offset)
