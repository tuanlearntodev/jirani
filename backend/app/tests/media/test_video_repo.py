from datetime import UTC, datetime, timedelta

import pytest

from app.models.video import Video
from app.repositories.video_repo import Video_Repo
from app.schemas.video_schema import Video_Create


def _seed_video(
    db, *, title: str = "clip", file_path: str = "/tmp/nonexistent.mp4"
) -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


def test_create_video_persists(db):
    video = Video_Repo(db).create_video(
        Video_Create(
            title="Intro", description="first", file_path="/tmp/nonexistent.mp4"
        )
    )
    assert video.id is not None
    assert video.title == "Intro"
    assert video.description == "first"
    assert video.file_path == "/tmp/nonexistent.mp4"
    assert video.deleted_at is None


def test_delete_video_soft_deletes(db):
    vid = _seed_video(db)
    deleted = Video_Repo(db).delete_video(vid.id)
    assert deleted.deleted_at is not None
    assert abs(datetime.now(UTC).replace(tzinfo=None) - deleted.deleted_at) < timedelta(
        seconds=60
    )
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.deleted_at is not None


def test_delete_video_missing_id_raises(db):
    with pytest.raises(AttributeError):
        Video_Repo(db).delete_video(999999)
