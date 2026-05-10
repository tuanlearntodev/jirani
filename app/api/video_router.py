from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from app.schemas.video_schema import Video_Create, Video_View
from app.repositories.video_repo import Video_Repo
from sqlalchemy.orm import Session, joinedload
from app.models.video import Video
from app.models.tag import Tag
import os, shutil, uuid, asyncio, mimetypes
from fastapi.responses import StreamingResponse
from app.database import get_db
from pathlib import Path
from typing import Optional

router = APIRouter(prefix="/videos", tags=["videos"])
VIDS_DIR = Path("uploads") / "vids"

def _build_video_view(v: Video) -> Video_View:
    return Video_View(
        id=v.id,
        title=v.title,
        description=v.description,
        video_url=f"/videos/stream/{v.id}",
        tags=[{"id": t.id, "name": t.name} for t in (v.tags or [])]
    )

@router.get("/", response_model=list[Video_View])
def get_videos(db: Session = Depends(get_db)):
    videos = db.query(Video).options(joinedload(Video.tags)).filter(Video.deleted_at == None).all()
    return [_build_video_view(v) for v in videos]

@router.post("/upload", response_model=Video_View)
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    tags: str = Form(""),
    db: Session = Depends(get_db)
):
    VIDS_DIR.mkdir(parents=True, exist_ok=True)
    file_location = VIDS_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)

    repo = Video_Repo(db)
    video_db = repo.create_video(Video_Create(
        title=title, description=description, file_path=str(file_location)
    ))

    tag_names = [t.strip() for t in tags.split(",") if t.strip()] if tags.strip() else []
    for tag_name in tag_names:
        tag = db.query(Tag).filter(Tag.name.ilike(tag_name)).first()
        if not tag:
            tag = Tag(name=tag_name.strip().lower())
            db.add(tag)
            db.flush()
        if tag not in video_db.tags:
            video_db.tags.append(tag)
    db.commit()
    db.refresh(video_db)
    return _build_video_view(video_db)

@router.post("/upload_multiple", response_model=list[Video_View])
async def upload_multiple(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    VIDS_DIR.mkdir(parents=True, exist_ok=True)
    repo = Video_Repo(db)
    results = []
    for file in files:
        file_location = VIDS_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
        video_db = repo.create_video(Video_Create(
            title=file.filename.rsplit(".", 1)[0],
            description=None,
            file_path=str(file_location)
        ))
        db.refresh(video_db)
        results.append(_build_video_view(video_db))
    return results

@router.patch("/{video_id}", response_model=Video_View)
def update_video(
    video_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    db: Session = Depends(get_db)
):
    video = db.query(Video).options(joinedload(Video.tags)).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if title is not None:
        video.title = title
    if description is not None:
        video.description = description
    if tags is not None:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]
        video.tags.clear()
        for tag_name in tag_names:
            tag = db.query(Tag).filter(Tag.name.ilike(tag_name)).first()
            if not tag:
                tag = Tag(name=tag_name.strip().lower())
                db.add(tag)
                db.flush()
            video.tags.append(tag)
    db.commit()
    db.refresh(video)
    return _build_video_view(video)

@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    repo = Video_Repo(db)
    return repo.delete_video(video_id)

@router.get("/stream/{video_id}")
def stream_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    mime_type, _ = mimetypes.guess_type(video.file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    def iterfile():
        with open(video.file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(iterfile(), media_type=mime_type)