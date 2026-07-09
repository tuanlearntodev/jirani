# Book Feature Refactor — Design Spec

**Date:** 2026-07-03
**Project:** Jirani Offline Library Backend
**Scope:** Book feature only (streaming, CRUD for epub + pdf, extensible search)
**Spec status:** Approved (no backward compatibility required — clean slate)
**Target database:** PostgreSQL 16 (via docker-compose; `DATABASE_URL` env var selects it at runtime)

---

## Context

The existing book feature works but violates several best practices and is hard to extend:

- `app/services/book_service.py` is a **567-line god class** mixing file I/O, magic-byte validation, PDF/EPUB cover generation (~140 lines of OPF/zip walking), EPUB→PDF conversion, tag extraction, and DB orchestration.
- **No auth on any book endpoint.** Comments call upload/update/delete "Teacher endpoint" but nothing enforces it. Anyone on the network can upload, mutate, or delete books.
- **Search is hard-coded** to `(title, tags, file_type, extension)`. Adding a field like `level`, `language`, or `author` means editing the repo, service, and router in three places. Not extensible.
- **Duplicated cover-save logic** between `upload_book` and `update_book`. `update_book` is half-broken: it mutates the ORM instance, then rebuilds a full `BookCreate` from the mutated object and passes it to the repo — overwriting fields and never replacing the book file.
- **Three inconsistent streaming paths**: `/books/{uid}/stream` (256 KB chunks), `/books/{uid}/epub` (raw `FileResponse`), and `/books/{uid}/read` (1 MB chunks). No HTTP Range support, so pdf.js / epub.js cannot seek.
- **EPUB→PDF conversion couples upload to read.** Every EPUB upload also writes a PDF to disk just to serve it later. Wastes storage and makes upload slow.
- Redundant `file_type` + `extension` columns (one derives the other).
- `uid` is truncated to 8 hex chars (`uuid.uuid4()[:8]`) — collision risk as the library grows.
- `print()` everywhere instead of `logging`.
- Bare `except Exception as e` leaks internal error strings into HTTP responses.
- SQLAlchemy 1.x `Column()` style and missing type hints; fails `mypy --strict`.
- No pagination on `get_all_books` — returns every row.
- No tests for any book behavior.

The refactor fixes all of the above and makes search trivially extensible.

---

## Design Decisions

### 1. Decompose the god class into focused modules

`BookService` shrinks to thin orchestration. Five single-purpose modules live in `app/services/`:

| Module | Responsibility |
|---|---|
| `book_service.py` | Orchestration only: call validator → storage → cover → metadata reader → repo. No file/zip logic. |
| `book_file_storage.py` | Chunked save with size cap, delete file + cover, safe filename generation. |
| `cover_generator.py` | PDF first-page render (PyMuPDF) and EPUB cover extraction (OPF/zip walking). Absorbs the ~140-line block verbatim, cleaned up. |
| `content_validator.py` | Magic-byte validation for PDF / EPUB / image uploads. |
| `epub_metadata_reader.py` | Read EPUB `subject` → tags, plus `author` / `language` to pre-fill the new columns. |

**Rationale:** matches the flat `services/` convention already in the repo; each unit is small enough to hold in context, learn in isolation, and test independently.

### 2. Data model — single `books` table, SQLAlchemy 2.0, hybrid attributes

The `books` table is rewritten in `Mapped[]` + `mapped_column()` style and gains `TimestampMixin`. Three typed, indexed columns cover the single-value query axes. The existing `tags` system handles multi-value categorization (subjects, genres — all in one flat list). A native `JSONB` `metadata` column carries arbitrary future attributes with no migration.

**Query priority (drives the data model):**
1. `level` — "level 1", "grade 2" (primary filter, single-value → column)
2. `book_type` — "storybook", "novel" (tertiary filter, single-value → column; named `book_type` because `type` shadows a Python builtin)
3. `language` — "en", "sw" (last filter, single-value → column)
4. `tags` — "math", "algebra", "sci fi" (multi-value → existing many-to-many `tags` + `book_tags`)

`level`, `book_type`, and `language` are **single-value per book** — that's why they're columns. `tags` is **multi-value** — that's why it's a many-to-many relationship. `author` is kept as a stored/displayed column (extracted from EPUBs) but is not a primary search axis; the `q` text query optionally matches title **and** author.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `uid` | String(36) unique indexed | **full UUID4** (was `[:8]`) |
| `title` | String(255) not null indexed | indexed for sort/exact-match; `q` does ilike |
| `author` | String(255) nullable | display field; `q` optionally matches it |
| `level` | String(50) nullable indexed | **new** — primary query axis (single-value) |
| `book_type` | String(50) nullable indexed | **new** — tertiary query axis (single-value) |
| `language` | String(50) nullable indexed | **new** — last query axis (single-value) |
| `cover_path` | String nullable | relative filename |
| `file_path` | String not null | relative filename |
| `extension` | String(10) not null | `pdf` \| `epub` |
| ~~`file_type`~~ | — | **dropped** (MIME derived from `extension`) |
| `metadata` | JSONB default `{}` | **new** — ad-hoc attributes, GIN-indexed, filtered via JSONB operators |
| `created_at` | DateTime | via `TimestampMixin` |
| `updated_at` | DateTime | via `TimestampMixin` |

**PostgreSQL specifics:**
- `metadata` uses the native `JSONB` type (`from sqlalchemy.dialects.postgresql import JSONB`), not the generic `JSON`. JSONB supports `@>` (containment), `?` (key exists), and `->>` (text extraction) operators, and can be GIN-indexed for fast ad-hoc queries.
- A **GIN index** on `metadata` makes `?` and `@>` lookups fast without per-key indexes: `Index("ix_books_metadata_gin", "metadata", postgresql_using="gin")`.
- Boolean defaults use `server_default=text("true")` (Postgres style), not `text("1")`.
- `uid` could use Postgres's native `UUID` type with `gen_random_uuid()` as server default — a future enhancement.

**Schema reset workflow (no Alembic yet):** the app uses `Base.metadata.create_all()`, which is additive-only — it will not drop or alter existing tables. Because this refactor changes the `books` table shape, the plan includes a task to drop and rebuild just the book tables via psql:

```sql
-- Connect to the jirani_library database, then:
DROP TABLE IF EXISTS book_tags, books CASCADE;
-- Restart the app; create_all() rebuilds them with the new schema.
```

This is the Postgres equivalent of the auth plan's "delete the SQLite file", scoped to the book tables only so `accounts` data survives. In a real production app you would use **Alembic** migrations — noted as a future learning topic.

### 3. Extensible search — one criteria object, one dynamic builder

The extensibility goal is the heart of this refactor. All search input flows through a single `BookSearchCriteria` schema; one filter builder in the repo turns it into a query. Adding a field later touches **one** place — or zero places for ad-hoc metadata.

```
class BookSearchCriteria(BaseModel):
    q: str | None = None            # title ilike (also matches author)
    level: str | None = None        # equality — primary axis (single-value)
    tags: list[str] | None = None # join (multi-value, like existing tags)
    book_type: str | None = None    # equality — tertiary axis (single-value)
    language: str | None = None     # equality — last axis (single-value)
    tags: list[str] | None = None   # join (multi-value)
    extension: str | None = None
    metadata: dict[str, Any] | None = None   # ad-hoc — NO code change
```

`BookRepo.search(criteria, limit, offset)` builds the query dynamically: `and_` of optional filters. The three single-value axes (`level`, `book_type`, `language`) use **equality** (`==`) — perfect for their btree indexes. `q` uses `or_(Book.title.ilike(...), Book.author.ilike(...))`. `tags` requires a join (`stmt.join(Book.tags).where(Tag.name.in_(...))`). Metadata via **Postgres JSONB operators** (`Book.metadata.op("->>")(key) == value` for text equality, `Book.metadata.contains({key: value})` for containment, `Book.metadata.has_key(key)` for existence). The GIN index on `metadata` keeps those fast.

- **Add a typed field later** (e.g. `publisher`): one attribute on the criteria + one `if` branch in the builder + one query param on the router. One migration if you want it indexed.
- **Add an ad-hoc field** (e.g. `isbn`): `?metadata[isbn]=978...` — **zero code change, zero migration**.

List and search merge into one endpoint: `GET /books` accepts all criteria as optional query params plus `limit` / `offset` and returns `Page[BookRead]`. The separate `GET /books/search/` is removed.

### 4. Streaming — one endpoint, HTTP Range / 206

A single `GET /books/{uid}/stream` serves both formats with **HTTP Range / 206 Partial Content** so pdf.js and epub.js can seek. MIME type is derived from `extension` (`pdf` → `application/pdf`, `epub` → `application/epub+zip`). `/books/{uid}/epub` and `/books/{uid}/read` are removed entirely (no backward compatibility per the user's instruction).

**EPUB is streamed natively** — a client-side reader (e.g. epub.js) renders it. EPUB→PDF conversion is deleted from the upload path, so uploads stay fast and storage stays lean.

### 5. CRUD + auth — RoleChecker, matching the auth router

Every endpoint is guarded with `RoleChecker` from `app/dependencies/auth.py`, identical to the auth router's pattern.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/books` | any authenticated | paginated list + search |
| GET | `/books/{uid}` | any authenticated | detail |
| GET | `/books/{uid}/stream` | any authenticated | Range / 206 |
| POST | `/books` | teacher / admin | upload file + optional cover + form metadata |
| PUT | `/books/{uid}` | teacher / admin | update metadata, optional new cover/file |
| DELETE | `/books/{uid}` | teacher / admin | remove files + row + orphan tags |

### 6. Error layering — services raise domain errors, routers map to HTTP

Services never import `HTTPException` (matches `auth_service`). They raise:

- `ValueError` — not found or bad input → router maps to 400 or 404
- `OSError` — disk failure → router maps to 500
- `BookError` (defined at the top of `book_service.py`) and its subclasses `BookNotFoundError`, `BookExistsError`, `InvalidFileError` → router maps each to its status (404, 409, 400 respectively)

This keeps the service reusable outside FastAPI and makes the HTTP contract live in one place.

### 7. Logging, not print

Every `print(...)` is replaced with `logging.getLogger(__name__)`. Log levels: `info` for lifecycle (upload start/finish, delete), `warning` for recoverable failures (old cover unlink failed), `error` for caught exceptions. No secrets or file contents logged.

### 8. Type hints + strict mypy

All new code carries full type hints and must pass `mypy --strict` (AGENTS.md Definition of Done). No `Any` except where unavoidable (JSON `metadata` values), and those are annotated explicitly.

### 9. Tests

`app/tests/test_books.py` uses a test database fixture in `conftest.py`. Because the target is PostgreSQL, tests use a dedicated `jirani_library_test` database (created once) with `Base.metadata.drop_all()` + `create_all()` per test session — not in-memory SQLite, so JSONB operators behave identically to production. If the auth plan already created a Postgres test fixture, reuse it. Coverage:

- CRUD happy paths (upload pdf + epub, update, delete)
- Search by each single-value field (`level`, `book_type`, `language`) + multi-value (`tags`) + `metadata` path + combined filters
- Pagination (`limit` / `offset`, `total` correctness)
- Streaming with Range request → 206, without Range → 200
- Auth guards: student blocked from write endpoints, teacher/admin allowed
- Cover generation fallbacks (manual cover, EPUB OPF cover, PDF first page)
- Error layering: missing book → 404, bad magic bytes → 400

---

## Schema Layer

All Pydantic schemas use `model_config = ConfigDict(from_attributes=True)` (v2 style). Layered `Base → Create → Read`.

| Schema | Purpose |
|---|---|
| `BookBase` | Shared read fields: `uid`, `title`, `author`, `level`, `book_type`, `language`, `extension`, `cover_url` (computed), `tags` |
| `BookRead(BookBase)` | Response: adds `id`, `created_at`, `metadata` |
| `BookCreate` | Internal (service → repo): adds `file_path`, `cover_path` |
| `BookUpdate` | All-optional: `title`, `author`, `level`, `book_type`, `language`, `tags`, `metadata`, optional new `cover` / `file` handled at the router |
| `BookUpload` | Multipart form input: `title?`, `author?`, `level?`, `book_type?`, `language?`, `tags`, keeps validators |
| `BookSearchCriteria` | Extensible search input (see section 3) |
| `Page[T]` | Generic `{items: list[T], total: int, limit: int, offset: int}` |

---

## Files Affected

### Modified
| File | Change |
|---|---|
| `app/models/book.py` | Rewrite: SQLAlchemy 2.0, new columns, `TimestampMixin`, full UUID |
| `app/models/book_tag.py` | Light 2.0-style cleanup |
| `app/schemas/book_schema.py` | Rewrite: layered schemas, `BookSearchCriteria`, `Page` |
| `app/schemas/__init__.py` | Export new schemas |
| `app/repositories/book_repo.py` | Rewrite: dynamic search, pagination, 2.0 style |
| `app/services/book_service.py` | Thin orchestration only |
| `app/api/book_router.py` | Rewrite: auth guards, consolidated Range streaming, paginated list/search |
| `app/main.py` | Verify (no changes expected) |

### Created
| File | Purpose |
|---|---|
| `app/services/book_errors.py` | `BookError` hierarchy |
| `app/services/book_file_storage.py` | Chunked save, size cap, delete, filename |
| `app/services/cover_generator.py` | PDF + EPUB cover extraction |
| `app/services/content_validator.py` | Magic-byte validation |
| `app/services/epub_metadata_reader.py` | EPUB subject/author/language extraction |
| `app/tests/test_books.py` | Book feature tests |
| `app/tests/conftest.py` | Postgres test DB fixture (if not already present from auth plan) |

### Deleted (behavior removed, not files)
- `/books/{uid}/epub` endpoint
- `/books/{uid}/read` endpoint
- EPUB→PDF conversion logic
- `file_type` column usage

---

## Out of Scope

- Alembic migrations (still `create_all` + manual `DROP TABLE` for schema changes, same reality as the auth plan — Alembic is a future learning topic)
- Frontend changes (no backward-compat aliases; frontend is updated separately)
- Video / audio routers (separate plan)
- Full-text search or an external index (ilike + JSON path is sufficient at this scale)
- Per-user book lending / read-progress tracking
