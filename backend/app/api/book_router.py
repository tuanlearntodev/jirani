from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.schemas import BookUpload, TagCreate
from app.schemas.book_schema import BookRead, BookSearchCriteria, BookUpdate, Page
from app.services.book_errors import BookAlreadyExists, BookNotFound, InvalidBookFile
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader

router = APIRouter(prefix="/books", tags=["books"])


def get_book_service(db: Session = Depends(get_db)) -> BookService:
    return BookService(
        book_repo=BookRepo(db),
        validator=ContentValidator(),
        storage=BookFileStorage(),
        epub_reader=EpubMetadataReader(),
        cover_generator=CoverGenerator(),
        author_repo=AuthorRepo(db),
        level_repo=LevelRepo(db),
        genre_repo=GenreRepo(db),
    )


@router.post("/upload", response_model=BookRead)
async def upload_book(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    author: str | None = Form(None),
    level: str | None = Form(None),
    genre: str | None = Form(None),
    language: str | None = Form(None),
    tags: str | None = Form(None),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> BookRead:
    try:
        tag_list = [
            TagCreate(name=t.strip()) for t in (tags or "").split(",") if t.strip()
        ]
        metadata = BookUpload(
            title=title,
            author=author,
            level=level,
            genre=genre,
            language=language,
            tags=tag_list,
        )

        data = await file.read()
        book_read = svc.create_from_upload(
            metadata, file.filename or "", data, file.content_type or ""
        )
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except InvalidBookFile as exc:
        raise HTTPException(status_code=400, detail="Invalid book file") from exc
    except BookAlreadyExists as exc:
        raise HTTPException(status_code=409, detail="Book already exists") from exc
    except (IntegrityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid book data") from exc
    return book_read


@router.get("/", response_model=Page[BookRead])
def list_books(
    title: str | None = Query(None),
    author: str | None = Query(None),
    level: str | None = Query(None),
    genre: str | None = Query(None),
    language: str | None = Query(None),
    tags: str | None = Query(None),
    extension: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> Page[BookRead]:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    criteria = BookSearchCriteria(
        title=title,
        author=author,
        level=level,
        genre=genre,
        language=language,
        tags=tag_list,
        extension=extension,
    )
    return svc.search(criteria, limit=limit, offset=offset)


@router.get("/{book_uid}/stream")
def stream_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> Response:
    try:
        media_path, media_type = svc.resolve_stream(book_uid)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/books/{quote(media_path.name)}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{book_uid}", response_model=BookRead)
def get_book_details(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> BookRead:
    book = svc.get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.put("/{book_uid}", response_model=BookRead)
def update_book(
    book_uid: str,
    title: str | None = Form(None),
    author: str | None = Form(None),
    level: str | None = Form(None),
    genre: str | None = Form(None),
    language: str | None = Form(None),
    tags: str | None = Form(None),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> BookRead:
    try:
        tag_list = (
            [TagCreate(name=t.strip()) for t in tags.split(",") if t.strip()]
            if tags
            else None
        )
        metadata = BookUpdate(
            title=title,
            author=author,
            level=level,
            genre=genre,
            language=language,
            tags=tag_list,
        )
        return svc.update_book(book_uid, metadata)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except (IntegrityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid book data") from exc


@router.delete("/{book_uid}", status_code=204)
def delete_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> Response:
    try:
        svc.delete_book(book_uid)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    return Response(status_code=204)
