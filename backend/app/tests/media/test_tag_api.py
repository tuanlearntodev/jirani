from app.repositories.tag_repo import TagRepo
from app.schemas.tag_schema import TagCreate


def test_get_tags_empty(client):
    response = client.get("/tags/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_tags_three_seeded(client, db):
    rows = [
        TagRepo(db).create_tag(TagCreate(name=n))
        for n in ["science", "math", "history"]
    ]
    response = client.get("/tags/")
    assert response.status_code == 200
    got = {(t["id"], t["name"]) for t in response.json()}
    assert got == {(r.id, r.name) for r in rows}
