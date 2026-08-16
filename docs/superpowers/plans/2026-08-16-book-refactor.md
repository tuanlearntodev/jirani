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

