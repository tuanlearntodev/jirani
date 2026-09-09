from urllib.parse import quote

import pytest

from app.config import settings
from app.models.book import Book
from app.tests.conftest import auth_headers, login, setup_admin


@pytest.fixture()
def stream_env(client, setup_paths, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


def _seed_book(db, *, uid: str, file_path: str, extension: str = "pdf") -> Book:
    book = Book(
        uid=uid,
        title=f"Title {uid}",
        file_path=file_path,
        extension=extension,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def test_stream_authed_returns_x_accel_204(db, client, stream_env):
    tmp_path, headers = stream_env
    uid = "abc123"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/stream", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Accept-Ranges"] == "bytes"


def test_stream_missing_book_404(client, stream_env):
    _, headers = stream_env
    response = client.get("/books/nonexistent/stream", headers=headers)
    assert response.status_code == 404


def test_stream_poisoned_file_path_404(db, client, stream_env):
    _, headers = stream_env
    _seed_book(db, uid="evil", file_path="../../../../etc/passwd")
    response = client.get("/books/evil/stream", headers=headers)
    assert response.status_code == 404


def test_stream_missing_file_on_disk_404(db, client, stream_env):
    _, headers = stream_env
    _seed_book(db, uid="gone", file_path="gone.pdf")
    response = client.get("/books/gone/stream", headers=headers)
    assert response.status_code == 404


def test_stream_unauthenticated_401(db, client, stream_env):
    tmp_path, _ = stream_env
    uid = "abc123"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/stream")
    assert response.status_code == 401


def test_stream_epub_content_type(db, client, stream_env):
    tmp_path, headers = stream_env
    uid = "epub1"
    (tmp_path / f"{uid}.epub").write_bytes(b"PK\x03\x04 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    response = client.get(f"/books/{uid}/stream", headers=headers)
    assert response.headers["Content-Type"] == "application/epub+zip"
