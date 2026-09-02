import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Tag
from app.repositories.tag_repo import TagRepo
from app.schemas.tag_schema import TagCreate


def _seed_tag(db, name: str) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def test_get_all_tags_returns_seeded_rows(db):
    _seed_tag(db, "math")
    _seed_tag(db, "science")
    _seed_tag(db, "history")
    rows = TagRepo(db).get_all_tags()
    assert {t.name for t in rows} == {"math", "science", "history"}
    assert len(rows) == 3


def test_get_tag_by_id_returns_row_or_none(db):
    seeded = _seed_tag(db, "math")
    row = TagRepo(db).get_tag_by_id(seeded.id)
    assert row.name == "math"
    assert TagRepo(db).get_tag_by_id(999999) is None


def test_create_tag_normalizes_whitespace_and_enforces_unique(db):
    created = TagRepo(db).create_tag(TagCreate(name="  Math  "))
    assert created.name == "Math"
    assert created.id is not None
    with pytest.raises(IntegrityError):
        TagRepo(db).create_tag(TagCreate(name="Math"))
