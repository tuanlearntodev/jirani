import io

import pymupdf
from sqlalchemy import select

from app.config import settings
from app.models.book import Book
from app.tests.conftest import auth_headers, login, setup_admin


def _make_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def _admin_headers(client, setup_paths) -> dict:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def test_upload_pdf_happy_path(db, client, monkeypatch, tmp_path, setup_paths):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Real PDF", "tags": "math, algebra"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert (tmp_path / row.file_path).exists()


def test_upload_bad_magic_400_nothing_on_disk(
    db, client, monkeypatch, tmp_path, setup_paths
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        data={"title": "Fake"},
        headers=headers,
    )
    assert response.status_code == 400
    assert not list(tmp_path.glob("*.pdf"))


def test_upload_requires_auth(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Real PDF"},
    )
    assert response.status_code in (401, 403)


def test_upload_genre_form_linked(db, client, monkeypatch, tmp_path, setup_paths):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Genre Book", "genre": "Sci-Fi"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert row.genre is not None
    assert row.genre.name == "sci-fi"


def test_upload_author_form_stored(db, client, monkeypatch, tmp_path, setup_paths):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Author Book", "author": "Ada Lovelace"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert row.author is not None
    assert row.author.name == "ada lovelace"


def test_upload_overlong_title_400(db, client, monkeypatch, tmp_path, setup_paths):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "x" * 256},
        headers=headers,
    )
    assert response.status_code == 400
    assert not list(tmp_path.glob("*.pdf"))
