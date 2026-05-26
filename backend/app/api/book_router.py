from pathlib import Path
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import settings
from app.services.book_service import BookService
from app.repositories.book_repo import BookRepo
from app.schemas import BookUpload, BookBase
from app.schemas.tag_schema import TagCreate

router = APIRouter(prefix="/books", tags=["books"])
BOOK_STREAM_CHUNK_SIZE = 1024 * 256  # 256KB

def get_book_service(db: Session = Depends(get_db)) -> BookService:
    book_repo = BookRepo(db)
    return BookService(book_repo)


def _get_book_file_path(db: Session, book_uid: str) -> Path:
    book = BookRepo(db).get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.extension.lower() not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported book format")

    file_path = settings.UPLOAD_DIR / book.file_path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found at {file_path}")

    return file_path


def _iter_file_chunks(file_path: Path, chunk_size: int = BOOK_STREAM_CHUNK_SIZE) -> Iterator[bytes]:
    with file_path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            yield chunk

@router.post("/upload", response_model=BookBase)
async def upload_new_book(
    title: Optional[str] = Form(None),
    tags: str = Form(""),
    file: UploadFile = File(...),
    book_service: BookService = Depends(get_book_service)
):
    print("router hit")
    try:
        tag_list = []
        if tags.strip():
            tag_list = [TagCreate(name=t.strip()).model_dump() for t in tags.split(",") if t.strip()]
        metadata = BookUpload(title=title, tags=tag_list)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tags format: {str(e)}")

    return await book_service.upload_book(
        metadata=metadata,
        file=file,
    )

@router.get("/search/", response_model=list[BookBase])
async def search_books(
    title: Optional[str] = Query(None, description="Search by book title (case-insensitive, partial match)"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    file_type: Optional[str] = Query(None, description="Filter by file type (e.g., epub, pdf)"),
    extension: Optional[str] = Query(None, description="Filter by file extension"),
    book_service: BookService = Depends(get_book_service)
):
    """
    Dynamic search endpoint for books with multiple optional filters.
    All parameters are optional - if none provided, returns all books.
    """
    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    return book_service.search_books(
        title=title,
        tags=tag_list,
        file_type=file_type,
        extension=extension
    )

@router.get("/{book_uid}/epub")
def serve_epub(book_uid: str, db: Session = Depends(get_db)):
    book = BookRepo(db).get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    file_path = settings.UPLOAD_DIR / book.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'inline; filename="{book.file_path}"'}
    )

@router.get("/{book_uid}/stream")
async def stream_book(
    book_uid: str,
    db: Session = Depends(get_db)
):
    file_path = _get_book_file_path(db, book_uid)
    extension = file_path.suffix.lower().lstrip(".")

    media_types = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
    }
    media_type = media_types.get(extension, "application/octet-stream")

    return StreamingResponse(
        _iter_file_chunks(file_path),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
            "Content-Length": str(file_path.stat().st_size),
        },
    )

@router.get("/{book_uid}", response_model=BookBase)
async def get_book_details(
    book_uid: str,
    book_service: BookService = Depends(get_book_service)
):
    """Get book details by UID."""
    book = book_service.get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.put("/{book_uid}", response_model=BookBase)
async def update_book(
    book_uid: str,
    title: Optional[str] = Form(None),
    tags: str = Form(""),
    cover: Optional[UploadFile] = File(None),
    book_service: BookService = Depends(get_book_service)
):
    """Teacher endpoint to update book metadata and optional cover."""
    # Convert tags_json string back to list for the schema
    try:
        tag_list = []
        if tags.strip():
            # Create TagCreate objects and convert to dict for BookUpload
            tag_list = [TagCreate(name=t.strip()).model_dump() for t in tags.split(",") if t.strip()]

        metadata = BookUpload(title=title, tags=tag_list)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tags format: {str(e)}")

    return await book_service.update_book(book_uid, metadata, cover)

@router.delete("/{book_uid}", status_code=204)
async def delete_book(
    book_uid: str,
    book_service: BookService = Depends(get_book_service)
):
    """Teacher endpoint to delete a book by UID."""
    try:
        book_service.delete_book(book_uid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return

@router.get("/{book_uid}/read")
def read_book(book_uid: str, db: Session = Depends(get_db)):
    book = BookRepo(db).get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.extension == "epub":
        # Look for the converted PDF
        pdf_name = book.file_path.rsplit(".", 1)[0] + ".pdf"
        file_path = settings.UPLOAD_DIR / pdf_name
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Converted PDF not found — try re-uploading the EPUB")
    else:
        file_path = settings.UPLOAD_DIR / book.file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {file_path}")

    def iterfile():
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"}
    )



