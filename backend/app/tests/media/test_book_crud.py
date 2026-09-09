from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.book import Book
from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.schemas.book_schema import BookUpdate
from app.services.book_errors import BookNotFound
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader


def _seed_book(db, *, uid: str, **kwargs) -> Book:
    book = Book(
        uid=uid,
        title=kwargs.pop("title", f"Title {uid}"),
        file_path=kwargs.pop("file_path", f"{uid}.pdf"),
        extension=kwargs.pop("extension", "pdf"),
        **kwargs,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def _make_svc(db) -> BookService:
    return BookService(
        book_repo=BookRepo(db),
        validator=ContentValidator(),
        storage=BookFileStorage(),
        epub_reader=EpubMetadataReader(),
        cover_generator=CoverGenerator(),
        author_repo=AuthorRepo(db),
        level_repo=LevelRepo(db),
        genre_repo=GenreRepo(db),
    )


def _patch_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    (tmp_path / "books").mkdir()
    (tmp_path / "covers").mkdir()


def test_update_book_persists_title(db):
    _seed_book(db, uid="bkupd001")
    updated = _make_svc(db).update_book("bkupd001", BookUpdate(title="Renamed"))
    assert updated.title == "Renamed"
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkupd001")).scalar_one()
    assert row.title == "Renamed"


def test_update_book_missing_raises_book_not_found(db):
    with pytest.raises(BookNotFound):
        _make_svc(db).update_book("missing1", BookUpdate(title="Renamed"))


def test_delete_book_removes_row_file_and_cover(db, monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(
        db, uid="bkdel0001", file_path="bkdel0001.pdf", cover_path="bkdel0001.jpg"
    )
    (tmp_path / "books" / "bkdel0001.pdf").write_bytes(b"%PDF-1.4 seed")
    (tmp_path / "covers" / "bkdel0001.jpg").write_bytes(b"\xff\xd8\xff seed")

    _make_svc(db).delete_book("bkdel0001")

    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkdel0001")).scalar_one_or_none()
    assert row is None
    assert not (tmp_path / "books" / "bkdel0001.pdf").exists()
    assert not (tmp_path / "covers" / "bkdel0001.jpg").exists()


def test_delete_book_missing_raises_book_not_found(db):
    with pytest.raises(BookNotFound):
        _make_svc(db).delete_book("missing1")


def test_get_book_file_returns_contained_existing_path(db, monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(db, uid="bkget0001", file_path="bkget0001.pdf")
    (tmp_path / "books" / "bkget0001.pdf").write_bytes(b"%PDF-1.4 seed")

    path = _make_svc(db).get_book_file("bkget0001")

    assert path == (tmp_path / "books" / "bkget0001.pdf").resolve()
    assert path.is_file()


def test_get_book_file_missing_book_raises_book_not_found(db):
    with pytest.raises(BookNotFound):
        _make_svc(db).get_book_file("missing1")


def test_get_book_file_missing_on_disk_raises_book_not_found(db, monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(db, uid="bkget0002", file_path="bkget0002.pdf")

    with pytest.raises(BookNotFound):
        _make_svc(db).get_book_file("bkget0002")
