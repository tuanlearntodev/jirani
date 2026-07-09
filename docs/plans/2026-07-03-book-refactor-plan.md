# Book Feature Refactor — Implementation Plan (Learning Edition)

**Goal:** Refactor the book feature — streaming, CRUD for epub + pdf, and extensible search — to best practices on PostgreSQL.

**Architecture:** Five focused service modules (storage, cover, validator, metadata reader, orchestration) instead of a 567-line god class; SQLAlchemy 2.0 `Mapped[]` model with hybrid typed columns + JSONB `metadata`; one `BookSearchCriteria` object driving a dynamic query builder; a single Range-aware streaming endpoint; `RoleChecker` auth on every endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (JSONB + GIN index), PyMuPDF (fitz), python-multipart

**Spec:** `docs/specs/2026-07-03-book-refactor-design.md`

> This plan is written for you to implement yourself. Each task gives you the **concept**, the **why**, and **hints** — not the finished code. Use the hints to guide your thinking. Verify your work at each step before moving on.

---

## How to read this plan

- Read the **Why** section before touching any code. Understanding the reason makes the code easier to write.
- The **Hints** section shows you partial examples and tells you what to look up — use them like a tutor, not a copy-paste source.
- The **Verify** step tells you what "done" looks like. Don't skip it.
- Commit after every task. Small commits = easy to undo mistakes.
- Run `ruff format .` and `ruff check . --fix` whenever you finish a file — keep the lint surface clean as you go.

---

## Important: PostgreSQL schema reset

You are on PostgreSQL (via docker-compose), not SQLite. The app uses `Base.metadata.create_all()`, which is **additive only** — it creates missing tables but never alters or drops existing ones. When you change the `books` model in Task 3, the existing `books` table will not pick up the new columns automatically.

When you reach Task 3, drop and rebuild just the book tables (this preserves your `accounts` data):

```bash
# From the project root — connect to the running postgres container
docker exec -it jirani_postgres psql -U postgres -d jirani_library -c \
  "DROP TABLE IF EXISTS book_tags, books CASCADE;"
# Restart the app (or just hit any endpoint) — create_all() rebuilds them
```

In a real production app, you would use **Alembic** to write migration scripts that modify the existing database safely. That is worth exploring after this project — search for "Alembic FastAPI tutorial".

---

## File Map

| File | Action | What changes |
|---|---|---|
| `app/models/book.py` | **Rewrite** | SQLAlchemy 2.0 style; add `author`, `level`, `book_type`, `language`, JSONB `metadata`; `TimestampMixin`; full UUID; drop `file_type` |
| `app/models/book_tag.py` | **Light update** | 2.0 style cleanup |
| `app/models/__init__.py` | **Update** | Export any new models |
| `app/schemas/book_schema.py` | **Rewrite** | Layered `Base → Create → Read → Update`; `BookUpload` with `tags`; `BookSearchCriteria` with `tags: list[str]`; `Page[T]` |
| `app/schemas/__init__.py` | **Update** | Export new schemas |
| `app/repositories/book_repo.py` | **Rewrite** | Dynamic search from criteria, pagination, 2.0 style, no `file_type` |
| `app/services/book_service.py` | **Shrink** | Thin orchestration only |
| `app/services/book_errors.py` | **Create** | `BookError` hierarchy: base + `BookNotFoundError`, `BookExistsError`, `InvalidFileError` |
| `app/services/book_file_storage.py` | **Create** | Chunked save, size cap, delete, safe filename |
| `app/services/cover_generator.py` | **Create** | PDF first-page render + EPUB OPF/zip cover extraction |
| `app/services/content_validator.py` | **Create** | Magic-byte validation for pdf / epub / images |
| `app/services/epub_metadata_reader.py` | **Create** | Extract EPUB subject → tags, author, language |
| `app/api/book_router.py` | **Rewrite** | `RoleChecker` guards, one Range/206 stream endpoint, paginated `GET /books`, error mapping |
| `app/tests/conftest.py` | **Create** | Postgres test DB fixture (drop/create per session) |
| `app/tests/test_books.py` | **Create** | Tests for CRUD, search, pagination, streaming, auth guards |

---

## Task 1: Read and understand the existing code

**Why:** You cannot safely refactor code you haven't read. This task produces understanding, not code. Take notes on anything that confuses you — you'll need those notes when you write the replacement.

- [ ] Read `app/models/book.py` and `app/models/book_tag.py`. Note the 1.x `Column()` style and the `tags` relationship through the `book_tags` secondary table. Which columns would you remove or rename, and which would you add?

- [ ] Read `app/schemas/book_schema.py`. Notice that `BookBase`, `BookRead`, and `BookDetail` all define the same `cover_url` computed field — that's duplication. Also note `BookCreate` is used for both create and update, which is why `update_book` in the service has to rebuild a full `BookCreate` from a mutated ORM object (the bug described in the spec).

- [ ] Read `app/repositories/book_repo.py`. Trace `search_books` — see how each filter (`title`, `tags`, `file_type`, `extension`) is a separate `if` branch hard-coded into the method. To add `author`, `level`, `language`, you'd have to edit this method, the service, and the router. That's what we're fixing with `BookSearchCriteria`.

- [ ] Read `app/services/book_service.py` (all 567 lines). Identify the five distinct responsibilities mixed together: (1) file saving with size cap, (2) magic-byte validation, (3) cover generation (the huge EPUB OPF-walking block, ~lines 397-548), (4) EPUB→PDF conversion, (5) tag extraction + DB orchestration. These will become five modules.

- [ ] Read `app/api/book_router.py`. Notice three streaming endpoints (`/stream`, `/epub`, `/read`) doing nearly the same thing with different chunk sizes and no HTTP Range support. Notice also that **none** of the endpoints have `Depends(get_current_user)` or `RoleChecker` — they're completely open despite the "Teacher endpoint" docstrings.

- [ ] Read `app/api/auth_router.py` to see the `RoleChecker` pattern you'll copy: `current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin]))`.

- [ ] Read `app/dependencies/auth.py` to understand `get_current_user` and `RoleChecker`.

- [ ] **No commit needed** — this task produces understanding, not code.

---

## Task 2: Rewrite the `Book` model (SQLAlchemy 2.0 + JSONB)

**Why:** The model is the foundation everything else builds on. Moving to SQLAlchemy 2.0 `Mapped[]` style gives you type hints your editor and `mypy --strict` can use. Adding `author`, `level`, `language` as typed indexed columns makes the high-value fields fast to filter. The JSONB `metadata` column is the extensibility escape hatch — ad-hoc attributes need no migration. Dropping `file_type` removes a redundant column (you derive MIME from `extension`). Using a full UUID4 instead of `uuid4()[:8]` eliminates collision risk.

**Concept — SQLAlchemy 2.0 `Mapped[]` + `mapped_column()`:**
```python
# Old (1.x — what you have)
id = Column(Integer, primary_key=True, index=True)
title = Column(String, nullable=False)

# New (2.0)
id: Mapped[int] = mapped_column(primary_key=True, index=True)
title: Mapped[str] = mapped_column(String(255), nullable=False)
```
The `Mapped[T]` annotation tells Python/mypy the attribute's type. `mapped_column()` tells SQLAlchemy how to store it. `Mapped[str]` = NOT NULL; `Mapped[str | None]` = nullable.

**Concept — PostgreSQL JSONB:**
```python
from sqlalchemy.dialects.postgresql import JSONB

# JSONB column — stores arbitrary JSON, queryable via operators.
# NOTE: `metadata` is reserved by SQLAlchemy on declarative classes,
# so the Python attribute is `metadata_` and the DB column is `metadata`.
metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))

# GIN index for fast @> and ? lookups (reference the Python attribute name)
from sqlalchemy import Index
Index("ix_books_metadata_gin", "metadata_", postgresql_using="gin")
```
JSONB is Postgres's binary JSON type. It supports `@>` (containment), `?` (key exists), `->>` (text extraction). A GIN index makes those fast without a per-key index. Use the `postgresql.JSONB` dialect import, **not** the generic `sqlalchemy.JSON`.

**Concept — `TimestampMixin`:**
Your `app/models/base.py` already defines `TimestampMixin` with `created_at` and `updated_at`. Inherit from it (before `Base`) and you get both columns for free.

**Hints for `app/models/book.py`:**
- Keep the file at `app/models/book.py` — rewrite its contents entirely.
- Import `TimestampMixin` from `app.models.base` and put it first in the class bases: `class Book(TimestampMixin, Base):`
- Import `JSONB` from `sqlalchemy.dialects.postgresql`
- Import `Index`, `text` from `sqlalchemy`
- Import `uuid` from the standard library — you'll store the string form, not a native UUID column (keeps it portable)
- Columns to define (use `Mapped[]` + `mapped_column()`):
  - `id: Mapped[int]` — PK, index
  - `uid: Mapped[str]` — `String(36)`, unique, indexed, nullable=False (full UUID4 string)
  - `title: Mapped[str]` — `String(255)`, nullable=False, indexed (for sort/exact-match; `q` does ilike which won't use the index but is fine at this scale)
  - `author: Mapped[str | None]` — `String(255)`, **not indexed** (display field; `q` optionally matches it via `or_`)
  - `level: Mapped[str | None]` — `String(50)`, indexed — **primary query axis** ("level 1", "grade 2"). Single-value.
  - `book_type: Mapped[str | None]` — `String(50)`, indexed — **tertiary query axis** ("storybook", "novel"). Named `book_type` because `type` shadows a Python builtin. Single-value.
  - `language: Mapped[str | None]` — `String(50)`, indexed — **last query axis** ("en", "sw"). Single-value.
  - `cover_path: Mapped[str | None]` — `String`
  - `file_path: Mapped[str]` — `String`, nullable=False
  - `extension: Mapped[str]` — `String(10)`, nullable=False
  - `metadata_: Mapped[dict]` — `JSONB`, `default=dict`, `server_default=text("'{}'::jsonb")`. **Naming note:** `metadata` is reserved by SQLAlchemy on declarative classes, so name the Python attribute `metadata_` and map it to the DB column `metadata` via `mapped_column("metadata", JSONB, ...)`.
- Keep the `tags` relationship exactly as it is: `relationship("Tag", secondary="book_tags", back_populates="books")`
- Add the GIN index inside `__table_args__`:
  ```python
  __table_args__ = (Index("ix_books_metadata_gin", "metadata_", postgresql_using="gin"),)
  ```
- **Do not** add a `file_type` column — it's gone.
- Search for: "SQLAlchemy 2.0 Mapped mapped_column", "PostgreSQL JSONB SQLAlchemy", "SQLAlchemy reserved attribute name metadata"

**Verify:**
```bash
cd backend
python -c "from app.models.book import Book; print(sorted(Book.__table__.columns.keys()))"
# Should print: ['author', 'book_type', 'cover_path', 'created_at', 'extension', 'file_path', 'id', 'language', 'level', 'metadata', 'title', 'uid', 'updated_at']
# Must NOT include 'file_type'
```
Note: the DB column is `metadata` (the print shows column names, not Python attr names).

- [ ] Rewrite `app/models/book.py`
- [ ] Verify column list (no `file_type`; has `metadata`, `author`, `level`, `book_type`, `language`, `created_at`, `updated_at`)
- [ ] Commit: `git commit -m "refactor: rewrite Book model in SQLAlchemy 2.0 with JSONB metadata"`

---

## Task 3: Clean up `BookTag` to 2.0 style

**Why:** `BookTag` is the junction table between books and tags. It's still in SQLAlchemy 1.x `Column()` style. This task rewrites it to 2.0 `Mapped[]` + `mapped_column()` style for consistency with the new `Book` model, so `mypy --strict` passes and your editor gets type hints.

**Hints for `app/models/book_tag.py`:**
- Rewrite in `Mapped[]` + `mapped_column()` style
- `id: Mapped[int]` — PK
- `book_id: Mapped[int]` — `ForeignKey("books.id", ondelete="CASCADE")`, nullable=False
- `tag_id: Mapped[int]` — `ForeignKey("tags.id", ondelete="CASCADE")`, nullable=False
- `is_active: Mapped[bool]` — `default=True`
- Keep `__table_args__ = (UniqueConstraint("book_id", "tag_id"),)`

**Verify:**
```bash
cd backend
python -c "from app.models.book_tag import BookTag; print(sorted(BookTag.__table__.columns.keys()))"
# ['book_id', 'id', 'is_active', 'tag_id']
```

- [ ] Rewrite `app/models/book_tag.py` in 2.0 style
- [ ] Verify column list
- [ ] Commit: `git commit -m "refactor: update BookTag to SQLAlchemy 2.0 style"`

---

## Task 4: Drop and rebuild the book tables

**Why:** `Base.metadata.create_all()` is additive only. Your old `books` table has the old columns (`file_type`, no `author`/`level`/`book_type`/`language`/`metadata`). Dropping the book-related tables and restarting rebuilds them with the new schema — your `accounts` data is untouched.

**Steps:**
- [ ] Make sure your postgres container is running:
  ```bash
  docker compose up -d db
  ```
- [ ] Drop the book tables (this deletes any existing book rows — fine for dev):
  ```bash
  docker exec -it jirani_postgres psql -U postgres -d jirani_library -c \
    "DROP TABLE IF EXISTS book_tags, books CASCADE;"
  ```
- [ ] Start the app so `create_all()` rebuilds them:
  ```bash
  cd backend
  uvicorn app.main:app --reload
  ```
- [ ] Confirm it starts without errors. Check the postgres container logs if there's a CREATE TABLE error — most likely cause is a typo in the model.
- [ ] Verify the new schema in psql:
  ```bash
  docker exec -it jirani_postgres psql -U postgres -d jirani_library -c "\d books"
  # Should show all new columns including 'metadata' of type jsonb
  # Should NOT show 'file_type'
  ```
- [ ] Verify the GIN index exists:
  ```bash
  docker exec -it jirani_postgres psql -U postgres -d jirani_library -c \
    "SELECT indexname FROM pg_indexes WHERE tablename='books';"
  # Should list 'ix_books_metadata_gin' with indexdef containing 'USING gin'
  ```
- [ ] Verify the tables were created:
  ```bash
  docker exec -it jirani_postgres psql -U postgres -d jirani_library -c "\dt"
  # Should list: books, book_tags (plus accounts, tags, etc.)
  ```
- [ ] Stop the server with Ctrl+C
- [ ] Commit: `git commit -m "chore: drop and rebuild book tables for new schema"`

> **Tip:** Any time you change a model's columns during this plan, re-run the DROP TABLE command and restart. Only the tables you dropped get rebuilt.

---

## Task 5: Rewrite book schemas (layered + `BookSearchCriteria` + `Page`)

**Why:** The schema layer is the contract between the API and the rest of the app. Layering (`Base → Create → Read → Update`) prevents accidental data leaks and makes each schema self-documenting. `BookSearchCriteria` is the **extensibility mechanism** — one object flows through router → service → repo, and adding a field means touching one place. `Page[T]` replaces "return every row" with proper pagination.

**Concept — Layered schemas:**
```python
class BookBase(BaseModel):       # shared fields
    uid: str
    title: str
class BookRead(BookBase):        # response — adds id, timestamps
    id: int
    created_at: datetime
class BookCreate(BookBase):      # internal input — adds file_path
    file_path: str
class BookUpdate(BaseModel):     # all-optional partial update
    title: str | None = None
```
`BookUpdate` being all-optional is what lets `update_book` change just the fields the user sent, instead of rebuilding a full `BookCreate` (the current bug).

**Concept — Generic `Page[T]`:**
```python
from typing import Generic, TypeVar
T = TypeVar("T")
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```
Usage: `Page[BookRead]` as a `response_model`. FastAPI renders `{"items": [...], "total": 42, "limit": 20, "offset": 0}`.

**Concept — Computed fields (Pydantic v2):**
```python
from pydantic import computed_field
class BookBase(BaseModel):
    cover_path: str | None = None
    @computed_field
    @property
    def cover_url(self) -> str | None:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"
```
Define `cover_url` **once** on `BookBase` — the current code duplicates it across three schemas.

**Hints for `app/schemas/book_schema.py`:**
- Import `ConfigDict`, `BaseModel`, `Field`, `computed_field`, `field_validator` from `pydantic`
- Import `Generic`, `TypeVar` from `typing`; `Any` from `typing`
- Import `datetime` from standard library
- Import `TagRead`, `TagCreate` from `app.schemas.tag_schema`
- Import `re` for the title validator
- Define `BookBase`:
  - Fields: `uid: str`, `title: str`, `author: str | None = None`, `level: str | None = None`, `book_type: str | None = None`, `language: str | None = None`, `extension: str`, `tags: list[TagRead] = []`, `cover_path: str | None = None`
  - `model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)`
  - Computed `cover_url` (defined once here)
- Define `BookRead(BookBase)`:
  - Adds `id: int`, `created_at: datetime`, `metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")`
  - **Naming note:** the Python attribute is `metadata_` (Pydantic also reserves `metadata`), but it maps to the model's `metadata_` attribute via `from_attributes`. Keep the field name `metadata_`.
- Define `BookCreate(BookBase)`:
  - Adds `file_path: str`, `cover_path: str | None = None`, `tags: list[TagCreate] = []`
  - This is internal — service → repo. Not an API response.
- Define `BookUpdate(BaseModel)`:
  - All-optional: `title: str | None = None`, `author: str | None = None`, `level: str | None = None`, `book_type: str | None = None`, `language: str | None = None`, `tags: list[TagCreate] | None = None`, `metadata_: dict[str, Any] | None = None`
  - `model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)`
- Define `BookUpload(BaseModel)`:
  - Multipart form input — all optional: `title: str | None = Field(None, min_length=1, max_length=255)`, `author: str | None = Field(None, max_length=255)`, `level: str | None = Field(None, max_length=50)`, `book_type: str | None = Field(None, max_length=50)`, `language: str | None = Field(None, max_length=50)`, `tags: list[TagCreate] = Field(default_factory=list, max_length=20)`
  - Keep the existing `validate_title` and `validate_tags` field validators (port them over)
- Define `BookSearchCriteria(BaseModel)`:
  - `q: str | None = None` (title ilike; also matches author via `or_`)
  - `level: str | None = None` (equality — primary axis)
  - `book_type: str | None = None` (equality — tertiary axis)
  - `language: str | None = None` (equality — last axis)
  - `tags: list[str] | None = None` (join — multi-value)
  - `extension: str | None = None`
  - `metadata_: dict[str, Any] | None = None` (ad-hoc JSONB filters)
  - All optional — empty criteria = return all (paginated)
- Define `Page[T]` as a generic model (see concept above)
- **Remove** the old `BookDetail` — `BookRead` now carries everything `BookDetail` did.

**Hints for `app/schemas/__init__.py`:**
- Update the book imports to: `BookBase, BookCreate, BookRead, BookUpdate, BookUpload, BookSearchCriteria, Page`
- Add all new schemas to `__all__`

**Verify:**
```bash
cd backend
python -c "
from app.schemas import BookBase, BookRead, BookCreate, BookUpdate, BookUpload, BookSearchCriteria, Page
c = BookSearchCriteria(q='alice', tags=['math', 'algebra'], metadata_={'publisher': 'Penguin'})
print(c.model_dump())
p = Page[BookRead](items=[], total=0, limit=20, offset=0)
print(p.model_dump())
print('OK')
"
```

- [ ] Rewrite `app/schemas/book_schema.py`
- [ ] Update `app/schemas/__init__.py` exports
- [ ] Verify with the REPL snippet
- [ ] Commit: `git commit -m "refactor: rewrite book schemas with layering, search criteria, and pagination"`

---

## Task 6: Rewrite `BookRepo` (dynamic search + pagination + 2.0 style)

**Why:** The repository is the only place that talks to the DB. Right now `search_books` has a hard-coded `if` per filter — adding a field means editing three layers. The new design takes a single `BookSearchCriteria` object and builds the query dynamically, so adding a typed field is one `if` branch in **one** place, and ad-hoc metadata filters need **zero** code change. Pagination prevents the list endpoint from returning every row in the library.

**Concept — Dynamic query building with SQLAlchemy:**
```python
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

def search(self, criteria: BookSearchCriteria, limit: int, offset: int) -> tuple[list[Book], int]:
    stmt = select(Book).options(joinedload(Book.tags))
    filters = []
    if criteria.q:
        # q matches title OR author (loose text search)
        filters.append(or_(Book.title.ilike(f"%{criteria.q}%"), Book.author.ilike(f"%{criteria.q}%")))
    # The three single-value axes use equality — they hit the btree indexes
    if criteria.level:
        filters.append(Book.level == criteria.level)
    if criteria.book_type:
        filters.append(Book.book_type == criteria.book_type)
    if criteria.language:
        filters.append(Book.language == criteria.language)
    if criteria.extension:
        filters.append(Book.extension == criteria.extension)
    # ...metadata filters (see below)...
    if filters:
        stmt = stmt.where(and_(*filters))
    # tags need a join (multi-value many-to-many)
    if criteria.tags:
        stmt = stmt.join(Book.tags).where(Tag.name.in_([t.lower() for t in criteria.tags]))
    # count total (for pagination) — use a subquery or separate count query
    total = self.db_session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    # apply pagination
    stmt = stmt.limit(limit).offset(offset)
    books = self.db_session.execute(stmt).unique().scalars().all()
    return books, total
```
Note the use of `select()` + `session.execute()` — that's the SQLAlchemy 2.0 way. The old `db.query(Book)` style still works but is legacy. Use `.unique()` when you `joinedload` a collection to avoid duplicate parent rows.

**Why equality (`==`) for `level`/`book_type`/`language`, not `ilike`:** these are categorical fields with a fixed set of values ("level 1", "storybook", "en"). Exact match is what you want, and it uses the btree index. `ilike` would match "level 10" when you query "level 1" — wrong. Reserve `ilike` for free-text fields (`q` → title/author).

**Why `tags` uses a join, not equality:** `tags` is multi-value (a book can be "math" **and** "algebra"). It's a many-to-many relationship, so filtering requires joining through `book_tags` and using `Tag.name.in_([...])`.

**Concept — JSONB filtering in SQLAlchemy:**
```python
# Key existence: metadata ? 'isbn'
from sqlalchemy import text
filters.append(Book.metadata_.op("?")(key))

# Containment: metadata @> '{"publisher": "Penguin"}'
filters.append(Book.metadata_.contains({key: value}))

# Text extraction: metadata ->> 'publisher' == 'Penguin'
filters.append(Book.metadata_.op("->>")(key) == value)
```
`Book.metadata_` is the Python attribute; `.op("?")` and `.contains()` emit the right Postgres operators. The GIN index you added in Task 2 makes `?` and `@>` fast.

**Hints for `app/repositories/book_repo.py`:**
- Rewrite the whole file. Keep the class name `BookRepo` and the `__init__(self, db_session: Session)` constructor.
- Use `select()` + `self.db_session.execute()` style (2.0). Import `select`, `func`, `and_` from `sqlalchemy`.
- Import `joinedload` from `sqlalchemy.orm`.
- Import `Book`, `Tag` from `app.models`, `BookCreate`, `BookUpdate`, `BookSearchCriteria` from `app.schemas`.
- Methods to implement:
  - `get_by_uid(uid: str) -> Book | None` — `select(Book).options(joinedload(Book.tags)).where(Book.uid == uid)`, return `.scalar_one_or_none()` (use `.unique()` first because of the joinedload)
  - `get_by_uid(uid: str) -> Book | None` — `select(Book).options(joinedload(Book.tags)).where(Book.uid == uid)`, return `.scalar_one_or_none()` (use `.unique()` first because of the joinedload)
  - `create(self, book_create: BookCreate) -> Book` — same tag-attach logic as today (find-or-create tags by `ilike`). Raise `ValueError(f"Book with UID {uid} already exists")` on duplicate. Commit + refresh + return.
  - `update(self, uid: str, update: BookUpdate) -> Book` — fetch the book (404 → `ValueError`), apply only the non-None fields from `update` via `setattr`. If `update.tags is not None`, clear and re-attach (find-or-create). If `update.metadata_ is not None`, merge into existing `metadata_` dict (don't overwrite — merge, so partial metadata updates don't drop existing keys). Commit + refresh + cleanup orphan tags + return.
  - `delete(self, uid: str) -> None` — fetch (404 → `ValueError`), delete, commit, cleanup orphan tags.
  - `search(self, criteria: BookSearchCriteria, limit: int, offset: int) -> tuple[list[Book], int]` — build dynamically per the concept above. Return `(books, total_count)`.
  - `cleanup_orphan_tags(self) -> None` — same logic as today, 2.0 style.
- **Drop** the old `search_books(self, title, tags, file_type, extension)` and `get_all_books` — `search` with empty criteria replaces `get_all_books`.
- Search for: "SQLAlchemy 2.0 select execute scalars", "SQLAlchemy JSONB op contains", "SQLAlchemy joinedload unique"

**Verify:**
```bash
cd backend
python -c "from app.repositories.book_repo import BookRepo; print('OK')"
```

- [ ] Rewrite `app/repositories/book_repo.py`
- [ ] Verify no import errors
- [ ] Commit: `git commit -m "refactor: rewrite BookRepo with dynamic search and pagination"`

---

## Task 7: Create `ContentValidator`

**Why:** Magic-byte validation is the first line of defense against malicious uploads — a file named `evil.pdf` could be anything. Checking the first few bytes against known signatures (`%PDF-` for PDF, `PK\x03\x04` for EPUB/ZIP) catches obvious lies. Pulling this into its own module makes it reusable and testable.

**Concept — Magic bytes:**
File formats have identifying byte sequences at offset 0:
- PDF: `%PDF-` (5 bytes)
- EPUB: `PK\x03\x04` (it's a ZIP)
- JPEG: `\xff\xd8\xff`
- PNG: `\x89PNG\r\n\x1a\n`
- WEBP: `RIFF` (then `WEBP` at offset 8)

```python
def validate_book(self, header: bytes, extension: str) -> None:
    signatures = {"pdf": b"%PDF-", "epub": b"PK\x03\x04"}
    sig = signatures.get(extension)
    if sig and not header.startswith(sig):
        raise InvalidFileError(f"File does not appear to be a valid {extension.upper()}")
```

**Hints for `app/services/content_validator.py`:**
- **First** create `app/services/book_errors.py` with the error hierarchy (this avoids circular imports — every service module imports from `book_errors`, and `book_errors` imports nothing):
  ```python
  class BookError(Exception): ...
  class BookNotFoundError(BookError): ...
  class BookExistsError(BookError): ...
  class InvalidFileError(BookError): ...
  ```
- Then create `app/services/content_validator.py`. Import `InvalidFileError` from `app.services.book_errors`.
- Define a class `ContentValidator` (no state needed — could be static methods, but a class matches the codebase convention).
- Methods:
  - `validate_book(header: bytes, extension: str) -> None` — raise `InvalidFileError` on mismatch
  - `validate_image(header: bytes, extension: str) -> None` — raise `InvalidFileError` on mismatch; image signatures dict as in the current code
  - `validate_extension(filename: str, allowed: set[str]) -> str` — extract and return the lowercased extension; raise `InvalidFileError` if missing or not in `allowed`
- No `HTTPException` here — this is a service-layer module. The router maps `InvalidFileError` → 400.

**Verify:**
```bash
cd backend
python -c "
from app.services.content_validator import ContentValidator
from app.services.book_errors import InvalidFileError
v = ContentValidator()
v.validate_book(b'%PDF-1.4...', 'pdf')  # passes
try:
    v.validate_book(b'not a pdf', 'pdf')
    print('ERROR: should have raised')
except InvalidFileError:
    print('correctly rejected bad PDF')
print('OK')
"
```

- [ ] Create `app/services/book_errors.py` with the `BookError` hierarchy
- [ ] Create `app/services/content_validator.py`
- [ ] Verify with the REPL snippet
- [ ] Commit: `git commit -m "feat: add ContentValidator and BookError hierarchy"`
---

## Task 8: Create `BookFileStorage`

**Why:** Saving an uploaded file in chunks with a running size check is currently inlined in `BookService.upload_book` and duplicated for covers. Pulling it into one module gives you a single tested save function used by both upload and update. Cleanup (delete file + cover) also lives here.

**Concept — Streaming save with size cap:**
```python
async def save_upload(self, file: UploadFile, dest: Path, max_size: int) -> int:
    total = 0
    with dest.open("wb") as buf:
        while chunk := await file.read(8192):
            total += len(chunk)
            if total > max_size:
                raise InvalidFileError(f"File too large ({total / 1048576:.2f}MB). Max: {max_size / 1048576:.0f}MB")
            buf.write(chunk)
    return total
```
Read in chunks (8 KB) so you never load the whole file into memory. Track the running total and bail early if it exceeds the cap. The first chunk (the header you already read for validation) is written before the loop — handle that by writing it first, then streaming the rest. Or restructure: read the header, validate, then call `save_upload` which reads from where the file pointer is (after the header) — pass the header in to write first. Pick one approach and be consistent.

**Concept — Safe filenames:**
```python
import re
def safe_filename(title: str, uid: str, extension: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", title).strip().lower()
    clean = re.sub(r"[-\s]+", "_", clean)
    return f"{clean}_{uid}.{extension}"
```
Strip anything that's not a word char, space, or hyphen. Collapse spaces/hyphens to underscores. Append the UID so filenames are unique even for duplicate titles.

**Hints for `app/services/book_file_storage.py`:**
- Import `Path` from `pathlib`, `UploadFile` from `fastapi`, `re`, `logging`
- Import `InvalidFileError` from `app.services.book_errors`
- Import `settings` from `app`
- Class `BookFileStorage`:
  - `__init__`: store `upload_dir = settings.UPLOAD_DIR`, `cover_dir = settings.COVER_DIR`, `max_upload = settings.MAX_UPLOAD_SIZE`, `max_cover = settings.MAX_COVER_SIZE`. Create the dirs in `__init__` (mkdir parents exist_ok).
  - `safe_filename(title, uid, extension) -> str` — static method, per concept above
  - `async def save_book(self, file: UploadFile, dest: Path, header: bytes) -> int` — write `header` first, then stream the rest in 8 KB chunks with the size cap; return total bytes
  - `async def save_cover(self, cover: UploadFile, dest: Path, header: bytes) -> int` — same but with `max_cover` cap
  - `delete_book_file(filename: str) -> None` — unlink if exists, log warning on failure (don't raise — best-effort)
  - `delete_cover(filename: str) -> None` — same
  - `book_path(filename: str) -> Path` — `self.upload_dir / filename`
  - `cover_path(filename: str) -> Path` — `self.cover_dir / filename`
- Use `logging.getLogger(__name__)` — no `print`
- No `HTTPException` — raise `InvalidFileError` on size/extension issues

**Verify:**
```bash
cd backend
python -c "
from app.services.book_file_storage import BookFileStorage
s = BookFileStorage()
print(s.safe_filename('A Title!! With Stuff', 'abc123', 'pdf'))
# something like 'a_title_with_stuff_abc123.pdf'
print('OK')
"
```

- [ ] Create `app/services/book_file_storage.py`
- [ ] Verify with the REPL snippet
- [ ] Commit: `git commit -m "feat: add BookFileStorage for chunked file saves"`

---

## Task 9: Create `EpubMetadataReader`

**Why:** EPUBs carry metadata (title, author, language, subject/keywords) in their OPF file. Extracting it lets you pre-fill the new `author`, `language` columns and suggest tags from the `subject` field — so the teacher doesn't have to type everything. Isolating this in its own module keeps the zip-parsing logic out of the service.

**Concept — EPUB structure:**
An EPUB is a ZIP. The entry point is `META-INF/container.xml`, which points to the OPF file (the manifest). The OPF contains `<dc:title>`, `<dc:creator>`, `<dc:language>`, `<dc:subject>` elements in the Dublin Core namespace.

```python
import zipfile, xml.etree.ElementTree as ET
def strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag

with zipfile.ZipFile(path) as z:
    container = ET.fromstring(z.read("META-INF/container.xml"))
    opf_path = next(e.get("full-path") for e in container.iter() if strip_ns(e.tag) == "rootfile")
    opf = ET.fromstring(z.read(opf_path))
    for meta in opf.iter():
        if strip_ns(meta.tag) == "title": title = meta.text
        if strip_ns(meta.tag) == "creator": author = meta.text
        if strip_ns(meta.tag) == "language": language = meta.text
        if strip_ns(meta.tag) == "subject": subjects.append(meta.text)
```

**Concept — PyMuPDF shortcut:**
The current code uses `fitz.open(path).metadata` which returns a dict with `subject`, `author`, etc. That's simpler than walking the OPF yourself, but PyMuPDF's EPUB metadata support can be spotty. Try PyMuPDF first, fall back to manual OPF parsing if a field is missing. Or just use PyMuPDF — it's already a dependency and the current code uses it. Your call; the verify step will tell you if it works on your test EPUBs.

**Hints for `app/services/epub_metadata_reader.py`:**
- Import `zipfile`, `xml.etree.ElementTree as ET`, `re`, `logging`, `Path`
- Import `fitz` (PyMuPDF) — optional, for the shortcut path
- Class `EpubMetadataReader`:
  - `read(path: Path) -> EpubMetadata` — extract title, author, language, subjects (list of str). Return a small dataclass or `TypedDict` `EpubMetadata`.
  - Define `EpubMetadata` as a dataclass: `title: str | None`, `author: str | None`, `language: str | None`, `subjects: list[str]`
  - The EPUB `subject` field maps naturally to **tags** (math, science, algebra). The service will merge these with user-provided tags on upload. You could also extract `book_type` from EPUB `<dc:type>` if present, but it's rarely populated — leave it as `None` and let the user fill it via the form.
  - Split `subjects` by comma/semicolon like the current `_extract_epub_tags` does
  - Log (don't raise) on parse errors — return an empty `EpubMetadata` if extraction fails
- The `strip_ns` helper in the concept above is needed because OPF tags are namespaced (`{http://purl.org/dc/elements/1.1/}title`)
- Search for: "EPUB OPF Dublin Core metadata", "Python zipfile xml namespace"

**Verify:**
```bash
cd backend
python -c "
from app.services.epub_metadata_reader import EpubMetadataReader
from pathlib import Path
# Point this at a real EPUB in your uploads dir, or skip if you don't have one handy
reader = EpubMetadataReader()
print('EpubMetadataReader importable — OK')
"
```
If you have a test EPUB handy:
```python
m = reader.read(Path("uploads/books/some_book.epub"))
print(m)
```

- [ ] Create `app/services/epub_metadata_reader.py`
- [ ] Verify no import errors (and test against a real EPUB if you have one)
- [ ] Commit: `git commit -m "feat: add EpubMetadataReader for EPUB metadata extraction"`

---

## Task 10: Create `CoverGenerator`

**Why:** The ~140-line EPUB cover extraction block is the single biggest reason `book_service.py` is 567 lines. It walks the EPUB's OPF, looks for `cover-image` properties, falls back to guide references, falls back to filename heuristics, falls back to the first image, and finally renders the first page via PyMuPDF. That logic is valuable but belongs in its own module, not the service.

**Concept — PDF cover (simple):**
```python
import fitz
doc = fitz.open(str(pdf_path))
pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
pix.save(str(output_path))
doc.close()
```
Render page 1 at half scale, save as the cover.

**Concept — EPUB cover (the hard part):**
The current `_generate_thumbnail` method (lines 397-548 of `book_service.py`) is your reference. **You are allowed to copy that logic into `cover_generator.py`** and clean it up (remove `print` statements → `logging`, remove the inline `import zipfile`/`import xml.etree.ElementTree as ET` → top-level imports, remove the DEBUG prints). The extraction order is:
1. OPF `<meta name="cover" content="cover-id">` → find the manifest item with that id
2. OPF item with `properties="cover-image"`
3. OPF `<guide><reference type="cover" href="..."/></guide>` (legacy)
4. Filename heuristic: any image whose name contains `cover`, `front`, or `thumb`
5. First image in the zip
6. Fallback: render first page via PyMuPDF (rare for EPUBs, but a last resort)

**Hints for `app/services/cover_generator.py`:**
- Import `zipfile`, `xml.etree.ElementTree as ET`, `re`, `logging`, `Path`
- Import `fitz`
- Class `CoverGenerator`:
  - `generate(self, book_path: Path, output_path: Path, extension: str) -> bool` — dispatch by extension:
    - `pdf` → render first page (per concept above)
    - `epub` → the OPF walk (port from current code, cleaned up)
    - return `True` on success, `False` on failure (log the error, don't raise — cover generation is best-effort)
  - `_extract_epub_cover(self, book_path: Path, output_path: Path) -> bool` — the OPF/zip logic
  - `_render_pdf_first_page(self, book_path: Path, output_path: Path) -> bool` — PyMuPDF render
  - `strip_ns(tag)` helper (same as in `EpubMetadataReader` — you could share it, but duplication here is fine for now)
- Use `logging.getLogger(__name__)` — no `print`
- The function is **synchronous** and potentially slow (zip parsing). The service will call it via `run_in_executor` to avoid blocking the event loop — that's the service's job, not yours.

**Verify:**
```bash
cd backend
python -c "
from app.services.cover_generator import CoverGenerator
from pathlib import Path
g = CoverGenerator()
print('CoverGenerator importable — OK')
"
```
If you have a test PDF:
```python
g.generate(Path('uploads/books/some.pdf'), Path('/tmp/test_cover.jpg'), 'pdf')
print(Path('/tmp/test_cover.jpg').exists())  # True
```

- [ ] Create `app/services/cover_generator.py` (port + clean the EPUB cover logic)
- [ ] Verify no import errors (and test against a real PDF if you have one)
- [ ] Commit: `git commit -m "feat: add CoverGenerator for PDF and EPUB cover extraction"`

---

## Task 11: Shrink `BookService` to thin orchestration

**Why:** Now that the helpers exist, `BookService` becomes a thin coordinator: validate → save → generate cover → read metadata → persist. No file I/O, no zip parsing, no `print`. This is the layer that knows the *order* of operations but not the *details*. It also defines the `BookError`-based contract: it raises domain errors, never `HTTPException`.

**Concept — Orchestration pattern:**
```python
class BookService:
    def __init__(self, repo: BookRepo, storage: BookFileStorage, validator: ContentValidator, cover_gen: CoverGenerator, epub_reader: EpubMetadataReader):
        self.repo = repo
        self.storage = storage
        # ...store all helpers
    
    async def upload(self, metadata: BookUpload, file: UploadFile, cover: UploadFile | None) -> BookRead:
        # 1. validate extension + header
        # 2. generate uid + filename
        # 3. save book file (storage)
        # 4. generate or save cover
        # 5. extract epub metadata (if epub) to pre-fill author/language/tags
        # 6. build BookCreate, call repo.create
        # 7. on any failure: cleanup saved files, re-raise
```
The service holds its helpers as dependencies (composition). This makes it testable — you can mock any helper in tests.

**Hints for `app/services/book_service.py`:**
- Rewrite the whole file. It should be **much** shorter — aim for ~150-200 lines.
- Imports: `uuid`, `asyncio`, `logging`, `Path` from `pathlib`, `UploadFile` from `fastapi`
- Import `BookRepo` from `app.repositories`, `BookFileStorage`, `ContentValidator`, `CoverGenerator`, `EpubMetadataReader` from the new modules
- Import `BookCreate`, `BookRead`, `BookUpdate`, `BookUpload`, `BookSearchCriteria` from `app.schemas`
- Import `BookNotFoundError`, `BookExistsError`, `InvalidFileError` from `app.services.book_errors`
- Import `TagCreate` from `app.schemas.tag_schema`
- Import `settings` from `app`
- `__init__` takes all five helpers as args (composition). The router's `get_book_service` dependency will wire them up.
- `logger = logging.getLogger(__name__)` at module level
- Methods:
  - `get_by_uid(uid: str) -> BookRead` — fetch via repo, raise `BookNotFoundError` if None, return `BookRead.model_validate(book)`
  - `search(criteria: BookSearchCriteria, limit: int, offset: int) -> Page[BookRead]` — call `repo.search`, build and return `Page[BookRead](items=[BookRead.model_validate(b) for b in books], total=total, limit=limit, offset=offset)`
  - `async def upload(self, metadata: BookUpload, file: UploadFile, cover: UploadFile | None) -> BookRead` — orchestrate per the concept. Use `asyncio.get_event_loop().run_in_executor(None, self.cover_gen.generate, ...)` for cover generation (it's sync). If `metadata.title` is empty, derive from filename (same as current). Merge extracted epub tags with user-provided tags (dedupe by lowercased name). Just store `extension` and derive MIME at stream time. Build `BookCreate(uid=..., title=..., author=..., level=..., book_type=..., language=..., extension=..., file_path=filename, cover_path=cover_name, tags=...)`. On any exception, call `storage.delete_book_file` / `storage.delete_cover` for the saved paths, then re-raise.
  - `async def update(self, uid: str, update: BookUpdate, cover: UploadFile | None) -> BookRead` — fetch (raise `BookNotFoundError` if missing). If new cover provided, validate + save + delete old. Build a `BookUpdate` with only the changed fields and call `repo.update`. **Do not** rebuild a full `BookCreate` — that was the old bug. Just pass the partial update through.
  - `delete(self, uid: str) -> None` — fetch (raise `BookNotFoundError`), delete files via storage, delete row via repo.
- **No `HTTPException` imports.** No `print`. No file I/O (delegate to storage). No zip parsing (delegate to cover_gen / epub_reader).

**Verify:**
```bash
cd backend
python -c "
from app.services.book_service import BookService
from app.services.book_errors import BookNotFoundError, InvalidFileError
print('BookService importable — OK')
# Verify it no longer imports HTTPException
import inspect
src = inspect.getsource(BookService)
assert 'HTTPException' not in src, 'BookService must not import HTTPException'
print('No HTTPException in BookService — OK')
"
```

- [ ] Rewrite `app/services/book_service.py` as thin orchestration
- [ ] Verify no import errors and no `HTTPException` reference
- [ ] Commit: `git commit -m "refactor: shrink BookService to thin orchestration"`

---

## Task 12: Rewrite `book_router.py` (auth guards, Range streaming, paginated list)

**Why:** This is the API surface. Three things change: (1) every endpoint gets a `RoleChecker` guard — read for any authenticated user, write for teacher/admin; (2) streaming becomes one Range-aware endpoint instead of three; (3) list and search merge into one paginated `GET /books`. The router also becomes the single place that maps service-layer exceptions to HTTP status codes.

**Concept — RoleChecker (you've seen this in auth_router):**
```python
from app.dependencies.auth import get_current_user, RoleChecker
from app.models import Account, RoleEnum

@router.post("/", response_model=BookRead, status_code=201)
async def upload_book(
    ...,
    book_service: BookService = Depends(get_book_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin])),
):
    ...
```
`RoleChecker([RoleEnum.student, RoleEnum.teacher, RoleEnum.admin])` = any authenticated user (all three roles). `RoleChecker([RoleEnum.teacher, RoleEnum.admin])` = write-only.

**Concept — HTTP Range / 206 Partial Content:**
```python
from fastapi import Request
from fastapi.responses import StreamingResponse

@router.get("/{uid}/stream")
async def stream_book(uid: str, request: Request, db: Session = Depends(get_db), current_user = Depends(RoleChecker([RoleEnum.student, RoleEnum.teacher, RoleEnum.admin]))):
    file_path = ...  # resolve
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        # parse "bytes=start-end"
        start, end = parse_range(range_header, file_size)
        length = end - start + 1
        def iter_range():
            with file_path.open("rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk: break
                    remaining -= len(chunk)
                    yield chunk
        return StreamingResponse(iter_range(), media_type=media_type, status_code=206, headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
        })
    # no Range header — stream the whole file
    return StreamingResponse(iter_file(file_path), media_type=media_type, headers={
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
    })
```
`Accept-Ranges: bytes` tells the client the server supports range requests. `Content-Range` is required on 206 responses. Parse `bytes=start-end` (handle `bytes=start-` meaning "to end"). Search for: "HTTP Range requests FastAPI StreamingResponse 206".

**Concept — Exception mapping:**
```python
@router.delete("/{uid}", status_code=204)
async def delete_book(uid: str, book_service = Depends(get_book_service), current_user = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin]))):
    try:
        book_service.delete(uid)
    except BookNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found")
    except OSError as e:
        logger.error("Failed to delete book: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete book")
```
Map each `BookError` subclass to its status (404 / 409 / 400). Map `OSError` → 500. Map `ValueError` → 400. Log server errors before raising.

**Hints for `app/api/book_router.py`:**
- Rewrite the whole file. Router prefix stays `/books`, tags stay `["books"]`.
- Imports: `APIRouter`, `Depends`, `File`, `Form`, `HTTPException`, `Query`, `UploadFile`, `Request` from `fastapi`; `StreamingResponse` from `fastapi.responses`; `Session` from `sqlalchemy.orm`; `logging`
- Import `get_db`, `settings`, `BookService`, `BookRepo`, the schemas, `RoleChecker`, `get_current_user`, `Account`, `RoleEnum`, the `BookError` hierarchy
- `logger = logging.getLogger(__name__)`
- `get_book_service(db: Session = Depends(get_db)) -> BookService` — wire up `BookRepo(db)` + the four service helpers (`BookFileStorage`, `ContentValidator`, `CoverGenerator`, `EpubMetadataReader`). The helpers that don't need `db` can be instantiated once at module level or per-request — per-request is simpler.
- Endpoints:
  - `GET /` — paginated list + search. Query params: `q`, `level`, `book_type`, `language`, `extension` (all `str | None = None`), `tags: str | None = None` (comma-separated, parse to list), `metadata` (skip this one — complex query param; note in a comment that metadata search is available via the schema but not exposed as a query param yet), `limit: int = Query(20, ge=1, le=100)`, `offset: int = Query(0, ge=0)`. Build `BookSearchCriteria` from the params. Auth: `RoleChecker([RoleEnum.student, RoleEnum.teacher, RoleEnum.admin])`. `response_model=Page[BookRead]`.
  - `GET /{uid}` — detail. `response_model=BookRead`. Auth: any. Map `BookNotFoundError` → 404.
  - `GET /{uid}/stream` — Range streaming per the concept above. Auth: any. Derive `media_type` from `book.extension`. Parse the Range header (write a helper `_parse_range(range_header: str, file_size: int) -> tuple[int, int]`).
  - `POST /` — upload. Form params: `title`, `author`, `level`, `book_type`, `language` (all `str | None = Form(None)`), `tags: str = Form("")` (comma-separated → parse to `list[TagCreate]`), `file: UploadFile = File(...)`, `cover: UploadFile | None = File(None)`. Build `BookUpload`. Auth: `RoleChecker([RoleEnum.teacher, RoleEnum.admin])`. `response_model=BookRead`, `status_code=201`. Map `InvalidFileError` → 400, `BookExistsError` → 409, `OSError` → 500.
  - `PUT /{uid}` — update. Form params: `title`, `author`, `level`, `book_type`, `language`, `tags`, `cover: UploadFile | None = File(None)`. Build `BookUpdate` from the non-None values. Auth: teacher/admin. `response_model=BookRead`. Map `BookNotFoundError` → 404, `InvalidFileError` → 400, `OSError` → 500.
  - `DELETE /{uid}` — delete. `status_code=204`. Auth: teacher/admin. Map `BookNotFoundError` → 404, `OSError` → 500.
- **Remove** `/upload`, `/search/`, `/{uid}/epub`, `/{uid}/read` — all gone.
- Helper `_iter_file(path: Path, chunk_size: int = 256 * 1024) -> Iterator[bytes]` — same as current.
- Helper `_parse_range(range_header: str, file_size: int) -> tuple[int, int]` — parse `bytes=start-end`; handle `bytes=start-` (end = file_size - 1); clamp to file bounds.
- Search for: "FastAPI Form UploadFile multipart", "HTTP 206 Partial Content Content-Range", "FastAPI Query validation ge le"

**Verify:**
Start the server and test via Swagger UI (`http://localhost:8000/docs`):
```bash
cd backend
uvicorn app.main:app --reload
```
1. `GET /books` without a token → 401 (auth required now)
2. Log in as a student (`POST /auth/token`), use the token, `GET /books` → 200 with `{"items": [], "total": 0, "limit": 20, "offset": 0}`
3. As a student, `POST /books` → 403 (write requires teacher/admin)
4. Log in as a teacher, `POST /books` with a small PDF → 201 with the book object
5. `GET /books/{uid}/stream` with header `Range: bytes=0-99` → 206, `Content-Range: bytes 0-99/<size>`, body is the first 100 bytes
6. `GET /books/{uid}/stream` without Range → 200, full file
7. `GET /books?q=<part-of-title>` → 200, filtered list
8. `PUT /books/{uid}` with a new title → 200, updated book
9. `DELETE /books/{uid}` → 204
10. `GET /books/{uid}` → 404

- [ ] Rewrite `app/api/book_router.py`
- [ ] Test each endpoint via Swagger UI with auth
- [ ] Commit: `git commit -m "feat: rewrite book router with auth guards, Range streaming, and pagination"`

---

## Task 13: Update `main.py` (if needed)

**Why:** The router import path may have changed (it shouldn't — same file). Just verify the app still starts and all routers register.

**Hints:**
- `main.py` should need no changes — `from app.api import book_router` still works.
- Verify the static mount for covers is still there: `app.mount("/static/covers", StaticFiles(directory=str(settings.COVER_DIR)), name="covers")`
- If `get_book_service` now needs the helper instances, that's wired in the router's dependency function, not `main.py`.

**Verify:**
```bash
cd backend
uvicorn app.main:app --reload
# Should start without errors
# Swagger UI at http://localhost:8000/docs should show all book endpoints with the lock icon (auth required)
```

- [ ] Verify app starts cleanly
- [ ] Commit (only if anything changed): `git commit -m "chore: verify main.py compatibility with book refactor"`

---

## Task 14: Create test fixtures (`conftest.py`)

**Why:** Tests need a clean, isolated database. Because you're on PostgreSQL, you can't use in-memory SQLite — JSONB operators behave differently. Instead, use a dedicated `jirani_library_test` database that gets dropped and recreated per test session. This keeps tests fast and hermetic without diverging from production's DB semantics.

**Concept — Postgres test fixture:**
```python
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.config import settings

TEST_DB_NAME = "jirani_library_test"
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/jirani_library", f"/{TEST_DB_NAME}")

@pytest.fixture(scope="session")
def db_engine():
    # Connect to the default DB to create the test DB
    admin_engine = create_engine(settings.DATABASE_URL)
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()
    # Now connect to the test DB and create tables
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    # Teardown: drop the test DB
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin_engine.dispose()

@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```
Per-test: get a session, rollback after (so tests don't pollute each other). Per-session: create the test DB once, drop it at the end.

**Concept — FastAPI dependency override for tests:**
```python
@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```
This makes the app use the test DB session instead of the real one.

**Hints for `app/tests/conftest.py`:**
- Create the file. You'll need `pytest`, `TestClient` from `fastapi.testclient`, the imports above.
- Use `scope="session"` for the engine fixture (create/drop the DB once per pytest run)
- Use `scope="function"` for the session and client fixtures (fresh per test)
- You also need an auth fixture — a helper that creates a teacher account and returns a valid token, so book tests can call write endpoints. Look at how `auth_service` creates users and tokens, and replicate that in a fixture. Or simpler: create the account directly via `AuthRepo` + `AuthService` in the fixture.
- Search for: "pytest FastAPI TestClient dependency override", "pytest PostgreSQL test database"

**Verify:**
```bash
cd backend
python -m pytest app/tests/conftest.py --collect-only  # should not error
```

- [ ] Create `app/tests/conftest.py` with Postgres test DB + auth fixtures
- [ ] Verify pytest can collect it
- [ ] Commit: `git commit -m "test: add Postgres test fixtures for book tests"`

---

## Task 15: Write book tests

**Why:** Tests prove the refactor works and protect you from breaking it later. They're also the spec's Definition of Done. Cover CRUD, search (including JSONB metadata), pagination, Range streaming, and auth guards.

**Concept — Testing uploads with TestClient:**
```python
from fastapi.testclient import TestClient
import io

def test_upload_pdf(client, teacher_token):
    fake_pdf = io.BytesIO(b"%PDF-1.4\nfake content")
    fake_pdf.name = "test.pdf"
    resp = client.post(
        "/books/",
        headers={"Authorization": f"Bearer {teacher_token}"},
        data={"title": "Test Book", "author": "Alice"},
        files={"file": ("test.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Test Book"
    assert resp.json()["author"] == "Alice"
```
`TestClient` handles multipart uploads via the `files=` arg. `data=` carries form fields. `headers=` carries the auth token.

**Hints for `app/tests/test_books.py`:**
- Test cases to write (one `def test_...` per case):
  1. `test_upload_pdf_happy_path` — 201, response has `uid`, `title`, `author`, `extension == "pdf"`, `cover_url` populated
  2. `test_upload_epub_happy_path` — 201, epub extracted tags appear in response
  3. `test_upload_invalid_extension` — `.docx` → 400
  4. `test_upload_bad_magic_bytes` — file named `.pdf` but content isn't `%PDF-` → 400
  5. `test_upload_too_large` — mock or set a tiny `MAX_UPLOAD_SIZE` → 400 (skip if hard to mock)
  6. `test_list_empty` — `GET /books/` → 200, `{"items": [], "total": 0, "limit": 20, "offset": 0}`
  7. `test_list_with_pagination` — upload 3 books, `GET /books/?limit=2&offset=0` → 2 items, total 3; `?offset=2` → 1 item
  8. `test_search_by_title` — upload "Alice in Wonderland", `GET /books/?q=Alice` → 1 result
  9. `test_search_by_q_matches_author` — upload with `author=Alice`, `GET /books/?q=Alice` → 1 result (q matches author too)
  10. `test_search_by_level` — upload with `level=level 1`, `GET /books/?level=level%201` → 1 result
  11. `test_search_by_book_type` — upload with `book_type=storybook`, `GET /books/?book_type=storybook` → 1 result
  12. `test_search_by_language` — upload with `language=en`, `GET /books/?language=en` → 1 result
  13. `test_search_by_tags` — upload with tags `["math", "algebra"]`, `GET /books/?tags=math` → 1 result
  14. `test_search_combined` — upload two books with different level + tags, combine `?level=level%201&tags=math` → only matching book returned
  15. `test_get_by_uid` — upload, then `GET /books/{uid}` → 200, full detail
  16. `test_get_by_uid_not_found` — `GET /books/nonexistent` → 404
  17. `test_stream_without_range` — `GET /books/{uid}/stream` → 200, `Content-Length` set, body is the full file
  18. `test_stream_with_range` — `GET /books/{uid}/stream` with `Range: bytes=0-99` → 206, `Content-Range: bytes 0-99/<size>`, body is 100 bytes
  19. `test_stream_not_found` — `GET /books/nonexistent/stream` → 404
  20. `test_update_metadata` — upload, then `PUT /books/{uid}` with new `author` and `tags` → 200, both changed, other fields preserved
  21. `test_update_cover` — upload, then `PUT` with a new cover file → 200, `cover_path` changed (and old cover file deleted — verify by checking the path)
  22. `test_delete` — upload, then `DELETE /books/{uid}` → 204, then `GET /books/{uid}` → 404
  23. `test_delete_not_found` — `DELETE /books/nonexistent` → 404
  24. `test_student_cannot_upload` — student token, `POST /books/` → 403
  25. `test_student_cannot_delete` — student token, `DELETE /books/{uid}` → 403
  26. `test_student_can_read` — student token, `GET /books/` → 200
  27. `test_unauthenticated_blocked` — no token, `GET /books/` → 401
- Use the `client` and `teacher_token` / `student_token` fixtures from `conftest.py`
- For fake PDFs/EPUBs: `io.BytesIO` with the right magic bytes (`b"%PDF-1.4\n..."` for PDF, `b"PK\x03\x04..."` for EPUB — a minimal valid ZIP is harder; for invalid-magic tests just use wrong bytes)
- Run: `pytest app/tests/test_books.py -v`

**Verify:**
```bash
cd backend
python -m pytest app/tests/test_books.py -v
# All tests should pass
```

- [ ] Create `app/tests/test_books.py` with the test cases above
- [ ] Run tests and make them all pass
- [ ] Commit: `git commit -m "test: add book feature tests"`

---

## Task 16: Logging pass — replace every `print` with `logging`

**Why:** `print()` is for development debugging. `logging` is for production: it has levels (DEBUG/INFO/WARNING/ERROR), can be routed to files or syslog, and can be silenced per-module. This is a best-practice cleanup pass across all the new book modules.

**Hints:**
- In each of the new service modules (`book_file_storage.py`, `cover_generator.py`, `content_validator.py`, `epub_metadata_reader.py`, `book_service.py`) and the router (`book_router.py`), add `import logging` and `logger = logging.getLogger(__name__)` at the top.
- Replace every `print(...)`:
  - `print(f"starting file save")` → `logger.info("starting file save")`
  - `print(f"Warning: Failed to delete old cover: {e}")` → `logger.warning("failed to delete old cover: %s", e)`
  - `print(f"Thumbnail extraction failed: {e}")` → `logger.error("thumbnail extraction failed: %s", e)`
  - `print(f"DEBUG: found cover via ...")` → `logger.debug("found cover via %s", ...)` (or just delete the debug prints — they were development noise)
- Use `%s`-style formatting in log calls (not f-strings) — the logging module lazy-formats, so if the log level is disabled the string is never built. Search: "Python logging lazy formatting".
- Verify no `print` remains:
  ```bash
  cd backend
  grep -rn "print(" app/services/book_file_storage.py app/services/cover_generator.py app/services/content_validator.py app/services/epub_metadata_reader.py app/services/book_service.py app/api/book_router.py
  # Should return nothing
  ```

**Verify:**
```bash
cd backend
grep -rn "print(" app/services/book_*.py app/services/cover_generator.py app/services/content_validator.py app/services/epub_metadata_reader.py app/api/book_router.py
# No output = all prints replaced
```

- [ ] Replace all `print(...)` with `logging` calls in the new modules
- [ ] Verify no `print` remains
- [ ] Commit: `git commit -m "refactor: replace print statements with logging in book modules"`

---

## Task 17: Final verification — lint, type check, tests

**Why:** The AGENTS.md Definition of Done requires all four checks to pass. This is the gate before the refactor is considered complete.

**Steps:**
- [ ] Format:
  ```bash
  cd backend
  ruff format .
  ```
- [ ] Lint (auto-fix what it can):
  ```bash
  ruff check . --fix
  ```
  If issues remain that `--fix` can't resolve, read them and fix manually. Common ones: unused imports, missing type hints.
- [ ] Type check (strict):
  ```bash
  mypy . --strict
  ```
  This is the hardest one. Common issues:
  - Missing return type annotations on functions — add them
  - `Any` types — narrow them where possible (JSONB `dict[str, Any]` is acceptable; annotate it explicitly)
  - `None` returns — annotate as `-> None`
  - `session.execute(...).scalar_one_or_none()` returns `T | None` — handle the None case explicitly
  Fix each error. If a third-party library (e.g. PyMuPDF) has no type stubs, add `# type: ignore[import-untyped]` on the import line with a comment explaining why.
- [ ] Tests:
  ```bash
  pytest -v -k "book"
  ```
  All book tests should pass.
- [ ] Commit: `git commit -m "chore: final lint, type check, and tests pass for book refactor"`

---

## What you learned

After completing this plan, you will have hands-on experience with:

- **SQLAlchemy 2.0** — `Mapped[T]`, `mapped_column()`, `select()` + `execute()` style, `joinedload` + `unique()`
- **PostgreSQL JSONB** — native type, GIN indexes, `@>`/`?`/`->>` operators in SQLAlchemy
- **Extensible search design** — one criteria object + one dynamic builder; typed columns for hot fields, JSONB for ad-hoc fields with zero migration
- **Pydantic v2** — `ConfigDict`, `computed_field`, layered schemas, generic `Page[T]`, all-optional `BookUpdate` for partial updates
- **God class decomposition** — splitting one 567-line service into five focused, testable modules
- **HTTP Range / 206 Partial Content** — seekable streaming for pdf.js / epub.js
- **FastAPI auth** — `RoleChecker` dependency for RBAC on every endpoint
- **Error layering** — services raise domain errors, routers map to HTTP status codes (no `HTTPException` in services)
- **Logging vs print** — lazy-formatted, leveled logging
- **Pagination** — `limit`/`offset` + `total` count
- **Test design** — Postgres test DB fixtures, multipart upload testing, auth-guard testing
- **Postgres schema reset workflow** — `DROP TABLE ... CASCADE` when you don't have Alembic yet
