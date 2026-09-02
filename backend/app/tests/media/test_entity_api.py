import pytest

from app.models.author import Author
from app.models.genre import Genre
from app.models.level import Level
from app.tests.conftest import auth_headers, login, setup_admin

CASES = [
    ("/authors/", Author),
    ("/levels/", Level),
    ("/genres/", Genre),
]


@pytest.mark.parametrize(
    ("prefix", "model"), CASES, ids=["authors", "levels", "genres"]
)
def test_authed_list_returns_seeded_rows(client, db, setup_paths, prefix, model):
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    rows = []
    for name in ["alpha", "beta"]:
        row = model(name=name)
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    response = client.get(prefix, headers=auth_headers(token))
    assert response.status_code == 200
    got = {(item["id"], item["name"]) for item in response.json()}
    assert got == {(row.id, row.name) for row in rows}


@pytest.mark.parametrize(
    "prefix", ["/authors/", "/levels/", "/genres/"], ids=["authors", "levels", "genres"]
)
def test_unauthenticated_returns_401(client, prefix):
    response = client.get(prefix)
    assert response.status_code == 401
