# Book Refactor Implementation Plan (revision of 2026-07-03)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the book feature refactor — streaming, epub + pdf CRUD, extensible search — on PostgreSQL, fixing the four Critical defects found in review of the 2026-07-03 plan.

**Architecture:** Five focused service modules replace the 605-line `BookService` god class; a SQLAlchemy 2.0 `Mapped[]` model with JSONB `metadata_`; a `BookSearchCriteria` object driving a dynamic query builder with `selectinload` + `tags.any()` + explicit `ORDER BY`; a single RFC 7233 Range-aware streaming endpoint; `RoleChecker` on every endpoint.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests), PyMuPDF, uv, pytest/httpx, ruff, mypy.

**Governing design:** `docs/superpowers/specs/2026-08-16-book-refactor-design.md`. Read it first. This plan implements that spec; where they appear to disagree, the spec wins.

## Global Constraints

Every task implicitly includes all of the following. Exact values copied from the spec.

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; no `docker compose up -d db` needed for tests
- `ruff check` with `--ignore B008` on changed files; `mypy --strict` on changed files only, against the measured baseline (103 errors / 24 files). Log pre-existing failures in STATE.md; do not fix unrelated files
- Commit after every task; message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- Never delete a failing test to make the suite pass — fix the underlying logic (AGENTS.md)
- After the final task, run `graphify update .` (AST-only)
- **Locked decisions:** tag filtering is **OR**; `metadata_` uses **containment (`@>`)**; `cover_url` lives on **`BookRead` only**; the `file_type` hotfix runs first (Task 0)
- **Prerequisites (external, not tasks here):** hygiene S1 (creates `backend/app/tests/__init__.py`; changes `from app import settings` → `from app.config import settings`) and hygiene S5 (Alembic). Neither blocks Tasks 0–4. Only the settings import path in Tasks 2 and 5 is affected — both forms are stated where relevant.

## Test Harness Reference

Tests use the committed fixtures at `backend/app/tests/conftest.py` (`361bb48`): `db` (a `Session`), `client` (a `TestClient`), `setup_paths`, plus helpers `setup_admin`/`login`/`auth_headers`. Two documented traps:

- Call `db.expire_all()` before reading via `db` after a write through `client` — the long-lived session's identity map otherwise returns stale objects.
- Never add `backend/app/tests/__init__.py` by hand. It makes `app.tests.conftest` a package import, which triggers `app/__init__.py`'s eager `from .database import ...` at collection time and builds the engine from the default `DATABASE_URL` before the container starts. Hygiene S1 handles this deliberately.

## File Structure Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/services/book_errors.py` | Create | `BookError` base; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed` |
| `backend/app/services/content_validator.py` | Create | `validate(bytes, filename) -> str` (extension); raises `InvalidBookFile` |
| `backend/app/services/book_file_storage.py` | Create | `save(bytes, filename, uid) -> str`; `delete(rel_path) -> None`; `resolve(rel_path) -> Path` with UPLOAD_DIR containment |
| `backend/app/services/epub_metadata_reader.py` | Create | `read(path) -> BookMetadata \| None` |
| `backend/app/services/cover_generator.py` | Create | `generate(src, dest) -> bool`; returns `False` on failure, never raises |
| `backend/app/services/book_service.py` | Rewrite | Thin orchestration over the four modules + `BookRepo` |
| `backend/app/repositories/book_repo.py` | Rewrite | `search(criteria) -> Page[BookRead]`; 2.0 `select()` |
| `backend/app/api/book_router.py` | Rewrite | `RoleChecker` + Range streaming + pagination + error mapping |
| `backend/app/schemas/book_schema.py` | Modify | Move `cover_url` from `BookBase` to `BookRead` |
| `backend/app/schemas/book_schema.py` (`BookUpload`) | — | Unchanged; reused by the router |
| `backend/app/tests/test_book_search.py` | Create | C1 search correctness + pagination probes |
| `backend/app/tests/test_book_stream.py` | Create | C3 Range cases + C4 traversal |
| `backend/app/tests/test_book_upload.py` | Create | Happy path + rejection |

---

### Task 0: `file_type` hotfix + `cover_url` move

**Files:**
- Modify: `backend/app/repositories/book_repo.py:103-136`
- Modify: `backend/app/services/book_service.py:36-50,223-231,323-331`
- Modify: `backend/app/schemas/book_schema.py:12-41`
- Test: `backend/app/tests/test_book_search.py`

**Interfaces:**
- Consumes: existing `BookRepo`, `BookService`, `Book` model, `BookCreate`/`BookRead` schemas, the `db` fixture
- Produces:
  - `BookRepo.search_books(title, tags, book_type, extension) -> list[Book]` — the `file_type` parameter renamed to `book_type`, mapping to `Book.book_type` (this method is fully replaced in Task 5; here it only gets the bug fixed in place)
  - `BookService.search_books(title, tags, book_type, extension) -> list[BookBase]` — `file_type` parameter removed
  - `BookRead.cover_url` present; `BookBase`/`BookCreate` without `cover_url`

**Why:** `Book.file_type` does not exist — the column is `book_type`. Three live sites raise `AttributeError` (500) today, and a fourth threads the dead param through the service signature. Fix the tree before refactoring, rather than carrying shipped 500s through six more commits.

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_search.py`:

```python
"""Red-first probe for the file_type -> book_type fix (C-adjacent, plan Task 0)."""

from app.models import Book, Tag
from app.repositories import BookRepo


def _seed_book(db, *, uid: str, book_type: str) -> None:
    db.add(
        Book(
            uid=uid,
            title=f"Title {uid}",
            book_type=book_type,
            extension="pdf",
            file_path=f"{uid}.pdf",
            metadata_={},
        )
    )
    db.commit()


def test_search_by_book_type_does_not_raise(db) -> None:
    """Searching by book_type must not touch the removed file_type attribute."""
    _seed_book(db, uid="bk0001", book_type="application/pdf")
    _seed_book(db, uid="bk0002", book_type="application/epub+zip")

    result = BookRepo(db).search_books(book_type="pdf")

    assert [b.uid for b in result] == ["bk0001"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_search.py -v
```

Expected: FAIL with `AttributeError: type object 'Book' has no attribute 'file_type'`. (Docker daemon required — the harness starts a `postgres:16-alpine` container.)

- [ ] **Step 3: Rename the parameter and map to `book_type` in the repo**

In `backend/app/repositories/book_repo.py`, change the signature (line 103-109) and the filter (line 122-123):

```python
    def search_books(
        self,
        title: str | None = None,
        tags: list[str] | None = None,
        book_type: str | None = None,
        extension: str | None = None,
    ) -> list[Book]:
```

```python
        if book_type:
            filters.append(Book.book_type.ilike(f"%{book_type}%"))
```

- [ ] **Step 4: Move `cover_url` off `BookBase`**

In `backend/app/schemas/book_schema.py`: delete the `@computed_field` block (lines 24-29) from `BookBase`, and add it to `BookRead` (after line 41). `cover_path` stays on `BookBase` — only the computed URL moves. Add the import note: `computed_field` and `Field` are already imported at line 5.

```python
class BookRead(BookBase):
    id: int
    created_at: datetime
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    @computed_field
    @property
    def cover_url(self) -> str | None:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"
```

- [ ] **Step 5: Fix the service call sites**

In `backend/app/services/book_service.py`:

- Line 36-41: remove the `file_type: str | None = None,` parameter from `search_books` and the `file_type=file_type` kwarg at line 48.
- Line 223-231 (`book_data = BookCreate(...)`): change `file_type=file.content_type or f"application/{file_extension}",` to `book_type=file.content_type or f"application/{file_extension}",`.
- Line 323-331 (`book_updated = BookCreate(...)`): change `file_type=existing_book.file_type,` to `book_type=existing_book.book_type,`.

- [ ] **Step 6: Drop the now-dead `cover_url` exclusion**

In `backend/app/repositories/book_repo.py`, lines 23 and 77: with `cover_url` no longer on `BookCreate`, the exclusion is unnecessary. Change both:

```python
        book_dict = book_create.model_dump(exclude={"tags"})
```

```python
        book_dict = book_update.model_dump(exclude={"tags"})
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
cd backend && uv run pytest app/tests/test_book_search.py -v
```

Expected: PASS.

- [ ] **Step 8: Type-check and lint the changed files**

```bash
cd backend && uv run mypy app/repositories/book_repo.py app/services/book_service.py app/schemas/book_schema.py --strict
cd backend && uv run ruff format app/repositories/book_repo.py app/services/book_service.py app/schemas/book_schema.py app/tests/test_book_search.py
cd backend && uv run ruff check app/repositories/book_repo.py app/services/book_service.py app/schemas/book_schema.py app/tests/test_book_search.py --ignore B008
```

Expected: no new mypy errors (baseline is 103 across 24 files; these files should contribute 0 new). Ruff clean after format.

- [ ] **Step 9: Commit**

```bash
cd backend && git add app/repositories/book_repo.py app/services/book_service.py app/schemas/book_schema.py app/tests/test_book_search.py
git commit -m "fix: map search file_type to book_type; move cover_url to BookRead"
```

---

### Task 1: `book_errors.py` + `ContentValidator`

**Files:**
- Create: `backend/app/services/book_errors.py`
- Create: `backend/app/services/content_validator.py`
- Test: `backend/app/tests/test_book_validator.py`

**Interfaces:**
- Consumes: `app.config.settings` (`ALLOWED_EXTENSIONS: set[str]`, `MAX_UPLOAD_SIZE: int`)
- Produces:
  - `BookError(Exception)` with `detail: str` and a per-class `default_detail`
  - `BookNotFound(BookError)`, `InvalidBookFile(BookError)`, `BookAlreadyExists(BookError)`, `CoverGenerationFailed(BookError)`
  - `ContentValidator.validate(file_bytes: bytes, filename: str) -> str` — returns the lowercase extension; raises `InvalidBookFile` on empty bytes, disallowed extension, magic-byte mismatch, or size over `MAX_UPLOAD_SIZE`

**Why:** The domain exception hierarchy and the upload gate are the two leaves every later module depends on. Both are pure Python — no HTTP, no `open()`, no DB — so they are unit-testable in isolation and the tree stays green.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_book_validator.py`:

```python
"""Red-first tests for ContentValidator (plan Task 1)."""

import pytest

from app.config import settings
from app.services.book_errors import InvalidBookFile
from app.services.content_validator import ContentValidator


def test_empty_file_rejected() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"", "book.pdf")


def test_disallowed_extension_rejected() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"MZ\x90\x00", "malware.exe")


def test_fake_pdf_rejected_by_magic_bytes() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"not a real pdf", "book.pdf")


def test_oversized_file_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)
    payload = b"%PDF-1.4" + b"\x00" * 8  # 16 bytes > 10-byte cap

    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(payload, "book.pdf")


def test_valid_pdf_stub_accepted() -> None:
    """Validation sniffs magic bytes only — a %PDF- stub is sufficient here."""
    result = ContentValidator().validate(b"%PDF-1.4 stub bytes", "Report.PDF")

    assert result == "pdf"


def test_valid_epub_stub_accepted() -> None:
    result = ContentValidator().validate(b"PK\x03\x04 stub bytes", "book.EPUB")

    assert result == "epub"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_validator.py -v
```

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.book_errors'`. (Docker daemon required — the harness starts a `postgres:16-alpine` container even for these pure-Python tests.)

- [ ] **Step 3: Create the domain exception hierarchy**

Create `backend/app/services/book_errors.py`:

```python
"""Domain exceptions for the book feature.

Pure domain errors — no HTTP types. The router is the sole translator
to HTTP status codes (Invariant 2).
"""


class BookError(Exception):
    """Base class for all book-domain errors."""

    detail: str
    default_detail: str = "Book error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class BookNotFound(BookError):
    default_detail = "Book not found"


class InvalidBookFile(BookError):
    default_detail = "The uploaded file is not a valid book"


class BookAlreadyExists(BookError):
    default_detail = "A book with this identifier already exists"


class CoverGenerationFailed(BookError):
    default_detail = "Could not generate a cover thumbnail"
```

- [ ] **Step 4: Create `ContentValidator`**

Create `backend/app/services/content_validator.py`:

```python
"""Upload gate: is this byte stream an acceptable book?

Pure validation — no HTTP, no open(), no DB. Every guard runs before any
byte reaches disk, so a rejected upload leaves nothing behind.
"""

from app.config import settings
from app.services.book_errors import InvalidBookFile

_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF-",
    "epub": b"PK\x03\x04",
}


class ContentValidator:
    """Validates upload bytes against extension allowlist and magic bytes."""

    def validate(self, file_bytes: bytes, filename: str) -> str:
        """Return the lowercase extension, or raise InvalidBookFile."""
        if not file_bytes:
            raise InvalidBookFile("Book file is empty")

        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise InvalidBookFile(
                f"File too large ({len(file_bytes) / (1024 * 1024):.1f}MB). "
                f"Max: {settings.MAX_UPLOAD_SIZE / (1024 * 1024):.0f}MB"
            )

        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in settings.ALLOWED_EXTENSIONS:
            raise InvalidBookFile(
                f"Invalid file type '.{extension}'. "
                f"Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
            )

        magic = _MAGIC_BYTES[extension]
        if not file_bytes.startswith(magic):
            raise InvalidBookFile(
                f"File does not appear to be a valid {extension.upper()}"
            )

        return extension
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && uv run pytest app/tests/test_book_validator.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/book_errors.py app/services/content_validator.py app/tests/test_book_validator.py
cd backend && uv run ruff check app/services/book_errors.py app/services/content_validator.py app/tests/test_book_validator.py --ignore B008
cd backend && uv run mypy app/services/book_errors.py app/services/content_validator.py --strict
```

Expected: ruff clean after format; mypy reports no errors for these two files (baseline is 103 errors across 24 files — these files must contribute 0 new).

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/services/book_errors.py app/services/content_validator.py app/tests/test_book_validator.py
git commit -m "feat: add book domain errors and ContentValidator upload gate"
```

---

### Task 2: `BookFileStorage` (incl. `resolve()` containment)

**Files:**
- Create: `backend/app/services/book_file_storage.py`
- Test: `backend/app/tests/test_book_storage.py`

**Interfaces:**
- Consumes: `app.config.settings` (`UPLOAD_DIR: Path`, `COVER_DIR: Path`), `app.services.book_errors.BookNotFound`
- Produces:
  - `BookFileStorage.save(file_bytes: bytes, filename: str, uid: str) -> str` — writes under `UPLOAD_DIR`, returns the RELATIVE path (string) to store in the DB
  - `BookFileStorage.delete(rel_path: str) -> None` — best-effort remove from `UPLOAD_DIR`, never raises
  - `BookFileStorage.delete_cover(cover_name: str) -> None` — best-effort remove from `COVER_DIR`, never raises
  - `BookFileStorage.resolve(rel_path: str) -> Path` — resolves under `UPLOAD_DIR`; raises `BookNotFound` if the result escapes `UPLOAD_DIR` or the file is absent (the C4 fix)
  - `BookFileStorage.cover_dir: Path` — read-only accessor for `COVER_DIR` (consumed by Task 5's cover call)

**Why:** `resolve()` centralises path-traversal containment so the router can never open a book file except through the guard. A DB-supplied `file_path` joined naively to `UPLOAD_DIR` escapes via `..` — today the tree is safe only because the write path incidentally strips traversal. One guard, unit-testable in isolation, instead of duplicated per call site.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_book_storage.py`:

```python
"""Red-first tests for BookFileStorage, incl. the C4 containment fix."""

from pathlib import Path

import pytest

from app.config import settings
from app.services.book_errors import BookNotFound
from app.services.book_file_storage import BookFileStorage


@pytest.fixture()
def storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BookFileStorage:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    return BookFileStorage()


def test_resolve_rejects_traversal(storage: BookFileStorage) -> None:
    """C4: a DB-supplied path must not escape UPLOAD_DIR."""
    with pytest.raises(BookNotFound):
        storage.resolve("../../../../etc/passwd")


def test_resolve_within_upload_dir(
    storage: BookFileStorage, tmp_path: Path
) -> None:
    rel = storage.save(b"%PDF-1.4 stub", "My Report.PDF", uid="abc12345")

    resolved = storage.resolve(rel)

    assert resolved == (tmp_path / "books" / rel).resolve()
    assert resolved.exists()


def test_save_round_trip(storage: BookFileStorage, tmp_path: Path) -> None:
    payload = b"%PDF-1.4 round-trip bytes"

    rel = storage.save(payload, "Lesson 1.pdf", uid="bk000001")

    assert not Path(rel).is_absolute()
    assert "/" not in rel and "\\" not in rel
    assert rel.endswith(".pdf")
    assert "bk000001" in rel
    assert (tmp_path / "books" / rel).read_bytes() == payload


def test_save_sanitizes_filename(storage: BookFileStorage) -> None:
    rel = storage.save(b"%PDF-1.4 stub", "../../etc/evil; rm -rf.pdf", uid="deadbeef")

    assert ".." not in rel
    assert "/" not in rel and "\\" not in rel
    assert " " not in rel


def test_delete_missing_file_is_silent(storage: BookFileStorage) -> None:
    storage.delete("never_existed.pdf")  # must not raise


def test_cover_dir_accessor(storage: BookFileStorage, tmp_path: Path) -> None:
    assert storage.cover_dir == tmp_path / "covers"


def test_delete_cover_missing_is_silent(storage: BookFileStorage) -> None:
    storage.delete_cover("never_existed.png")  # must not raise
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_storage.py -v
```

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.book_file_storage'`.

- [ ] **Step 3: Create `BookFileStorage`**

> **Settings import note:** current tree code uses `from app import settings` (`book_service.py:9`); hygiene S1 changes it to `from app.config import settings`. New modules use the S1 form below so S1 does not rewrite them later.

Create `backend/app/services/book_file_storage.py`:

```python
"""Bytes <-> disk, with path-traversal containment (the C4 fix).

The router must never open a book file except through resolve(): a
DB-supplied file_path joined naively to UPLOAD_DIR escapes the directory
via '..'. Centralising the guard here makes it unit-testable in isolation
instead of duplicated per call site.
"""

import logging
import re
from pathlib import Path

from app.config import settings
from app.services.book_errors import BookNotFound

logger = logging.getLogger(__name__)


def safe_filename(filename: str, uid: str) -> str:
    """Sanitise a user-supplied filename and bind it to the book uid."""
    name = Path(filename).name  # drop any directory components
    stem, dot, ext = name.rpartition(".")
    stem = re.sub(r"[^\w\s-]", "", stem).strip().lower()
    stem = re.sub(r"[-\s]+", "_", stem)
    ext = re.sub(r"[^a-z0-9]", "", ext.lower()) if dot else ""
    safe = f"{stem}_{uid}" if stem else uid
    return f"{safe}.{ext}" if ext else safe


class BookFileStorage:
    """Stores book bytes under UPLOAD_DIR and covers under COVER_DIR."""

    def __init__(self) -> None:
        self.upload_dir = settings.UPLOAD_DIR
        self._cover_dir = settings.COVER_DIR

    @property
    def cover_dir(self) -> Path:
        """Where covers live (consumed by Task 5's cover call)."""
        return self._cover_dir

    def save(self, file_bytes: bytes, filename: str, uid: str) -> str:
        """Write bytes under UPLOAD_DIR; return the RELATIVE path for the DB."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        name = safe_filename(filename, uid)
        (self.upload_dir / name).write_bytes(file_bytes)
        return name

    def delete(self, rel_path: str) -> None:
        """Best-effort remove from UPLOAD_DIR; never raises."""
        try:
            target = self.resolve(rel_path)
        except BookNotFound:
            return
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete book file %s", rel_path)

    def delete_cover(self, cover_name: str) -> None:
        """Best-effort remove from COVER_DIR; never raises."""
        try:
            base = self._cover_dir.resolve()
            target = (base / cover_name).resolve()
            if target.is_relative_to(base) and target.is_file():
                target.unlink()
        except OSError:
            logger.warning("Could not delete cover %s", cover_name)

    def resolve(self, rel_path: str) -> Path:
        """Resolve a DB-stored relative path, contained within UPLOAD_DIR.

        Raises BookNotFound if the path escapes UPLOAD_DIR (traversal) or the
        file is absent.
        """
        base = self.upload_dir.resolve()
        resolved = (base / rel_path).resolve()
        if not resolved.is_relative_to(base):
            raise BookNotFound(f"Invalid book file path: {rel_path!r}")
        if not resolved.is_file():
            raise BookNotFound(f"Book file not found: {rel_path!r}")
        return resolved
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && uv run pytest app/tests/test_book_storage.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/book_file_storage.py app/tests/test_book_storage.py
cd backend && uv run ruff check app/services/book_file_storage.py app/tests/test_book_storage.py --ignore B008
cd backend && uv run mypy app/services/book_file_storage.py --strict
```

Expected: ruff clean after format; mypy reports no errors for this file (0 new against the 103-error / 24-file baseline).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/book_file_storage.py app/tests/test_book_storage.py
git commit -m "feat: add BookFileStorage with UPLOAD_DIR traversal containment"
```

---

### Task 3: `EpubMetadataReader`

**Files:**
- Create: `backend/app/services/epub_metadata_reader.py`
- Test: `backend/app/tests/test_book_epub_reader.py`

**Interfaces:**
- Consumes: `pymupdf` (PyMuPDF), stdlib `logging`/`re`/`dataclasses`/`pathlib`. No `app.*` imports — pure leaf.
- Produces:
  - `@dataclass(frozen=True) BookMetadata` — `title: str | None`, `author: str | None`, `language: str | None`, `tags: list[str]`
  - `EpubMetadataReader.read(path: Path) -> BookMetadata | None` — returns `None` on a corrupt or missing file; never raises

**Why:** Replaces the god class's epub-tag logic with a total function whose `None` return lets the service layer (Task 5) own the filename/user-input fallback.

**Naming contract — read carefully:** the dataclass field is **`tags`**, not `subjects`. Task 5b consumes `epub_meta.tags`. (An earlier draft of this plan named it `subjects`; that name is retired to match the shipped dataclass.)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_epub_reader.py`. The fixture builds a real minimal EPUB with `zipfile` (an EPUB is a zip: uncompressed `mimetype` first entry, `META-INF/container.xml` pointing at the OPF, one spine item):

```python
"""Tests for EpubMetadataReader (plan Task 3)."""

import zipfile
from pathlib import Path

from app.services.epub_metadata_reader import BookMetadata, EpubMetadataReader


def _write_minimal_epub(path: Path) -> None:
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Minimal Title</dc:title>
    <dc:creator>Jane Doe</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="uid">urn:uuid:test</dc:identifier>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    chapter = (
        "<?xml version='1.0'?>"
        "<html xmlns='http://www.w3.org/1999/xhtml'>"
        "<body><p>Hello</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", chapter)


def test_read_corrupt_epub_returns_none(tmp_path: Path) -> None:
    bad = tmp_path / "corrupt.epub"
    bad.write_bytes(b"this is not an epub at all")

    assert EpubMetadataReader().read(bad) is None


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    assert EpubMetadataReader().read(tmp_path / "nope.epub") is None


def test_read_extracts_title_and_author(tmp_path: Path) -> None:
    epub = tmp_path / "good.epub"
    _write_minimal_epub(epub)

    meta = EpubMetadataReader().read(epub)

    assert isinstance(meta, BookMetadata)
    assert meta.title == "Minimal Title"
    assert meta.author == "Jane Doe"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_epub_reader.py -v
```

Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.services.epub_metadata_reader'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/epub_metadata_reader.py`. New code imports `pymupdf`, not the `fitz` alias the legacy `book_service.py` uses: only the `pymupdf` package ships a `py.typed` marker, so `import fitz` fails mypy `--strict` as `import-untyped`. The `pymupdf.open` constructor is untyped upstream, so the call site carries a targeted `# type: ignore[no-untyped-call]`.

```python
"""EPUB metadata extraction. Leaf module; Task 5 wires it into BookService."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookMetadata:
    """Metadata harvested from an EPUB. Every field may come back empty."""

    title: str | None
    author: str | None
    language: str | None
    tags: list[str] = field(default_factory=list)


class EpubMetadataReader:
    """Read title/author/language/subjects from an EPUB via PyMuPDF.

    Honest caveat: PyMuPDF's EPUB support is limited — it may surface only
    title/author, dropping dc:language and dc:subject. Empty fields are
    acceptable; the service layer falls back to filename and user input.
    """

    def read(self, path: Path) -> BookMetadata | None:
        """Return the EPUB's metadata, or None if it cannot be parsed."""
        try:
            doc = pymupdf.open(str(path))  # type: ignore[no-untyped-call]
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning("EPUB metadata read failed for %s: %s", path, exc)
            return None
        with doc:
            meta = doc.metadata or {}
        title = meta.get("title") or None
        author = meta.get("author") or None
        language = meta.get("language") or None
        subjects = meta.get("subject") or ""
        tags = [t.strip() for t in re.split(r"[,;]+", subjects) if t.strip()]
        return BookMetadata(title=title, author=author, language=language, tags=tags)
```

Do **not** export it from `app/services/__init__.py` — Task 5 wires the composition; this commit stays a pure addition.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && uv run pytest app/tests/test_book_epub_reader.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/epub_metadata_reader.py app/tests/test_book_epub_reader.py
cd backend && uv run ruff check app/services/epub_metadata_reader.py app/tests/test_book_epub_reader.py --ignore B008
cd backend && uv run mypy app/services/epub_metadata_reader.py --strict
```

Expected: ruff clean after format; mypy clean on this file (0 new errors).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/epub_metadata_reader.py app/tests/test_book_epub_reader.py
git commit -m "feat: add EpubMetadataReader leaf module with EPUB metadata tests"
```

---

### Task 4: `CoverGenerator`

**Files:**
- Create: `backend/app/services/cover_generator.py`
- Test: `backend/app/tests/test_book_cover.py`

**Interfaces:**
- Consumes: `app.config.settings` (`MAX_COVER_SIZE: int`), `pymupdf`, stdlib `zipfile`/`re`/`xml.etree.ElementTree`/`logging`
- Produces:
  - `CoverGenerator.generate(source_path: Path, dest_dir: Path) -> bool` — writes the cover into the `dest_dir` **directory**, named `{source_path.stem}.png` (the stem is the book uid per Task 2's `save`). Returns `True` only when a cover lands within `settings.MAX_COVER_SIZE`; `False` on ANY failure; never raises.

**Why:** Replaces `_generate_thumbnail` with the spec's `-> bool` contract: a stub or corrupt upload degrades to a missing cover, never a failed upload.

**Signature contract — read carefully:** the second parameter is a **directory** (`dest_dir`), and the method derives the filename from `source_path.stem`. Task 5b calls it as `generate(source_path, storage.cover_dir)`. (An earlier draft passed a full file path; that is retired.)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_cover.py`. The happy path builds a **real** one-page PDF in-fixture — stub bytes pass magic-byte validation but are unparseable, so the happy path needs a genuine document:

```python
"""Tests for CoverGenerator (plan Task 4)."""

import zipfile
from pathlib import Path

import pymupdf  # PyMuPDF
import pytest

from app.config import settings
from app.services.cover_generator import CoverGenerator


def _write_real_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello cover")
    doc.save(str(path))
    doc.close()


def _png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2))
    return pix.tobytes("png")


def _write_epub_with_cover(path: Path) -> None:
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Has Cover</dc:title>
    <dc:identifier id="uid">urn:uuid:test</dc:identifier>
    <meta name="cover" content="cover-img"/>
  </metadata>
  <manifest>
    <item id="cover-img" href="images/cover.png" media-type="image/png"/>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    chapter = (
        "<?xml version='1.0'?>"
        "<html xmlns='http://www.w3.org/1999/xhtml'>"
        "<body><p>Hello</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", chapter)
        z.writestr("OEBPS/images/cover.png", _png_bytes())


def test_generate_corrupt_pdf_returns_false(tmp_path: Path) -> None:
    """Stub/corrupt PDF degrades to False and leaves nothing behind."""
    stub = tmp_path / "broken.pdf"
    stub.write_bytes(b"%PDF-1.4 corrupt trailer, unparseable")
    dest = tmp_path / "covers"

    assert CoverGenerator().generate(stub, dest) is False
    assert list(dest.iterdir()) == []


def test_generate_pdf_writes_cover(tmp_path: Path) -> None:
    src = tmp_path / "bk0001.pdf"  # stem is the book uid (Task 2 save contract)
    _write_real_pdf(src)
    dest = tmp_path / "covers"

    assert CoverGenerator().generate(src, dest) is True

    cover = dest / "bk0001.png"
    assert cover.exists()
    assert cover.stat().st_size <= settings.MAX_COVER_SIZE


def test_generate_epub_extracts_embedded_cover(tmp_path: Path) -> None:
    src = tmp_path / "bk0002.epub"
    _write_epub_with_cover(src)
    dest = tmp_path / "covers"

    assert CoverGenerator().generate(src, dest) is True

    assert (dest / "bk0002.png").exists()


def test_generate_epub_without_images_returns_false(tmp_path: Path) -> None:
    src = tmp_path / "bk0003.epub"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("OEBPS/ch1.xhtml", "<html><body><p>text only</p></body></html>")
    dest = tmp_path / "covers"

    assert CoverGenerator().generate(src, dest) is False
    assert list(dest.iterdir()) == []


def test_generate_discards_oversize_cover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_COVER_SIZE", 1)  # any render exceeds it
    src = tmp_path / "bk0004.pdf"
    _write_real_pdf(src)
    dest = tmp_path / "covers"

    assert CoverGenerator().generate(src, dest) is False
    assert list(dest.iterdir()) == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_cover.py -v
```

Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.services.cover_generator'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/cover_generator.py`. Ported from `_generate_thumbnail`: PDF page-0 render at half scale; EPUB OPF-declared cover; XHTML `<img>` unwrap; first-image fallback; `..`-resolving in-archive join. **Deliberately dropped:** the filename-keyword heuristic (subsumed by first-image) and render-the-epub's-first-page (a text page is not a cover; absence is honest). `generate` is the boundary: private helpers may raise, `generate` converts anything to a logged `False`.

```python
"""Cover/thumbnail generation for book uploads. Leaf module."""

import logging
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pymupdf  # PyMuPDF

from app.config import settings

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def _local_name(tag: str) -> str:
    """Strip an XML namespace: ``{ns}item`` -> ``item``."""
    return tag.rpartition("}")[2].lower()


class CoverGenerator:
    """Best-effort cover generation.

    ``generate`` returns ``True`` on success and ``False`` on ANY failure —
    it never raises. A function typed ``-> bool`` must be able to return
    ``False``; a corrupt or stub upload degrades to a missing cover, not a
    failed upload.
    """

    def generate(self, source_path: Path, dest_dir: Path) -> bool:
        """Write a cover for ``source_path`` into the ``dest_dir`` directory.

        The cover is named ``{source_path.stem}.png`` — BookFileStorage names
        book files ``{uid}.{ext}``, so the stem is the book uid.
        """
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            suffix = source_path.suffix.lower()
            if suffix == ".pdf":
                return self._from_pdf(source_path, dest_dir)
            if suffix == ".epub":
                return self._from_epub(source_path, dest_dir)
            logger.warning("No cover strategy for extension %r", suffix)
            return False
        except Exception:
            logger.exception("Cover generation failed for %s", source_path)
            return False

    def _from_pdf(self, source_path: Path, dest_dir: Path) -> bool:
        with pymupdf.open(str(source_path)) as doc:  # type: ignore[no-untyped-call]
            matrix = pymupdf.Matrix(0.5, 0.5)  # type: ignore[no-untyped-call]
            pix = doc.load_page(0).get_pixmap(matrix=matrix)
            dest = dest_dir / f"{source_path.stem}.png"
            pix.save(str(dest))
        return self._keep_if_small_enough(dest)

    def _from_epub(self, source_path: Path, dest_dir: Path) -> bool:
        found = self._extract_epub_cover(source_path)
        if found is None:
            logger.info("No cover image found in %s", source_path)
            return False
        suffix, data = found
        dest = dest_dir / f"{source_path.stem}.png"
        dest.write_bytes(data)
        return self._keep_if_small_enough(dest)

    @staticmethod
    def _keep_if_small_enough(dest: Path) -> bool:
        if dest.stat().st_size > settings.MAX_COVER_SIZE:
            logger.warning("Cover %s exceeds MAX_COVER_SIZE; discarding", dest)
            dest.unlink()
            return False
        return True

    def _extract_epub_cover(self, source_path: Path) -> tuple[str, bytes] | None:
        with zipfile.ZipFile(source_path) as archive:
            names = archive.namelist()
            opf_path = self._find_opf_path(archive, names)
            if opf_path is not None:
                found = self._cover_from_opf(archive, names, opf_path)
                if found is not None:
                    return found
            return self._first_image(archive, names)

    @staticmethod
    def _find_opf_path(archive: zipfile.ZipFile, names: list[str]) -> str | None:
        if "META-INF/container.xml" not in names:
            return None
        root = ET.fromstring(archive.read("META-INF/container.xml"))
        for elem in root.iter():
            if _local_name(elem.tag) == "rootfile":
                full_path = elem.get("full-path")
                return full_path if full_path in names else None
        return None

    def _cover_from_opf(
        self, archive: zipfile.ZipFile, names: list[str], opf_path: str
    ) -> tuple[str, bytes] | None:
        opf_dir = opf_path.rpartition("/")[0]
        root = ET.fromstring(archive.read(opf_path))
        cover_id: str | None = None
        href: str | None = None
        for elem in root.iter():
            if (
                _local_name(elem.tag) == "meta"
                and elem.get("name", "").lower() == "cover"
            ):
                cover_id = elem.get("content")
                break
        for elem in root.iter():
            if _local_name(elem.tag) != "item":
                continue
            if "cover-image" in elem.get("properties", ""):
                href = elem.get("href")
                break
            if cover_id and elem.get("id") == cover_id:
                href = elem.get("href")
                break
        if not href:
            return None
        return self._read_cover_href(archive, names, self._join(opf_dir, href))

    def _read_cover_href(
        self, archive: zipfile.ZipFile, names: list[str], cover_path: str
    ) -> tuple[str, bytes] | None:
        if cover_path not in names:
            return None
        if cover_path.lower().endswith((".xhtml", ".html", ".htm")):
            content = archive.read(cover_path)
            match = re.search(
                rb'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE
            )
            if not match:
                return None
            img_dir = cover_path.rpartition("/")[0]
            img_path = self._join(img_dir, match.group(1).decode())
            return self._read_image(archive, names, img_path)
        return self._read_image(archive, names, cover_path)

    @staticmethod
    def _read_image(
        archive: zipfile.ZipFile, names: list[str], name: str
    ) -> tuple[str, bytes] | None:
        if name not in names:
            return None
        suffix = Path(name).suffix.lower()
        if suffix not in _IMAGE_SUFFIXES:
            return None
        return suffix, archive.read(name)

    @staticmethod
    def _first_image(
        archive: zipfile.ZipFile, names: list[str]
    ) -> tuple[str, bytes] | None:
        for name in names:
            suffix = Path(name).suffix.lower()
            if suffix in _IMAGE_SUFFIXES:
                return suffix, archive.read(name)
        return None

    @staticmethod
    def _join(base: str, rel: str) -> str:
        """Join in-archive paths, resolving ``..`` segments."""
        parts = f"{base}/{rel}".replace("\\", "/").split("/")
        resolved: list[str] = []
        for part in parts:
            if part == "..":
                if resolved:
                    resolved.pop()
            elif part and part != ".":
                resolved.append(part)
        return "/".join(resolved)
```

Do **not** export it from `app/services/__init__.py` — Task 5 wires the composition; this commit stays a pure addition.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && uv run pytest app/tests/test_book_cover.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/cover_generator.py app/tests/test_book_cover.py
cd backend && uv run ruff check app/services/cover_generator.py app/tests/test_book_cover.py --ignore B008
cd backend && uv run mypy app/services/cover_generator.py --strict
```

Expected: ruff clean after format; mypy clean on this file (0 new errors).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/cover_generator.py app/tests/test_book_cover.py
git commit -m "feat: add CoverGenerator leaf module with cover generation tests"
```

---

### Task 5: FUSED rewrite of `BookRepo` + `BookService` + `book_router` (single commit)

**Files:**
- Rewrite: `backend/app/repositories/book_repo.py`
- Rewrite: `backend/app/services/book_service.py`
- Rewrite: `backend/app/api/book_router.py`
- Test (extend): `backend/app/tests/test_book_search.py`
- Test (create): `backend/app/tests/test_book_stream.py`
- Test (create): `backend/app/tests/test_book_upload.py`

**Interfaces:**

Consumes (from Tasks 1–4 — if their shipped signatures differ from this list, stop and reconcile before writing Task 5):
- `app.services.book_errors`: `BookError(Exception)` base; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed`
- `ContentValidator.validate(file_bytes: bytes, filename: str) -> str` — returns the lowercased extension; raises `InvalidBookFile`
- `BookFileStorage.save(file_bytes: bytes, filename: str, uid: str) -> str` — returns the stored **relative** path; `.delete(rel_path) -> None`; `.delete_cover(cover_name) -> None`; `.resolve(rel_path) -> Path` (raises `BookNotFound` on traversal or missing file); `.cover_dir -> Path`
- `EpubMetadataReader.read(path: Path) -> BookMetadata | None` — `BookMetadata` has `title`, `author`, `language`, **`tags: list[str]`**
- `CoverGenerator.generate(source_path: Path, dest_dir: Path) -> bool` — `dest_dir` is a **directory**; never raises
- `app.schemas`: `BookCreate`, `BookRead`, `BookUpload`, `BookSearchCriteria`, `Page`, `TagCreate`
- `app.dependencies.auth.RoleChecker`, `app.models.RoleEnum`

Produces:
- `BookRepo.search(criteria: BookSearchCriteria, *, limit: int, offset: int) -> Page[BookRead]`
- `BookRepo.get_book_by_uid(book_uid: str) -> Book | None`
- `BookRepo.create_book(book_create: BookCreate) -> Book` — raises `ValueError` on duplicate uid; lets `IntegrityError` propagate
- `BookRepo.update_book(book_uid: str, book_update: BookCreate) -> Book` — raises `ValueError` on missing uid
- `BookRepo.delete_book(book_uid: str) -> None`; `BookRepo.cleanup_orphan_tags() -> None`
- `BookService.create_from_upload(metadata: BookUpload, filename: str, data: bytes, content_type: str | None) -> BookRead`
- `BookService.update_book(book_uid: str, metadata: BookUpload) -> BookRead`
- `BookService.delete_book(book_uid: str) -> None`
- `BookService.search(criteria, *, limit, offset) -> Page[BookRead]`
- `BookService.get_book_by_uid(book_uid) -> BookRead`
- `BookService.get_book_file(book_uid) -> Path`
- Router: `POST /books/upload`, `GET /books/` (`Page[BookRead]`), `GET /books/{book_uid}`, `PUT /books/{book_uid}`, `DELETE /books/{book_uid}` (204), `GET /books/{book_uid}/stream` (RFC 7233). **Deleted:** `GET /books/search/` (replaced by `GET /books/`), `GET /books/{book_uid}/epub` and `/read` (replaced by the single stream endpoint; epub→pdf conversion has no module in the approved design and is dropped).

**Why:** Fused into one commit on purpose: rewriting `BookRepo` deletes `search_books` and `get_all_books`, which `book_service.py:33,47` and `book_router.py:81` still call. Splitting the three files across commits leaves commits where `GET /books/search/` raises `AttributeError` at call time — and the old plan's import-only gate passes anyway. One commit keeps every point in history importable and runnable, which matters because `git pull && cat STATE.md` is the cross-machine resume path. Three separated steps (5a/5b/5c) with a mypy gate after each keep it reviewable; a single commit at the end. Red-first tests come first (5a-i) and fail against the old code — intended TDD ordering, not a broken gate.

- [ ] **Step 5a-i: Write the failing tests**

Extend `backend/app/tests/test_book_search.py` (append; keep the Task 0 test). These are repo-level — they pin SQL semantics, not HTTP:

```python
"""Additional red-first probes for Task 5: C1 search, metadata, pagination."""

from sqlalchemy import select

from app.models import Book, Tag
from app.repositories import BookRepo
from app.schemas import BookSearchCriteria


def _seed_tagged_book(
    db, *, uid: str, tag_names: list[str], metadata: dict | None = None
) -> None:
    book = Book(
        uid=uid,
        title=f"Title {uid}",
        book_type="application/pdf",
        extension="pdf",
        file_path=f"{uid}.pdf",
        metadata_=metadata or {},
    )
    for name in tag_names:
        tag = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
        book.tags.append(tag)
    db.add(book)
    db.commit()


def test_search_tags_or_semantics_and_honest_total(db) -> None:
    """C1: OR tags; total == 2 and 2 distinct books at limit=2 (old: 3 and 1)."""
    _seed_tagged_book(db, uid="bk0001", tag_names=["math", "algebra"])
    _seed_tagged_book(db, uid="bk0002", tag_names=["math"])

    page = BookRepo(db).search(
        BookSearchCriteria(tags=["Math", "ALGEBRA"]), limit=2, offset=0
    )

    assert page.total == 2
    assert len(page.items) == 2
    assert {item.uid for item in page.items} == {"bk0001", "bk0002"}


def test_search_metadata_containment(db) -> None:
    """metadata_ filter is Postgres @> containment, served by the GIN index."""
    _seed_tagged_book(
        db, uid="bk0010", tag_names=[], metadata={"publisher": "Penguin"}
    )
    _seed_tagged_book(db, uid="bk0011", tag_names=[], metadata={"publisher": "Puffin"})

    page = BookRepo(db).search(
        BookSearchCriteria(metadata_={"publisher": "Penguin"}), limit=10, offset=0
    )

    assert page.total == 1
    assert [item.uid for item in page.items] == ["bk0010"]


def test_search_pagination_pages_are_disjoint_and_complete(db) -> None:
    """Explicit ORDER BY makes LIMIT/OFFSET stable: pages partition the set."""
    for i in range(5):
        _seed_tagged_book(db, uid=f"bk002{i}", tag_names=[])

    repo = BookRepo(db)
    criteria = BookSearchCriteria()
    pages = [repo.search(criteria, limit=2, offset=n) for n in (0, 2, 4)]

    uid_sets = [{item.uid for item in page.items} for page in pages]
    assert uid_sets[0].isdisjoint(uid_sets[1])
    assert uid_sets[0].isdisjoint(uid_sets[2])
    assert uid_sets[1].isdisjoint(uid_sets[2])
    assert uid_sets[0] | uid_sets[1] | uid_sets[2] == {f"bk002{i}" for i in range(5)}
    assert all(page.total == 5 for page in pages)
```

Create `backend/app/tests/test_book_stream.py`. Note: `app/tests/` has no `__init__.py`, so conftest helpers are not importable — replicate the two-line login flow inline:

```python
"""Red-first probes for Task 5: C3 RFC 7233 Range streaming, C4 traversal."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models import Book

CONTENT = bytes(range(256)) * 4  # 1024 bytes, position-verifiable


def _admin_headers(client: TestClient, setup_paths: Path) -> dict[str, str]:
    client.get("/setup")
    password = json.loads((setup_paths / ".credentials").read_text())["password"]
    token = client.post(
        "/auth/token", json={"username": "admin", "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def seeded_file(
    db, client: TestClient, setup_paths: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, str]:
    upload_dir = tmp_path / "books"
    upload_dir.mkdir()
    (upload_dir / "stream_test.pdf").write_bytes(CONTENT)
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    db.add(
        Book(
            uid="stream01",
            title="Stream Test",
            book_type="application/pdf",
            extension="pdf",
            file_path="stream_test.pdf",
            metadata_={},
        )
    )
    db.commit()
    return _admin_headers(client, setup_paths)


def test_stream_full_body_when_no_range(client: TestClient, seeded_file) -> None:
    r = client.get("/books/stream01/stream", headers=seeded_file)
    assert r.status_code == 200
    assert r.content == CONTENT
    assert r.headers["Accept-Ranges"] == "bytes"


def test_stream_explicit_range(client: TestClient, seeded_file) -> None:
    r = client.get("/books/stream01/stream", headers={**seeded_file, "Range": "bytes=0-99"})
    assert r.status_code == 206
    assert r.headers["Content-Range"] == f"bytes 0-99/{len(CONTENT)}"
    assert r.content == CONTENT[0:100]


def test_stream_open_ended_range(client: TestClient, seeded_file) -> None:
    r = client.get("/books/stream01/stream", headers={**seeded_file, "Range": "bytes=500-"})
    assert r.status_code == 206
    assert r.content == CONTENT[500:]


def test_stream_suffix_range(client: TestClient, seeded_file) -> None:
    """C3: bytes=-500 is legal (Safari, pdf.js). Old spec 500s."""
    r = client.get("/books/stream01/stream", headers={**seeded_file, "Range": "bytes=-500"})
    assert r.status_code == 206
    assert len(r.content) == 500
    assert r.content == CONTENT[-500:]


def test_stream_start_after_end_is_416(client: TestClient, seeded_file) -> None:
    r = client.get("/books/stream01/stream", headers={**seeded_file, "Range": "bytes=99-0"})
    assert r.status_code == 416
    assert r.headers["Content-Range"] == f"bytes */{len(CONTENT)}"


def test_stream_start_beyond_size_is_416(client: TestClient, seeded_file) -> None:
    """Out-of-range start is unsatisfiable — clamping it is WRONG."""
    r = client.get(
        "/books/stream01/stream", headers={**seeded_file, "Range": f"bytes={len(CONTENT)}-"}
    )
    assert r.status_code == 416


def test_stream_multi_range_falls_back_to_full_body(client: TestClient, seeded_file) -> None:
    r = client.get(
        "/books/stream01/stream", headers={**seeded_file, "Range": "bytes=0-99,200-299"}
    )
    assert r.status_code == 200
    assert r.content == CONTENT


def test_stream_path_traversal_is_404(
    db, client: TestClient, setup_paths: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C4: a DB-supplied file_path escaping UPLOAD_DIR must not be served."""
    upload_dir = tmp_path / "books"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    db.add(
        Book(
            uid="evil0001",
            title="Evil",
            book_type="application/pdf",
            extension="pdf",
            file_path="../../../../etc/passwd",
            metadata_={},
        )
    )
    db.commit()
    headers = _admin_headers(client, setup_paths)

    assert client.get("/books/evil0001/stream", headers=headers).status_code == 404


def test_stream_requires_auth(client: TestClient, seeded_file) -> None:
    assert client.get("/books/stream01/stream").status_code in (401, 403)
```

Create `backend/app/tests/test_book_upload.py` (happy path with a **real** PDF built in-fixture; stub bytes only for the magic-byte rejection test):

```python
"""Red-first probes for Task 5: upload happy path + rejection."""

import io
import json
from pathlib import Path

import pymupdf  # PyMuPDF
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.models import Book


def _admin_headers(client: TestClient, setup_paths: Path) -> dict[str, str]:
    client.get("/setup")
    password = json.loads((setup_paths / ".credentials").read_text())["password"]
    token = client.post(
        "/auth/token", json={"username": "admin", "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_pdf_happy_path(
    db, client: TestClient, setup_paths: Path, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    headers = _admin_headers(client, setup_paths)

    r = client.post(
        "/books/upload",
        headers=headers,
        data={"title": "Real PDF", "tags": "math, algebra"},
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Real PDF"
    assert body["extension"] == "pdf"
    assert {t["name"] for t in body["tags"]} == {"math", "algebra"}

    db.expire_all()  # identity-map trap: refresh before reading via db
    book = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert book.file_path.endswith(".pdf")
    assert (settings.UPLOAD_DIR / book.file_path).exists()


def test_upload_rejects_bad_magic_bytes(
    client: TestClient, setup_paths: Path, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    headers = _admin_headers(client, setup_paths)

    r = client.post(
        "/books/upload",
        headers=headers,
        data={"title": "Lies", "tags": ""},
        files={"file": ("lies.pdf", io.BytesIO(b"not a pdf at all"), "application/pdf")},
    )

    assert r.status_code == 400
    assert not any((tmp_path / "books").glob("*"))  # validate-first: nothing on disk


def test_upload_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/books/upload",
        data={"title": "X", "tags": ""},
        files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert r.status_code in (401, 403)
```

- [ ] **Step 5a-ii: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py -v
```

Expected: FAIL. `test_search_*` fail with `AttributeError: 'BookRepo' object has no attribute 'search'`; stream/upload tests fail (no `/stream` route exists today; old code ignores `Range`; traversal goes unchecked; old upload response model has no `cover_url`). The point is red, not the shade of red. (Docker daemon required.)

- [ ] **Step 5a-iii: Rewrite `backend/app/repositories/book_repo.py`**

Full replacement. SQLAlchemy 2.0 throughout (Invariant 4). `search` is the C1 fix — `selectinload` (a second query, immune to `LIMIT` fanout), `tags.any()` (no row multiplication, honest `count(*)`), `@>` containment (GIN index), explicit `ORDER BY`, `total` counted over an ordering-stripped subquery. The `try/except Exception` wrappers that today swallow `IntegrityError` into a generic `Exception` are removed — the router maps `IntegrityError` → 400 (Invariant 2), so it must reach the router intact:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Book, Tag
from app.schemas import BookCreate, BookRead, BookSearchCriteria, Page


class BookRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_book_by_uid(self, book_uid: str) -> Book | None:
        stmt = (
            select(Book)
            .options(selectinload(Book.tags))
            .where(Book.uid == book_uid)
        )
        return self.db_session.execute(stmt).scalar_one_or_none()

    def create_book(self, book_create: BookCreate) -> Book:
        tag_data = book_create.tags
        book_dict = book_create.model_dump(exclude={"tags"})

        existing = self.db_session.execute(
            select(Book).where(Book.uid == book_create.uid)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Book with UID {book_create.uid} already exists")

        new_book = Book(**book_dict)
        if tag_data:
            for tag_in in tag_data:
                tag = self.db_session.execute(
                    select(Tag).where(Tag.name.ilike(tag_in.name))
                ).scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                new_book.tags.append(tag)

        self.db_session.add(new_book)
        self.db_session.commit()
        self.db_session.refresh(new_book)
        return new_book

    def update_book(self, book_uid: str, book_update: BookCreate) -> Book:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise ValueError(f"Book with UID {book_uid} does not exist")

        tag_data = book_update.tags
        book_dict = book_update.model_dump(exclude={"tags"})
        for key, value in book_dict.items():
            setattr(book, key, value)

        if tag_data is not None:
            book.tags.clear()
            for tag_in in tag_data:
                tag = self.db_session.execute(
                    select(Tag).where(Tag.name.ilike(tag_in.name))
                ).scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_in.name.strip().lower())
                book.tags.append(tag)

        self.db_session.commit()
        self.db_session.refresh(book)
        self.cleanup_orphan_tags()
        return book

    def delete_book(self, book_uid: str) -> None:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise ValueError(f"Book with UID {book_uid} does not exist")
        self.db_session.delete(book)
        self.db_session.commit()
        self.cleanup_orphan_tags()

    def cleanup_orphan_tags(self) -> None:
        """Delete tags that are no longer attached to any book."""
        orphans = (
            self.db_session.execute(select(Tag).where(~Tag.books.any()))
            .scalars()
            .all()
        )
        for tag in orphans:
            self.db_session.delete(tag)
        self.db_session.commit()

    def search(
        self, criteria: BookSearchCriteria, *, limit: int, offset: int
    ) -> Page[BookRead]:
        """Dynamic search over BookSearchCriteria.

        C1 corrections (measured against postgres:16-alpine):
        - selectinload, not joinedload: joinedload + LIMIT returned 1 book
          for limit=2.
        - Book.tags.any(...), not .join(Book.tags): the join fanned rows out
          and count(*) reported 3 for 2 matching books.
        - Explicit ORDER BY: without it Postgres may repeat a row on one page
          and skip it on another.
        """
        stmt = select(Book).options(selectinload(Book.tags))

        if criteria.q:
            stmt = stmt.where(Book.title.ilike(f"%{criteria.q}%"))
        if criteria.level:
            stmt = stmt.where(Book.level == criteria.level)
        if criteria.book_type:
            stmt = stmt.where(Book.book_type.ilike(f"%{criteria.book_type}%"))
        if criteria.language:
            stmt = stmt.where(Book.language == criteria.language)
        if criteria.extension:
            stmt = stmt.where(Book.extension.ilike(criteria.extension))
        if criteria.tags:
            # OR semantics; names lowercased before comparison
            names = [t.strip().lower() for t in criteria.tags]
            stmt = stmt.where(Book.tags.any(Tag.name.in_(names)))
        if criteria.metadata_:
            # @> containment — served by ix_books_metadata_gin
            stmt = stmt.where(Book.metadata_.contains(criteria.metadata_))

        total = self.db_session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Book.created_at.desc(), Book.id.desc())
            .limit(limit)
            .offset(offset)
        )
        items = self.db_session.execute(stmt).scalars().all()

        return Page[BookRead](
            items=[BookRead.model_validate(b) for b in items],
            total=total,
            limit=limit,
            offset=offset,
        )
```

- [ ] **Step 5a-iv: Gate — mypy + repo-level search tests**

```bash
cd backend && uv run mypy app/repositories/book_repo.py --strict
cd backend && uv run pytest app/tests/test_book_search.py -v
```

Expected: mypy clean on this file (0 new against the 103-error / 24-file baseline). `test_book_search.py` fully PASS — **update the Task 0 test in place** to call the new API: `BookRepo(db).search(BookSearchCriteria(book_type="pdf"), limit=10, offset=0)` returning only `bk0001`. Do not keep a test for the deleted `search_books` method.

- [ ] **Step 5b-i: Rewrite `backend/app/services/book_service.py`**

Full replacement — 605 lines → thin orchestration. No `HTTPException`, no `open()`, no PyMuPDF, no `print` (Invariant 1, 2). Validate-first, mutate-second. Cover generation is best-effort: `False` degrades to `cover_path=None`. Empty-title note: `BookUpload.title` has `min_length=1`, so `""` raises `ValidationError` at schema build — the router sends `None`, and the filename fallback below runs on `None`:

```python
import logging
import uuid
from pathlib import Path

from app.repositories import BookRepo
from app.schemas import (
    BookCreate,
    BookRead,
    BookSearchCriteria,
    BookUpload,
    Page,
    TagCreate,
)
from app.services.book_errors import BookAlreadyExists, BookNotFound
from app.services.book_file_storage import BookFileStorage
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader

logger = logging.getLogger(__name__)


class BookService:
    """Orchestration only. Business rules live in the composed modules;
    HTTP translation lives in the router. Raises book_errors types."""

    def __init__(
        self,
        book_repo: BookRepo,
        validator: ContentValidator,
        storage: BookFileStorage,
        epub_reader: EpubMetadataReader,
        cover_generator: CoverGenerator,
    ):
        self.book_repo = book_repo
        self.validator = validator
        self.storage = storage
        self.epub_reader = epub_reader
        self.cover_generator = cover_generator

    def get_book_by_uid(self, book_uid: str) -> BookRead:
        book = self.book_repo.get_book_by_uid(book_uid)
        if book is None:
            raise BookNotFound(f"Book with UID {book_uid} not found")
        return BookRead.model_validate(book)

    def search(
        self, criteria: BookSearchCriteria, *, limit: int, offset: int
    ) -> Page[BookRead]:
        return self.book_repo.search(criteria, limit=limit, offset=offset)

    def get_book_file(self, book_uid: str) -> Path:
        """Resolved, containment-checked absolute path for streaming."""
        book = self.book_repo.get_book_by_uid(book_uid)
        if book is None:
            raise BookNotFound(f"Book with UID {book_uid} not found")
        # C4: resolve() raises BookNotFound on traversal or missing file
        return self.storage.resolve(book.file_path)

    def create_from_upload(
        self,
        metadata: BookUpload,
        filename: str,
        data: bytes,
        content_type: str | None,
    ) -> BookRead:
        # --- validate first: no byte reaches disk before every guard passes
        extension = self.validator.validate(data, filename)  # InvalidBookFile

        title = metadata.title
        if title is None:
            title = Path(filename).stem.replace("_", " ").replace("-", " ").title().strip()

        book_uid = uuid.uuid4().hex[:8]

        # --- mutate
        rel_path = self.storage.save(data, filename, book_uid)

        # EPUB metadata prefill (best-effort, epub only). Field is `tags`.
        author = metadata.author
        language = metadata.language
        final_tags = list(metadata.tags)
        if extension == "epub":
            epub_meta = self.epub_reader.read(self.storage.resolve(rel_path))
            if epub_meta is not None:
                author = author or epub_meta.author
                language = language or epub_meta.language
                known = {t.name.lower() for t in final_tags}
                for tag in epub_meta.tags:
                    if tag.lower() not in known:
                        final_tags.append(TagCreate(name=tag))

        # Cover: best-effort; False degrades to no cover, never fails upload.
        # generate() takes a dest DIRECTORY and names the file from the uid.
        cover_ok = self.cover_generator.generate(
            self.storage.resolve(rel_path),
            self.storage.cover_dir,
        )
        cover_name: str | None = f"{book_uid}.png" if cover_ok else None
        if not cover_ok:
            logger.warning("Cover generation failed for %s", rel_path)

        book_create = BookCreate(
            uid=book_uid,
            title=title,
            author=author,
            level=metadata.level,
            book_type=content_type or f"application/{extension}",
            language=language,
            extension=extension,
            file_path=rel_path,
            cover_path=cover_name,
            tags=final_tags,
        )
        try:
            created = self.book_repo.create_book(book_create)
        except ValueError as e:
            # Duplicate UID — repo's contract for "already exists"
            self.storage.delete(rel_path)
            raise BookAlreadyExists(str(e)) from e
        return BookRead.model_validate(created)

    def update_book(self, book_uid: str, metadata: BookUpload) -> BookRead:
        existing = self.book_repo.get_book_by_uid(book_uid)
        if existing is None:
            raise BookNotFound(f"Book with UID {book_uid} not found")

        book_update = BookCreate(
            uid=existing.uid,
            title=metadata.title or existing.title,
            author=metadata.author if metadata.author is not None else existing.author,
            level=metadata.level if metadata.level is not None else existing.level,
            book_type=existing.book_type,
            language=(
                metadata.language if metadata.language is not None else existing.language
            ),
            extension=existing.extension,
            file_path=existing.file_path,
            cover_path=existing.cover_path,
            tags=(
                metadata.tags
                if metadata.tags
                else [TagCreate(name=t.name) for t in existing.tags]
            ),
        )
        updated = self.book_repo.update_book(book_uid, book_update)
        return BookRead.model_validate(updated)

    def delete_book(self, book_uid: str) -> None:
        existing = self.book_repo.get_book_by_uid(book_uid)
        if existing is None:
            raise BookNotFound(f"Book with UID {book_uid} not found")
        self.storage.delete(existing.file_path)
        if existing.cover_path:
            self.storage.delete_cover(existing.cover_path)
        self.book_repo.delete_book(book_uid)
```

**Dropped, stated honestly:** (a) inline cover replacement on `PUT` — no image validator exists in the new module set, so the old cover-upload branch has no safe home; re-add with an image validator if wanted; (b) epub→pdf conversion and the `/read` endpoint — no converter module exists in the approved design; (c) the `BookUpload.book_type` form field is intentionally not honored on create — `book_type` is derived from `content_type`/extension, not client-supplied text.

- [ ] **Step 5b-ii: Gate — mypy + service grep**

```bash
cd backend && uv run mypy app/services/book_service.py --strict
cd backend && grep -n "HTTPException\|fitz\|open(" app/services/book_service.py
```

Expected: mypy clean on this file; grep prints **nothing** (the spec's `inspect.getsource` gate is replaced by this grep — `getsource` on the class misses module-level imports).

- [ ] **Step 5c-i: Rewrite `backend/app/api/book_router.py`**

Full replacement. `RoleChecker` on **every** endpoint including stream (403 on wrong role from `RoleChecker` itself; 401 from `get_current_user`). Read endpoints allow all three roles; write endpoints admin+teacher. Full RFC 7233 single-range grammar (see the table in the design spec): `bytes=0-99` → 206; `bytes=500-` → 206 through size-1; `bytes=-500` → 206 last 500 (C3); `start > end` or `start >= size` → 416 with `Content-Range: bytes */size`; malformed or multi-range → 200 full body. `Accept-Ranges: bytes` on all responses. Settings import is the hygiene-S1 form `from app.config import settings`. The `metadata` repeatable `?metadata=key:value` param is parsed to a dict — making the extensibility claim true through HTTP:

```python
from collections.abc import Iterator
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models import Account, RoleEnum
from app.repositories.book_repo import BookRepo
from app.schemas import BookRead, BookSearchCriteria, BookUpload, Page
from app.schemas.tag_schema import TagCreate
from app.services.book_errors import (
    BookAlreadyExists,
    BookNotFound,
    InvalidBookFile,
)
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader

router = APIRouter(prefix="/books", tags=["books"])
BOOK_STREAM_CHUNK_SIZE = 1024 * 256  # 256KB

MEDIA_TYPES = {"pdf": "application/pdf", "epub": "application/epub+zip"}

read_roles = RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
write_roles = RoleChecker([RoleEnum.admin, RoleEnum.teacher])


def get_book_service(db: Session = Depends(get_db)) -> BookService:
    return BookService(
        book_repo=BookRepo(db),
        validator=ContentValidator(),
        storage=BookFileStorage(),
        epub_reader=EpubMetadataReader(),
        cover_generator=CoverGenerator(),
    )


class _UnsatisfiableRange(Exception):
    pass


def _parse_range_header(range_header: str | None, size: int) -> tuple[int, int] | None:
    """Parse one RFC 7233 byte-range against a body of ``size`` bytes.

    Returns inclusive ``(start, end)`` to stream, or ``None`` to send the full
    body (header absent, malformed, or multi-range). Raises
    ``_UnsatisfiableRange`` for a syntactically valid range that cannot be
    satisfied — the caller answers 416, never a clamped start.
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes=") :].strip()
    if not spec or "," in spec:
        return None  # empty or multi-range: full body
    start_s, sep, end_s = spec.partition("-")
    if not sep or (not start_s and not end_s):
        return None  # malformed
    if not start_s:
        # Suffix range: bytes=-500 -> last 500 bytes
        if not end_s.isdigit():
            return None
        suffix = int(end_s)
        if suffix == 0:
            raise _UnsatisfiableRange
        return (max(size - suffix, 0), size - 1)
    if not start_s.isdigit() or (end_s and not end_s.isdigit()):
        return None  # non-numeric: malformed
    start = int(start_s)
    end = int(end_s) if end_s else size - 1
    if start >= size or start > end:
        raise _UnsatisfiableRange
    return (start, min(end, size - 1))  # end beyond size clamps per RFC 7233


def _iter_range(
    path: Path, start: int, end: int, chunk_size: int = BOOK_STREAM_CHUNK_SIZE
) -> Iterator[bytes]:
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = end - start + 1  # inclusive
        while remaining > 0:
            chunk = stream.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _base_headers(file_name: str) -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_name}"',
    }


@router.post("/upload", response_model=BookRead)
async def upload_new_book(
    title: str | None = Form(None),
    tags: str = Form(""),
    file: UploadFile = File(...),
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(write_roles),
) -> BookRead:
    try:
        tag_list = (
            [TagCreate(name=t.strip()) for t in tags.split(",") if t.strip()]
            if tags.strip()
            else []
        )
        # title="" (empty form field) would fail BookUpload's min_length=1;
        # send None so the service's filename fallback runs
        metadata = BookUpload(title=title if title and title.strip() else None, tags=tag_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid upload metadata: {e}") from e

    if not file.filename:
        raise HTTPException(status_code=400, detail="Book filename is required")
    data = await file.read()

    try:
        return book_service.create_from_upload(
            metadata=metadata,
            filename=file.filename,
            data=data,
            content_type=file.content_type,
        )
    except InvalidBookFile as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except BookAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="Database constraint violated") from e


@router.get("/", response_model=Page[BookRead])
def list_books(
    q: str | None = Query(None),
    level: str | None = Query(None),
    book_type: str | None = Query(None),
    language: str | None = Query(None),
    tags: list[str] | None = Query(None),
    extension: str | None = Query(None),
    metadata: list[str] | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(read_roles),
) -> Page[BookRead]:
    metadata_dict: dict[str, str] = {}
    for pair in metadata or []:
        key, sep, value = pair.partition(":")
        if not sep:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metadata filter {pair!r}; expected key:value",
            )
        metadata_dict[key] = value

    criteria = BookSearchCriteria(
        q=q,
        level=level,
        book_type=book_type,
        language=language,
        tags=tags,
        extension=extension,
        metadata_=metadata_dict or None,
    )
    return book_service.search(criteria, limit=limit, offset=offset)


@router.get("/{book_uid}", response_model=BookRead)
def get_book_details(
    book_uid: str,
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(read_roles),
) -> BookRead:
    try:
        return book_service.get_book_by_uid(book_uid)
    except BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{book_uid}", response_model=BookRead)
def update_book(
    book_uid: str,
    title: str | None = Form(None),
    tags: str = Form(""),
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(write_roles),
) -> BookRead:
    try:
        tag_list = (
            [TagCreate(name=t.strip()) for t in tags.split(",") if t.strip()]
            if tags.strip()
            else []
        )
        metadata = BookUpload(title=title if title and title.strip() else None, tags=tag_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid upload metadata: {e}") from e

    try:
        return book_service.update_book(book_uid, metadata)
    except BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="Database constraint violated") from e


@router.delete("/{book_uid}", status_code=204)
def delete_book(
    book_uid: str,
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(write_roles),
) -> Response:
    try:
        book_service.delete_book(book_uid)
    except BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)


@router.get("/{book_uid}/stream")
def stream_book(
    book_uid: str,
    range_header: str | None = Header(None, alias="Range"),
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(read_roles),
) -> Response:
    try:
        file_path = book_service.get_book_file(book_uid)  # C4 containment inside
    except BookNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    size = file_path.stat().st_size
    media_type = MEDIA_TYPES.get(
        file_path.suffix.lower().lstrip("."), "application/octet-stream"
    )
    headers = _base_headers(file_path.name)

    try:
        byte_range = _parse_range_header(range_header, size)
    except _UnsatisfiableRange:
        return Response(
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{size}"},
        )

    if byte_range is None:
        return StreamingResponse(
            _iter_range(file_path, 0, size - 1),
            status_code=200,
            media_type=media_type,
            headers={**headers, "Content-Length": str(size)},
        )

    start, end = byte_range
    return StreamingResponse(
        _iter_range(file_path, start, end),
        status_code=206,
        media_type=media_type,
        headers={
            **headers,
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
        },
    )
```

- [ ] **Step 5c-ii: Run the full test suite to verify it passes**

```bash
cd backend && uv run pytest -v
```

Expected: all of `test_book_search.py`, `test_book_stream.py`, `test_book_upload.py` PASS, plus the pre-existing `test_auth.py`.

- [ ] **Step 5c-iii: Type-check and lint the changed files**

```bash
cd backend && uv run mypy app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py --strict
cd backend && uv run ruff format app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py
cd backend && uv run ruff check app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py --ignore B008
```

Expected: mypy clean on the three changed source files (0 new against baseline). Ruff clean after format. `B008` ignored — FastAPI's `Depends()` default-argument idiom trips it by design.

- [ ] **Step 5c-iv: Run `/audit` against the diff, then `/verify`**

Dispatch `invariant-auditor` on the full diff (three rewritten files exceed the ~50-line review threshold), then `verifier` on the Definition of Done commands. Do not commit on a VIOLATION report — fix or escalate first.

- [ ] **Step 5c-v: Commit (single commit for all of Task 5)**

```bash
cd backend && git add app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py
git commit -m "refactor: fuse BookRepo/BookService/book_router — criteria search, thin orchestration, RoleChecker + RFC 7233 streaming"
```

---

### Task 6: Final gate

**Files:**
- Verify-only: everything Tasks 0–5 touched
- Modify: `STATE.md` (via the `state` skill)

**Interfaces:**
- Consumes: the Definition of Done command set from `AGENTS.md`; the repo-wide baseline (103 mypy errors / 24 files; 120 ruff errors)
- Produces: a green, formatted, linted, type-scoped tree; refreshed graphify output; final commit

**Why:** The refactor is only done when the repo's own Definition of Done has actually run and the output has been seen — a completion claim without command output is a guess. The `print(` sweep is the residual of the old plan's Task 16, folded in here: old `book_service.py` carried a dozen `print()` debug calls, and the sweep proves none survived the rewrite. mypy is scoped to changed files only — the 103-error baseline is pre-existing debt, logged in STATE.md, not fixed here.

- [ ] **Step 1: Format and lint**

```bash
cd backend && uv run ruff format .
cd backend && uv run ruff check . --fix --ignore B008
```

Expected: format reports files unchanged or reformats them — either is fine; `ruff check` ends with no remaining errors other than pre-existing ones in files this plan never touched. If `--fix` touches an untouched file, include it in the commit and note it.

- [ ] **Step 2: Type-check the changed files only**

```bash
cd backend && uv run mypy app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/services/book_errors.py app/services/content_validator.py app/services/book_file_storage.py app/services/epub_metadata_reader.py app/services/cover_generator.py app/schemas/book_schema.py --strict
```

Expected: 0 errors in these files. Do **not** run `mypy . --strict` as a gate — the 103-error / 24-file baseline is out of scope. If a changed file surfaces a pre-existing error in an untouched dependency, log it in STATE.md; do not fix the unrelated file.

- [ ] **Step 3: Full test suite**

```bash
cd backend && uv run pytest -v
```

Expected: PASS — `test_auth.py`, `test_book_search.py`, `test_book_stream.py`, `test_book_upload.py`. Docker daemon required (testcontainers starts its own `postgres:16-alpine`; no `docker compose up -d db`).

- [ ] **Step 4: `print(` sweep**

```bash
cd backend && grep -rn "print(" app/services/ app/api/book_router.py
```

Expected: **no output.** Any hit is a leftover debug statement from the old god class — remove it (use `logging.getLogger(__name__)` if the log line carries real value) and re-run Steps 1–3.

- [ ] **Step 5: Refresh the knowledge graph**

```bash
cd backend && cd .. && graphify update .
```

Expected: `graphify update` completes (AST-only, no API cost). Dirty `graphify-out/` files afterwards are expected — they are generated artifacts and gitignored.

- [ ] **Step 6: Final audit + verify, then STATE.md**

Run `/audit` (invariant-auditor over the accumulated diff since Task 0) and `/verify` (full DoD). On PASS/PASS: invoke the `state` skill — record Tasks 0–6 complete in `STATE.md`, log the untouched baseline debt (103 mypy errors / 24 files, remaining ruff baseline) under open items, and note the two dropped features (cover replacement on PUT; epub→pdf conversion + `/read`) so a future plan can resurrect them deliberately.

- [ ] **Step 7: Final commit**

```bash
cd backend && git add -A
git commit -m "chore: final gate — format, lint, scoped mypy, print sweep, graphify refresh"
```

---

## Self-Review

- **Spec coverage:** C1 search fix → Task 5a ✓; C3 Range grammar → Task 5c + `test_book_stream.py` ✓; C4 traversal containment → Task 2 `resolve()` + Task 5c ✓; I1 `cover_url` on write schema → Task 0 ✓; I5 `ORDER BY` + disjoint pagination → Task 5a ✓; module decomposition (5 modules) → Tasks 1–4 + Task 5b ✓; `RoleChecker` → Task 5c ✓; error mapping router-only → Task 5c ✓.
- **Placeholder scan:** no TBD/TODO; every code step carries complete paste-ready code; every command has an Expected output.
- **Type consistency:** `BookMetadata.tags` (not `subjects`) — Task 3 produces, Task 5b consumes ✓. `CoverGenerator.generate(source_path, dest_dir)` directory form — Task 4 produces, Task 5b calls `generate(resolve(rel_path), storage.cover_dir)` ✓. `BookFileStorage.cover_dir`/`delete_cover` — Task 2 produces, Task 5b consumes ✓. `Page[BookRead]` from `search` — Task 5a produces, Task 5c returns ✓. `BookService(...)` constructor with five dependencies — Task 5b defines, Task 5c `get_book_service` wires ✓.
- **Interface reconciliation note:** the three contributing batches were drafted independently and carried three cross-module mismatches (field name `subjects` vs `tags`; cover `dest_dir` directory vs file path; `cover_dir`/`delete_cover` referenced before they existed). All three are reconciled in this document: Task 2 exposes `cover_dir` + `delete_cover`, Task 3's field is `tags`, Task 4's `generate` takes a directory.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-16-book-refactor.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

