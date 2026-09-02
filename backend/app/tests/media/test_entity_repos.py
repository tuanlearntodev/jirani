import pytest
from sqlalchemy import func, select

from app.models.author import Author
from app.models.genre import Genre
from app.models.level import Level
from app.repositories.author_repo import AuthorRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo

CASES = [
    (Author, AuthorRepo),
    (Level, LevelRepo),
    (Genre, GenreRepo),
]


def _create(db, model, name: str):
    row = model(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.parametrize(("model", "repo_cls"), CASES, ids=["author", "level", "genre"])
def test_get_by_name_case_insensitive_returns_stored_case(db, model, repo_cls):
    _create(db, model, "Math")
    found = repo_cls(db).get_by_name("MATH")
    assert found is not None
    assert found.name == "Math"
    assert repo_cls(db).get_by_name("missing") is None


@pytest.mark.parametrize(("model", "repo_cls"), CASES, ids=["author", "level", "genre"])
def test_get_or_create_reuses_existing_row(db, model, repo_cls):
    existing = _create(db, model, "Math")
    got = repo_cls(db).get_or_create_by_name("  MATH ")
    assert got.id == existing.id
    assert got.name == "Math"
    db.expire_all()
    count = db.scalar(select(func.count()).select_from(model))
    assert count == 1


@pytest.mark.parametrize(("model", "repo_cls"), CASES, ids=["author", "level", "genre"])
def test_get_or_create_creates_lowercased(db, model, repo_cls):
    created = repo_cls(db).get_or_create_by_name("Algebra")
    assert created.id is not None
    assert created.name == "algebra"


@pytest.mark.parametrize(("model", "repo_cls"), CASES, ids=["author", "level", "genre"])
def test_list_all_sorted_by_name(db, model, repo_cls):
    for name in ["zeta", "alpha", "mid"]:
        _create(db, model, name)
    names = [entity.name for entity in repo_cls(db).list_all()]
    assert names == ["alpha", "mid", "zeta"]
