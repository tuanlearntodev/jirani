from importlib.metadata import metadata
from fastapi import UploadFile, HTTPException
from pathlib import Path
import uuid
from typing import Optional
from app.repositories import BookRepo
from app import settings
from app.schemas import BookDetail, BookRead, BookCreate, BookUpload, BookBase, TagCreate
import re
import fitz  # PyMuPDF
import asyncio

class BookService:
    def __init__(self, book_repo: BookRepo):
        self.book_repo = book_repo
        self.cover_path = settings.COVER_DIR
        self.upload_path = settings.UPLOAD_DIR
        self.max_upload_size = settings.MAX_UPLOAD_SIZE
        self.max_cover_size = settings.MAX_COVER_SIZE
        
        # Create upload directories if they don't exist
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.cover_path.mkdir(parents=True, exist_ok=True)
    
    def get_book_by_uid(self, book_uid: str) -> Optional[BookDetail]:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            return None
        return BookDetail.model_validate(book)
    
    
    
    def get_all_books(self) -> list[BookRead]:
        books = self.book_repo.get_all_books()
        return [BookRead.model_validate(book) for book in books]
    
    def search_books(
        self,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        file_type: Optional[str] = None,
        extension: Optional[str] = None
    ) -> list[BookBase]:
        """
        Dynamic search for books with multiple optional filters.
        If no filters are provided, returns all books.
        """
        books = self.book_repo.search_books(
            title=title,
            tags=tags,
            file_type=file_type,
            extension=extension
        )
        return [BookBase.model_validate(book) for book in books]
    
    @staticmethod
    def _file_name_generator(title: str, uid: str, extension: str) -> str:
        """Generate a safe filename from title, UID and extension"""
        clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        
        return f"{clean_title}_{uid}.{extension}"
    def _convert_epub_to_pdf(self, epub_path: Path, pdf_path: Path) -> bool:
        try:
            doc = fitz.open(str(epub_path))
            # convert_to_pdf() returns bytes of a PDF
            pdf_bytes = doc.convert_to_pdf()
            doc.close()
            
            with open(str(pdf_path), "wb") as f:
                f.write(pdf_bytes)
            
            print(f"EPUB converted to PDF: {pdf_path.exists()}")
            return True
        except Exception as e:
            print(f"EPUB to PDF failed: {e}")
            return False
    
    async def upload_book(self, metadata: BookUpload, file: UploadFile, cover: Optional[UploadFile] = None) -> BookBase:
        """Upload book and cover with validation and error handling"""
        if not metadata.title or not metadata.title.strip():
            # Get filename without extension: "lesson_1.pdf" -> "lesson_1"
            raw_name = Path(file.filename).stem 
            # Replace underscores/dashes with spaces and capitalize for a "clean" look
            metadata.title = raw_name.replace('_', ' ').replace('-', ' ').title().strip()
        # Validate file parameter
        if not file:
            raise HTTPException(status_code=400, detail="Book file is required")
        if not file.filename:
            raise HTTPException(status_code=400, detail="Book filename is required")
        
        # Validate file extension
        if '.' not in file.filename:
            raise HTTPException(status_code=400, detail="Book file must have an extension")
        
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '.{file_extension}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Read and validate book file header
        file_header = await file.read(8192)  # Read first 8KB for validation
        if len(file_header) == 0:
            raise HTTPException(status_code=400, detail="Book file is empty")
        
        # Validate book file content type from header
        self._validate_book_content(file_header, file_extension)
        
        # Generate unique ID and filename
        book_uid = str(uuid.uuid4())[:8]
        file_name = self._file_name_generator(metadata.title, book_uid, file_extension)
        file_path = self.upload_path / file_name
        
        # Variables for cleanup
        saved_file_path = None
        saved_cover_path = None
        
        try:
            print("1. starting file save")
            # Save book file while checking size
            total_size = len(file_header)
            with file_path.open("wb") as buffer:
                # Write the header we already read
                buffer.write(file_header)
                
                # Stream the rest of the file in chunks
                while True:
                    chunk = await file.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > self.max_upload_size:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File too large ({total_size / (1024*1024):.2f}MB). Max: {self.max_upload_size / (1024*1024):.0f}MB"
                        )
                    buffer.write(chunk)
            
            saved_file_path = file_path
            print("2. file saved")

            # Handle cover upload if provided
            if cover and cover.filename:
                print("3a manual cover branch")
                # Validate cover extension
                if '.' not in cover.filename:
                    raise HTTPException(status_code=400, detail="Cover file must have an extension")
                
                cover_extension = cover.filename.split('.')[-1].lower()
                if cover_extension not in settings.ALLOWED_IMAGE_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid cover type '.{cover_extension}'. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}"
                    )
                
                # Read and validate cover header
                cover_header = await cover.read(8192)  # Read first 8KB
                if len(cover_header) == 0:
                    raise HTTPException(status_code=400, detail="Cover file is empty")
                
                # Validate cover content type
                self._validate_image_content(cover_header, cover_extension)
                
                # Save cover file while checking size
                cover_name = f"{book_uid}.{cover_extension}"
                cover_path = self.cover_path / cover_name
                total_cover_size = len(cover_header)
                
                with cover_path.open("wb") as buffer:
                    # Write the header we already read
                    buffer.write(cover_header)
                    
                    # Stream the rest of the file
                    while True:
                        chunk = await cover.read(8192)
                        if not chunk:
                            break
                        total_cover_size += len(chunk)
                        if total_cover_size > self.max_cover_size:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Cover too large ({total_cover_size / (1024*1024):.2f}MB). Max: {self.max_cover_size / (1024*1024):.0f}MB"
                            )
                        buffer.write(chunk)
                
                saved_cover_path = cover_path
            else: 
                cover_name = f"{book_uid}.jpg"
                gen_cover_path = self.cover_path / cover_name
                await asyncio.get_event_loop().run_in_executor(
                    None, self._generate_thumbnail, file_path, gen_cover_path, file_extension
                )
                saved_cover_path = gen_cover_path

                if file_extension == "epub":
                    pdf_name = file_name.replace(".epub", ".pdf")
                    pdf_path = self.upload_path / pdf_name
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._convert_epub_to_pdf, file_path, pdf_path
                    )
            
            extracted_tags = []
            if file_extension == "epub":
                extracted_tags = self._extract_epub_tags(file_path)
            all_tag_names = {t.name.lower(): t for t in metadata.tags}
            for t_name in extracted_tags:
                if t_name.lower() not in all_tag_names:
                    all_tag_names[t_name.lower()] = TagCreate(name=t_name)
            
            final_tags = list(all_tag_names.values())
            # Create book data for database
            book_data = BookCreate(
                title=metadata.title,
                uid=book_uid,
                file_type=file.content_type or f"application/{file_extension}",
                extension=file_extension,
                file_path=file_name,  # Store relative path, not absolute
                cover_path=cover_name,  # Store relative path, not absolute
                tags=final_tags,
            )
            
            # Save to database
            created_book = self.book_repo.create_book(book_data)
            return BookBase.model_validate(created_book)
            
        except HTTPException:
            # Clean up uploaded files on validation error
            if saved_file_path and saved_file_path.exists():
                saved_file_path.unlink()
            if saved_cover_path and saved_cover_path.exists():
                saved_cover_path.unlink()
            raise
        except Exception as e:
            # Clean up uploaded files on any error
            if saved_file_path and saved_file_path.exists():
                saved_file_path.unlink()
            if saved_cover_path and saved_cover_path.exists():
                saved_cover_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload book: {str(e)}"
            )
    
    async def update_book(self, book_uid: str, metadata: BookUpload, cover: Optional[UploadFile] = None) -> BookBase:
        existing_book = self.book_repo.get_book_by_uid(book_uid)
        if not existing_book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        # Update title if provided
        if metadata.title and metadata.title.strip():
            existing_book.title = metadata.title.strip() 
       
        
        # Handle cover update if provided
        if cover and cover.filename:
            # Delete old cover image if it exists
            if existing_book.cover_path:
                old_cover_path = self.cover_path / existing_book.cover_path
                if old_cover_path.exists():
                    try:
                        old_cover_path.unlink()
                    except Exception as e:
                        print(f"Warning: Failed to delete old cover: {e}")
            
            # Validate cover extension
            if '.' not in cover.filename:
                raise HTTPException(status_code=400, detail="Cover file must have an extension")
            
            cover_extension = cover.filename.split('.')[-1].lower()
            if cover_extension not in settings.ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid cover type '.{cover_extension}'. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}"
                )
            
            # Read and validate cover header
            cover_header = await cover.read(8192)  # Read first 8KB
            if len(cover_header) == 0:
                raise HTTPException(status_code=400, detail="Cover file is empty")
            
            # Validate cover content type
            self._validate_image_content(cover_header, cover_extension)
            
            # Save new cover file while checking size
            cover_name = f"{book_uid}.{cover_extension}"
            cover_path = self.cover_path / cover_name
            total_cover_size = len(cover_header)
            
            with cover_path.open("wb") as buffer:
                # Write the header we already read
                buffer.write(cover_header)
                
                # Stream the rest of the file
                while True:
                    chunk = await cover.read(8192)
                    if not chunk:
                        break
                    total_cover_size += len(chunk)
                    if total_cover_size > self.max_cover_size:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cover too large ({total_cover_size / (1024*1024):.2f}MB). Max: {self.max_cover_size / (1024*1024):.0f}MB"
                        )
                    buffer.write(chunk)
            
            existing_book.cover_path = cover_name
        if metadata.tags is not None:
            all_tag_names = {t.name.lower(): t for t in metadata.tags}
            final_tags = list(all_tag_names.values())
        else:
            final_tags = [TagCreate(name=t.name) for t in existing_book.tags]
        book_updated = BookCreate(
            title=existing_book.title,  
            uid=existing_book.uid,
            file_type=existing_book.file_type,
            extension=existing_book.extension,
            file_path=existing_book.file_path,
            cover_path=existing_book.cover_path,
            tags=final_tags
        )
        # Save updates to database
        try:    
            updated_book = self.book_repo.update_book(book_uid, book_updated)
            return BookBase.model_validate(updated_book)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update book: {str(e)}"
            )
            
            
    def delete_book(self, book_uid: str) -> None:
        existing_book = self.book_repo.get_book_by_uid(book_uid)
        if not existing_book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        # Delete book file
        book_path = self.upload_path / existing_book.file_path
        if book_path.exists():
            try:
                book_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete book file: {e}")
        
        # Delete cover file
        if existing_book.cover_path:
            cover_path = self.cover_path / existing_book.cover_path
            if cover_path.exists():
                try:
                    cover_path.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete cover file: {e}")
        
        # Delete from database
        try:
            self.book_repo.delete_book(book_uid)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete book: {str(e)}"
            )
    
    def _validate_book_content(self, content: bytes, extension: str):
        """Validate book file content matches its extension"""
        # Check PDF signature
        if extension == "pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=400,
                    detail="File does not appear to be a valid PDF"
                )
        # Check EPUB signature (it's a ZIP file)
        elif extension == "epub":
            if not content.startswith(b"PK\x03\x04"):
                raise HTTPException(
                    status_code=400,
                    detail="File does not appear to be a valid EPUB"
                )
    
    def _validate_image_content(self, content: bytes, extension: str):
        image_signatures = {
            "jpg": b"\xff\xd8\xff",
            "jpeg": b"\xff\xd8\xff",
            "png": b"\x89PNG\r\n\x1a\n",
            "webp": b"RIFF" # WEBP starts with RIFF then WEBP at offset 8
        }
        
        sig = image_signatures.get(extension)
        if sig and not content.startswith(sig):
            raise HTTPException(
                status_code=400,
                detail=f"File does not appear to be a valid {extension.upper()} image"
            )
            
    def _generate_thumbnail(self, book_path: Path, output_path: Path, extension: str) -> bool:
        print(f"THUMBNAIL INPUT: {book_path} | exists={book_path.exists()}")
        print(f"THUMBNAIL OUTPUT: {output_path}")
        try:
            doc = fitz.open(str(book_path))

            if extension == "pdf":
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
                pix.save(str(output_path))
                doc.close()
                print(f"THUMBNAIL SAVED: {output_path.exists()}")
                return True
            elif extension == "epub":
                doc.close()
                import zipfile
                import xml.etree.ElementTree as ET
                import re as _re

                def strip_ns(tag):
                    return tag.split("}")[-1].lower() if "}" in tag else tag.lower()

                cover_bytes = None

                with zipfile.ZipFile(str(book_path), 'r') as z:
                    names = z.namelist()

                    opf_path = None
                    if "META-INF/container.xml" in names:
                        container = ET.fromstring(z.read("META-INF/container.xml"))
                        for elem in container.iter():
                            if strip_ns(elem.tag) == "rootfile":
                                opf_path = elem.get("full-path")
                                break

                    if opf_path and opf_path in names:
                        opf_dir = "/".join(opf_path.split("/")[:-1])
                        opf = ET.fromstring(z.read(opf_path))

                        cover_id = None
                        cover_href = None

                        for meta in opf.iter():
                            if strip_ns(meta.tag) == "meta":
                                if meta.get("name", "").lower() == "cover":
                                    cover_id = meta.get("content")
                                    break

                        for item in opf.iter():
                            if strip_ns(item.tag) == "item":
                                if "cover-image" in item.get("properties", ""):
                                    cover_href = item.get("href")
                                    print(f"DEBUG: found via properties=cover-image: {cover_href}")
                                    break
                                if cover_id and item.get("id") == cover_id:
                                    cover_href = item.get("href")
                                    print(f"DEBUG: found via cover_id match: {cover_href}")
                                    break

                        if cover_href:
                            full_cover_path = f"{opf_dir}/{cover_href}".replace("\\", "/")
                            print(f"DEBUG: full_cover_path: {full_cover_path}, in names: {full_cover_path in names}")

                            if full_cover_path in names:
                                content = z.read(full_cover_path)
                                if full_cover_path.endswith(('.xhtml', '.html', '.htm')):
                                    match = _re.search(rb'<img[^>]+src=["\']([^"\']+)["\']', content, _re.IGNORECASE)
                                    if match:
                                        img_src = match.group(1).decode()
                                        xhtml_dir = "/".join(full_cover_path.split("/")[:-1])
                                        img_path = f"{xhtml_dir}/{img_src}".replace("\\", "/")
                                        parts = img_path.split("/")
                                        resolved = []
                                        for p in parts:
                                            if p == "..":
                                                if resolved:
                                                    resolved.pop()
                                            else:
                                                resolved.append(p)
                                        img_path = "/".join(resolved)
                                        if img_path in names:
                                            cover_bytes = z.read(img_path)
                                            print(f"DEBUG: found cover via xhtml img: {img_path}")
                                else:
                                    cover_bytes = content
                                    print(f"DEBUG: found cover via manifest direct image: {full_cover_path}")

                        if not cover_bytes:
                            for ref in opf.iter():
                                if strip_ns(ref.tag) == "reference":
                                    if ref.get("type", "").lower() == "cover":
                                        guide_href = ref.get("href", "")
                                        full_path = f"{opf_dir}/{guide_href}".replace("\\", "/")
                                        if full_path in names:
                                            content = z.read(full_path)
                                            if full_path.endswith(('.xhtml', '.html', '.htm')):
                                                match = _re.search(rb'<img[^>]+src=["\']([^"\']+)["\']', content, _re.IGNORECASE)
                                                if match:
                                                    img_src = match.group(1).decode()
                                                    xhtml_dir = "/".join(full_path.split("/")[:-1])
                                                    img_path = f"{xhtml_dir}/{img_src}".replace("\\", "/")
                                                    parts = img_path.split("/")
                                                    resolved = []
                                                    for p in parts:
                                                        if p == "..":
                                                            if resolved:
                                                                resolved.pop()
                                                        else:
                                                            resolved.append(p)
                                                    img_path = "/".join(resolved)
                                                    if img_path in names:
                                                        cover_bytes = z.read(img_path)
                                                        print(f"DEBUG: found cover via guide xhtml: {img_path}")
                                        break

                    # Fallback: cover in filename
                    if not cover_bytes:
                        for name in names:
                            lower = name.lower()
                            if any(lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                                if any(k in lower for k in ['cover', 'front', 'thumb']):
                                    cover_bytes = z.read(name)
                                    print(f"DEBUG: found cover by filename: {name}")
                                    break

                    # Fallback: first image
                    if not cover_bytes:
                        for name in names:
                            lower = name.lower()
                            if any(lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                                cover_bytes = z.read(name)
                                print(f"DEBUG: using first image found: {name}")
                                break

                if cover_bytes:
                    with open(output_path, "wb") as f:
                        f.write(cover_bytes)
                    print(f"DEBUG: cover saved: {output_path.exists()}")
                    return True

                print("DEBUG: no image found, rendering first page")
                doc = fitz.open(str(book_path))
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
                pix.save(str(output_path))
                doc.close()
                return True
                        

        except Exception as e:
            print(f"Thumbnail extraction failed: {e}")
            return False
                            
                
        
    def _extract_epub_tags(self, book_path: Path) -> list[str]:
        """Extracts subjects/tags from EPUB metadata."""
        try:
            doc = fitz.open(str(book_path))
            # Get 'subject' string: "History, Africa, Economy"
            subjects = doc.metadata.get("subject", "")
            doc.close()
            
            if subjects:
                # Split by comma or semicolon and clean up whitespace
                return [t.strip() for t in re.split(r'[,;]+', subjects) if t.strip()]
            return []
        except Exception as e:
            print(f"Tag extraction failed: {e}")
            return []
        