import pytest

import app.api.video_router as video_router_module
from app.models.tag import Tag
from app.models.video import Video
from app.repositories.video_repo import Video_Repo


def _seed_video(
    db, *, title: str = "clip", file_path: str = "/tmp/nonexistent.mp4"
) -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


def test_get_videos_empty(client):
    response = client.get("/videos/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_videos_excludes_soft_deleted(db, client):
    a = _seed_video(db, title="a")
    b = _seed_video(db, title="b")
    Video_Repo(db).delete_video(a.id)
    db.expire_all()
    response = client.get("/videos/")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {b.id}


def test_upload_happy(db, client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload",
        files={
            "file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42 mock bytes", "video/mp4")
        },
        data={"title": "Intro", "description": "first", "tags": "lesson"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Intro"
    assert body["description"] == "first"
    assert body["video_url"] == f"/videos/stream/{body['id']}"
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "lesson"
    assert body["tags"][0]["id"] is not None
    files_on_disk = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(files_on_disk) == 1
    assert files_on_disk[0].read_bytes() == b"\x00\x00\x00\x18ftypmp42 mock bytes"
    db.expire_all()
    row = db.query(Video).filter(Video.id == body["id"]).first()
    assert row is not None
    assert row.file_path == str(files_on_disk[0])


def test_upload_missing_title_returns_422(client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    assert response.status_code == 422


def test_upload_txt_still_succeeds_quirk(client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"title": "Notes"},
    )
    # Quirk pin: no extension validation exists. Task 8 flips this to 400.
    assert response.status_code == 200
    assert response.json()["title"] == "Notes"


def test_upload_tags_whitespace_first_seen_reused(db, client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        data={"title": "T", "tags": " MATH , math "},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "math"
    assert body["tags"][0]["id"] is not None
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_tag_reuses_preexisting_row(db, client, monkeypatch, tmp_path):
    tag = Tag(name="math")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        data={"title": "T", "tags": "math"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["id"] == tag.id
    assert body["tags"][0]["name"] == "math"
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_multiple_valid_pair(client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload_multiple",
        files=[
            ("files", ("a.mp4", b"bytes-a", "video/mp4")),
            ("files", ("b.mp4", b"bytes-b", "video/mp4")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert [item["title"] for item in body] == ["a", "b"]
    assert all(item["tags"] == [] for item in body)


def test_upload_multiple_txt_second_still_commits(db, client, monkeypatch, tmp_path):
    monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)
    response = client.post(
        "/videos/upload_multiple",
        files=[
            ("files", ("a.mp4", b"bytes-a", "video/mp4")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    db.expire_all()
    # Quirk pin: no validation = no failure. Task 8's probe flips this.
    assert db.query(Video).count() == 2


def test_patch_title_description_tags_replace(db, client):
    vid = _seed_video(db)
    response = client.patch(
        f"/videos/{vid.id}",
        params={"title": "New", "description": "desc", "tags": "x, y"},
    )
    assert response.status_code == 200
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.title == "New"
    assert row.description == "desc"
    assert sorted(tag.name for tag in row.tags) == ["x", "y"]


def test_patch_empty_tags_clears_but_keeps_tag_rows(db, client):
    vid = _seed_video(db)
    tag = Tag(name="lesson")
    db.add(tag)
    db.flush()
    vid.tags.append(tag)
    db.commit()
    tag_id = tag.id
    response = client.patch(f"/videos/{vid.id}", params={"tags": ""})
    assert response.status_code == 200
    assert response.json()["tags"] == []
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.tags == []
    assert db.query(Tag).filter(Tag.id == tag_id).one().name == "lesson"


def test_patch_omitted_fields_unchanged(db, client):
    vid = _seed_video(db, title="Keep")
    response = client.patch(f"/videos/{vid.id}", params={"description": "changed"})
    assert response.status_code == 200
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.title == "Keep"
    assert row.description == "changed"
    assert row.tags == []


def test_patch_missing_video_404(client):
    response = client.patch("/videos/999999", params={"title": "x"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_delete_video_soft_deletes_via_api(db, client):
    vid = _seed_video(db)
    response = client.delete(f"/videos/{vid.id}")
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert "title" in body
    assert body["deleted_at"] is not None
    db.expire_all()
    assert db.query(Video).count() == 1
    assert client.get("/videos/").json() == []


def test_delete_missing_video_raises_attribute_error(client):
    with pytest.raises(AttributeError):
        client.delete("/videos/999999")


def test_stream_serves_bytes_byte_for_byte(db, client, tmp_path):
    file_bytes = b"\x00\x01\x02\x03" * 1000
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(file_bytes)
    vid = _seed_video(db, file_path=str(video_file))
    response = client.get(f"/videos/stream/{vid.id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.content == file_bytes


def test_stream_missing_video_404(client):
    response = client.get("/videos/stream/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_stream_soft_deleted_still_streams_quirk(db, client, tmp_path):
    file_bytes = b"\x00\x01\x02\x03" * 1000
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(file_bytes)
    vid = _seed_video(db, file_path=str(video_file))
    Video_Repo(db).delete_video(vid.id)
    response = client.get(f"/videos/stream/{vid.id}")
    assert response.status_code == 200
    assert response.content == file_bytes


def test_stream_missing_file_raises(db, client, tmp_path):
    vid = _seed_video(db, file_path=str(tmp_path / "gone.mp4"))
    with pytest.raises(FileNotFoundError):
        client.get(f"/videos/stream/{vid.id}")
