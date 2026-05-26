from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from app.schemas.audio_schema import Audio_Create, Audio_View
from app.repositories.audio_repo import Audio_Repo
from app.models.audio import Audio
from app.models.tag import Tag
from app.database import get_db
import os, shutil, uuid, asyncio
from typing import Optional

router = APIRouter(prefix="/audio", tags=["audio"])
ALLOWED_AUDIO = {"mp3", "mp4", "wav", "ogg", "m4a", "aac", "flac"}

def validate_audio(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed")

def _build_audio_view(a: Audio) -> Audio_View:
    return Audio_View(
        id=a.id,
        title=a.title,
        description=a.description,
        audio_url=f"/audio/stream/{a.id}",
        tags=[{"id": t.id, "name": t.name} for t in (a.tags or [])]
    )

@router.get("/", response_model=list[Audio_View])
def get_audio(db: Session = Depends(get_db)):
    tracks = db.query(Audio).options(joinedload(Audio.tags)).filter(Audio.deleted_at == None).all()
    return [_build_audio_view(a) for a in tracks]

@router.post("/upload", response_model=Audio_View)
async def upload_audio(
    file: UploadFile = File(...),
    tags: str = Form(""),
    db: Session = Depends(get_db)
):
    validate_audio(file.filename)
    upload_directory = "uploads/audio"
    os.makedirs(upload_directory, exist_ok=True)
    file_location = f"{upload_directory}/{uuid.uuid4()}_{file.filename}"
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)

    title = file.filename.rsplit(".", 1)[0]
    repo = Audio_Repo(db)
    
    tag_names = [t.strip() for t in tags.split(",") if t.strip()] if tags.strip() else []
    
    audio_db = repo.create_audio(Audio_Create(
        title=title,
        description=None,
        file_path=file_location,
    ))
    
    for tag_name in tag_names:
        tag = db.query(Tag).filter(Tag.name.ilike(tag_name)).first()
        if not tag:
            tag = Tag(name=tag_name.strip().lower())
            db.add(tag)
            db.flush()
        if tag not in audio_db.tags:
            audio_db.tags.append(tag)
    db.commit()
    db.refresh(audio_db)
    
    return _build_audio_view(audio_db)

@router.post("/upload_multiple", response_model=list[Audio_View])
async def upload_multiple(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    upload_directory = "uploads/audio"
    os.makedirs(upload_directory, exist_ok=True)
    repo = Audio_Repo(db)
    results = []
    for file in files:
        validate_audio(file.filename)
        file_location = f"{upload_directory}/{uuid.uuid4()}_{file.filename}"
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
        title = file.filename.rsplit(".", 1)[0]
        audio_db = repo.create_audio(Audio_Create(
            title=title, description=None, file_path=file_location
        ))
        db.refresh(audio_db)
        results.append(_build_audio_view(audio_db))
    return results

@router.patch("/{audio_id}", response_model=Audio_View)
def update_audio(
    audio_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    db: Session = Depends(get_db)
):
    audio = db.query(Audio).options(joinedload(Audio.tags)).filter(Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found")
    if title is not None:
        audio.title = title
    if description is not None:
        audio.description = description
    if tags is not None:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]
        audio.tags.clear()
        for tag_name in tag_names:
            tag = db.query(Tag).filter(Tag.name.ilike(tag_name)).first()
            if not tag:
                tag = Tag(name=tag_name.strip().lower())
                db.add(tag)
                db.flush()
            audio.tags.append(tag)
    db.commit()
    db.refresh(audio)
    return _build_audio_view(audio)

@router.delete("/{audio_id}")
def delete_audio(audio_id: int, db: Session = Depends(get_db)):
    from app.repositories.audio_repo import Audio_Repo
    repo = Audio_Repo(db)
    return repo.delete_audio(audio_id)


@router.get("/stream/{audio_id}")
def stream_audio(audio_id: int, db: Session = Depends(get_db)):
    audio = db.query(Audio).filter(Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found")
    ext = audio.file_path.rsplit(".", 1)[-1].lower()
    media_types = {
        "mp3": "audio/mpeg", "mp4": "audio/mp4", "wav": "audio/wav",
        "ogg": "audio/ogg", "m4a": "audio/mp4", "aac": "audio/aac", "flac": "audio/flac"
    }
    media_type = media_types.get(ext, "audio/mpeg")
    def iterfile():
        with open(audio.file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
    return StreamingResponse(iterfile(), media_type=media_type)