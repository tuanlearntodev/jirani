from app.models.author import Author
from app.models.book import Book
from app.models.genre import Genre
from app.models.tag import Tag
from app.repositories.book_repo import BookRepo
from app.schemas.book_schema import BookSearchCriteria
from app.tests.conftest import auth_headers, login, setup_admin


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


def test_search_genre_filter_and_entities(db):
    author = Author(name="Ada")
    genre = Genre(name="scifi")
    db.add(author)
    db.add(genre)
    db.commit()
    db.refresh(author)
    db.refresh(genre)

    scifi = _seed_book(db, uid="bk0001")
    scifi.genre = genre
    _seed_book(db, uid="bk0002")
    db.commit()

    page = BookRepo(db).search(BookSearchCriteria(genre="SCIFI"), limit=10, offset=0)
    assert page.total == 1
    assert [item.uid for item in page.items] == ["bk0001"]
    assert page.items[0].genre == "scifi"


def test_search_unknown_author_matches_nothing(db):
    _seed_book(db, uid="bk0001")
    page = BookRepo(db).search(BookSearchCriteria(author="nobody"), limit=10, offset=0)
    assert page.total == 0


def test_search_tags_or_semantics_and_honest_total(db):
    b1 = _seed_book(db, uid="bk0001")
    b2 = _seed_book(db, uid="bk0002")
    t_math = Tag(name="math")
    t_algebra = Tag(name="algebra")
    db.add_all([t_math, t_algebra])
    db.flush()
    b1.tags.append(t_math)
    b1.tags.append(t_algebra)
    b2.tags.append(t_math)
    db.commit()

    page = BookRepo(db).search(
        BookSearchCriteria(tags=["Math", "ALGEBRA"]), limit=2, offset=0
    )
    assert page.total == 2
    assert {item.uid for item in page.items} == {"bk0001", "bk0002"}


def test_search_metadata_containment(db):
    _seed_book(db, uid="bk0001", metadata_={"publisher": "Penguin"})
    _seed_book(db, uid="bk0002", metadata_={"publisher": "Puffin"})
    page = BookRepo(db).search(
        BookSearchCriteria(metadata_={"publisher": "Penguin"}), limit=10, offset=0
    )
    assert page.total == 1
    assert [item.uid for item in page.items] == ["bk0001"]


def test_search_pagination_pages_are_disjoint_and_complete(db):
    for i in range(5):
        _seed_book(db, uid=f"bk{i:04d}")
    pages = [
        BookRepo(db).search(BookSearchCriteria(), limit=2, offset=off)
        for off in (0, 2, 4)
    ]
    uid_sets = [{item.uid for item in p.items} for p in pages]
    assert all(p.total == 5 for p in pages)
    assert all(not (a & b) for a, b in zip(uid_sets, uid_sets[1:], strict=False))
    assert set().union(*uid_sets) == {f"bk{i:04d}" for i in range(5)}


def test_list_books_endpoint_authed_returns_page(db, client, setup_paths):
    _seed_book(db, uid="bklist01")
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    response = client.get("/books/", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["uid"] == "bklist01"


def test_list_books_unauthenticated_401(client):
    response = client.get("/books/")
    assert response.status_code == 401
