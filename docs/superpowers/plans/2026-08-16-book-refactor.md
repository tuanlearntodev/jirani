# Book Refactor Implementation Plan (rescoped 2026-08-20, learner edition 2026-08-24)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Learner mode (2026-08-24):** full implementations were deliberately removed from this plan at the user's request. What remains is the *contract* (signatures, expected outputs, red errors, gates) and *samples* of the novel idioms — you write the rest yourself. References when stuck: (1) the governing spec `docs/superpowers/specs/2026-08-16-book-refactor-design.md` (detailed designs); (2) git history — `git show <commit>^:docs/superpowers/plans/2026-08-16-book-refactor.md` before this edit carries the complete paste-ready version. TDD is binding (AGENTS.md): a step that says "write the failing test" must be red before you touch the implementation.

**Goal:** Finish the book feature refactor — streaming, epub + pdf CRUD, extensible search — on PostgreSQL, fixing the four Critical defects found in review of the 2026-07-03 plan.

**Explicitly out of scope this pass:** the audio / video / tag test suites and their delete-missing 500s, plus the two features this plan deliberately drops (cover replacement on PUT; epub→pdf conversion and `/read`). They are preserved verbatim in the Deferred Work annex at the bottom so nothing is lost. The audio/video routers are untouched here — hygiene S3 already re-anchored their upload paths, and Part A's `BookFileStorage` learns from that lesson rather than re-litigating it.

**Architecture:** Five focused service modules replace the 605-line `BookService` god class; a SQLAlchemy 2.0 `Mapped[]` model with JSONB `metadata_`; a `BookSearchCriteria` object driving a dynamic query builder with `selectinload` + `tags.any()` + explicit `ORDER BY`; a single RFC 7233 Range-aware streaming endpoint; `RoleChecker` on every endpoint. Tests run on the committed testcontainers harness (`backend/app/tests/conftest.py`, `361bb48`): `db`, `client`, `setup_paths`, plus module-level `setup_admin`/`login`/`auth_headers`. Since hygiene S1 (commit `467beee`) `app.tests` is a real package, so those helpers are importable rather than an artifact of pytest path insertion. One harness trap survives: **call `db.expire_all()` before reading via `db` after a write through `client`** — the long-lived session's identity map otherwise returns stale objects.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests), PyMuPDF, uv, pytest/httpx, ruff, mypy.

**Governing design:** `docs/superpowers/specs/2026-08-16-book-refactor-design.md`. Read it first. This plan implements that spec; where they appear to disagree, the spec wins.

## Global Constraints

Every task implicitly includes all of the following. Exact values copied from the spec.

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; no `docker compose up -d db` needed for tests
- `ruff check` with `--ignore B008` on changed files; `mypy --strict` on changed files only, per the **Debt Coverage Annex** below — it replaces the old "103 errors / 24 files" baseline with a per-file ledger, and every row has an owning task. Log pre-existing failures owned by *other* plans in STATE.md; do not fix unrelated files
- Commit after every task; message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- Never delete a failing test to make the suite pass — fix the underlying logic (AGENTS.md)
- After the final task, run `graphify update .` (AST-only)
- **Locked decisions:** tag filtering is **OR**; `metadata_` uses **containment (`@>`)**; `cover_url` lives on **`BookRead` only**; the `file_type` hotfix runs first (Task 0)
- **Prerequisites (external, not tasks here):** hygiene **S1 landed** (commit `467beee` — `app.tests` is a package, `from app.config import settings` is the only import form in the tree) and hygiene **S2/S3 landed** (single manifest; `UPLOAD_DIR`/`COVER_DIR` already BASE_DIR-anchored). Hygiene **S5 (Alembic)** landed and does not block here: this plan touches no schema, so no migration is needed. Tasks 2 and 5 use the S1 import form throughout.

## Corrections to the previous plan

The prior revision of this document — and its ancestor `docs/plans/2026-07-03-book-refactor-plan.md`, recovered from git (`git show 7ef380a^:docs/plans/2026-07-03-book-refactor-plan.md`) — was audited against the working tree on 2026-08-20. Five claims were wrong or stale. Their corrections are folded into the tasks below.

| # | Previous claim | Verified reality | Consequence |
|---|---|---|---|
| 1 | "current tree code uses `from app import settings` (`book_service.py:9`); hygiene S1 changes it to `from app.config import settings`" (Task 2 Step 3) | **S1 already landed** (commit `467beee`, 2026-08-16): the tree imports `from app.config import settings` | The note was written in future tense. The S1 form is the only form; the "both forms are stated where relevant" caveat is retired, and the in-task note is updated |
| 2 | Test Harness Reference trap: "Never add `backend/app/tests/__init__.py`" — it would make `app.tests` importable and trigger `app/__init__.py`'s eager imports at collection time | **Both halves are outdated.** S1 created `backend/app/tests/__init__.py` **and** stripped the eager subpackage imports from `app/__init__.py` (commit `467beee`) | `from app.tests.conftest import setup_admin, login, auth_headers` is now safe. Task 5a's inline login replication is kept only because it makes the probe files self-contained — the necessity is gone |
| 3 | 2026-07-03 plan: "Task 2: Rewrite the `Book` model…" — model is 1.x `Column()` style | **Already done.** `Book` is SQLAlchemy 2.0 `Mapped[]` with JSONB `metadata_` and the GIN index (`models/book.py:13,23,30`) | No model task in this plan; Tasks 0–5 touch no schema. A future model change runs through hygiene S5's Alembic |
| 4 | 2026-07-03 plan: "`app/tests/conftest.py` **Create** — Postgres test DB fixture (drop/create per session)" | The **testcontainers harness is committed** (`361bb48`): session-scoped `postgres:16-alpine`, autouse `reset_db`, `db`/`client`/`setup_paths` + `setup_admin`/`login`/`auth_headers` | Zero conftest work in this plan; the harness is consumed as-is |
| 5 | 2026-07-03 plan: god class is "567 lines" | **605 lines** as of 2026-08-20 — it grew 38 lines after the old plan was written | Cosmetic. The target (thin orchestration) is unchanged; Task 5b's rewrite is 605 → ~130 lines |

## Current State (verified against the tree, 2026-08-20)

| Area | State | Where |
|---|---|---|
| `BookService` god class | 🔴 605 lines — file save, magic-byte validation, cover generation, epub→pdf conversion, tag extraction and DB orchestration in one file | `backend/app/services/book_service.py` |
| `BookRepo` | 🔴 Legacy 1.x `query()` + `joinedload`; filters hardcoded per method | `backend/app/repositories/book_repo.py:15,26,36,54,58,86,114` |
| Search `file_type` defect | 🔴 LIVE — filters on `Book.file_type`, a column that does not exist → `AttributeError` (500) on `/books/search/` | `book_repo.py:122-123` |
| MIME never persisted | 🔴 LIVE — `file_type=` kwarg to `BookCreate` silently dropped (`extra="ignore"`) | `book_service.py:226` |
| Update reads dead attr | 🔴 LIVE — `file_type=existing_book.file_type` on the same nonexistent attribute | `book_service.py:326` |
| Router auth | 🔴 Zero `RoleChecker` / `get_current_user` — all 8 endpoints open | `book_router.py:47-189` |
| Streaming | 🔴 Three endpoints (`/stream` ignores `Range`, `/epub`, `/read`); `print("router hit")` debug call | `book_router.py:101,118,189,54` |
| `cover_url` schema leak | 🔴 `@computed_field` on `BookBase` → leaks onto the `BookCreate` write schema | `book_schema.py:24-26` |
| Book model | ✅ Already 2.0 — `Mapped[]`, JSONB `metadata_`, GIN index; no model task needed | `backend/app/models/book.py:13,23,30` |
| Book tests | 🔴 Zero — the suite contains only `test_auth.py` | `backend/app/tests/` |
| Test harness | ✅ testcontainers Postgres, session-scoped; `app.tests` importable as a package since S1 | `backend/conftest.py`, `backend/app/tests/__init__.py` |

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/services/book_errors.py` | Create | 1 | `BookError` base; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed` |
| `backend/app/services/content_validator.py` | Create | 1 | `validate(bytes, filename) -> str` (extension); raises `InvalidBookFile` |
| `backend/app/services/book_file_storage.py` | Create | 2 | `save(bytes, filename, uid) -> str`; `delete(rel_path) -> None`; `resolve(rel_path) -> Path` with UPLOAD_DIR containment |
| `backend/app/services/epub_metadata_reader.py` | Create | 3 | `read(path) -> BookMetadata \| None` |
| `backend/app/services/cover_generator.py` | Create | 4 | `generate(src, dest) -> bool`; returns `False` on failure, never raises |
| `backend/app/services/book_service.py` | Rewrite | 0, 5 | Hotfix call sites; then thin orchestration over the four modules + `BookRepo` |
| `backend/app/repositories/book_repo.py` | Rewrite | 0, 5 | `file_type` fix in place; then `search(criteria) -> Page[BookRead]`; 2.0 `select()` |
| `backend/app/api/book_router.py` | Rewrite | 5 | `RoleChecker` + Range streaming + pagination + error mapping |
| `backend/app/schemas/book_schema.py` | Modify | 0 | Move `cover_url` from `BookBase` to `BookRead` |
| `backend/app/schemas/book_schema.py` (`BookUpload`) | — | — | Unchanged; reused by the router |
| `backend/app/tests/test_book_search.py` | Create | 0, 5 | Task 0 hotfix probe; Part B C1 search correctness + pagination probes |
| `backend/app/tests/test_book_validator.py` | Create | 1 | ContentValidator unit tests |
| `backend/app/tests/test_book_storage.py` | Create | 2 | Storage round-trip + C4 traversal |
| `backend/app/tests/test_book_epub_reader.py` | Create | 3 | EpubMetadataReader unit tests |
| `backend/app/tests/test_book_cover.py` | Create | 4 | CoverGenerator unit tests |
| `backend/app/tests/test_book_stream.py` | Create | 5 | C3 Range cases + C4 traversal |
| `backend/app/tests/test_book_upload.py` | Create | 5 | Happy path + rejection |

## Debt Coverage Annex (approved 2026-08-23 — reference snapshot, not a maintained ledger)

Every task in this plan carries the same lint/type gate: the files it touches end the task with **0 `ruff` + 0 `mypy --strict` errors** (`uv run ruff check <files> --ignore B008`, `uv run mypy <files> --strict`). New violations fail the task; pre-existing errors in a touched file are that task's debt to clear. The table records the S6 snapshot (ruff 0.16.3 — the auto-fix pass already consumed the fixable half) with a named owner per file for orientation:

| File | ruff | mypy | Owning task |
|---|---|---|---|
| `app/services/book_service.py` | 15 | 17 | 0 (hotfix lines) → 5 (fused rewrite) |
| `app/api/book_router.py` | 3 | 22 | 5 |
| `app/repositories/book_repo.py` | 2 | 1 | 0 (rename touch) → 5 (2.0 rewrite) |
| `app/schemas/book_schema.py` | 0 | 2 | 0 (`cover_url` move) |
| `app/models/book.py`, `book_tag.py` | 0 | 3 | 5/6 |
| `app/models/tag.py` | 0 | 1 | — |
| `app/schemas/tag_schema.py` | 2 | 0 | — |
| `app/repositories/tag_repo.py` | 0 | 2 | — |
| `app/api/tag_router.py` | 0 | 1 | — |

The tag module plus `audio_router`/`video_router`/audio-video repos + models are owned by the **future audio/video/tag plan** (user 2026-08-23, mirroring D1's bundle), and the auth/config/database files by the hygiene plan — red rows on other plans' files are expected until those plans run. **Task 6 verifies this plan's own files are clean.**

# PART A — Hotfix + leaf modules

Part A makes the tree safe and builds the four pure leaf modules the fused rewrite consumes. Task 0 fixes the shipped 500s and schema leak in place; Tasks 1–4 ship one unit-tested module each, all with their own commit. Nothing in Part A touches HTTP behavior beyond the Task 0 defect fixes. Each task is green independently — Part B reuses their outputs without modifying them.

### Task 0: `file_type` hotfix + `cover_url` move

> **Lint/type gate:** touched files end at 0 ruff + 0 `mypy --strict` — the `cover_url` move and the rename touch are the first bites at `book_schema.py`/`book_repo.py`.

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

**Why (learning):** `Book.file_type` does not exist — the column is `book_type`. Three live sites raise `AttributeError` (500) today, and a fourth threads the dead param through the service signature. Fix the tree before refactoring, rather than carrying shipped 500s through six more commits.

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_search.py`. It needs two seeded books whose `book_type` differs, then asserts `BookRepo(db).search_books(book_type="pdf")` returns only the PDF one — and the test's whole point is that the *filter must address `Book.book_type`*.

Sample — the seeding idiom (a helper that inserts a `Book` row and commits):
```python
def _seed_book(db, *, uid: str, book_type: str) -> None:
    db.add(Book(uid=uid, title=f"Title {uid}", book_type=book_type,
                extension="pdf", file_path=f"{uid}.pdf", metadata_={}))
    db.commit()
```
Test list (write the bodies yourself): seed `bk0001` (`application/pdf`) + `bk0002` (`application/epub+zip`); assert `[b.uid for b in BookRepo(db).search_books(book_type="pdf")] == ["bk0001"]`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_search.py -v
```

Expected: FAIL with `AttributeError: type object 'Book' has no attribute 'file_type'`. (Docker daemon required — the harness starts a `postgres:16-alpine` container.)

- [ ] **Step 3: Rename the parameter and map to `book_type` in the repo**

In `backend/app/repositories/book_repo.py`: change the `search_books` signature parameter `file_type` → `book_type`, and the filter site from `Book.file_type.ilike(...)` to `Book.book_type.ilike(...)`. Hint: nothing else in this method changes — the rename is the fix.

- [ ] **Step 4: Move `cover_url` off `BookBase`**

In `backend/app/schemas/book_schema.py`: delete the `@computed_field` block from `BookBase`; add it to `BookRead`. `cover_path` stays on `BookBase` — only the computed URL moves. The idiom (computed property on a Pydantic model) — the body is yours to write:

```python
@computed_field
@property
def cover_url(self) -> str | None:
    if not self.cover_path:
        return None
    return f"/static/covers/{self.cover_path}"
```

- [ ] **Step 5: Fix the service call sites**

In `backend/app/services/book_service.py`: (1) remove the `file_type` parameter from `search_books` and its kwarg at the repo call (~lines 36-48); (2) ~line 223-231 change `file_type=` → `book_type=` in the `BookCreate(...)` for uploads; (3) ~line 323-331 change `file_type=existing_book.file_type` → `book_type=existing_book.book_type`. Hint: three mechanical renames — do not touch anything else in those functions.

- [ ] **Step 6: Drop the now-dead `cover_url` exclusion**

In `backend/app/repositories/book_repo.py` (lines 23 and 77): with `cover_url` gone from `BookCreate`, `model_dump(exclude={"tags", "cover_url"})` shrinks to:

```python
book_dict = book_create.model_dump(exclude={"tags"})
```
(ditto for `book_update`). Hint: the `exclude` set is the *only* edit per site.

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

Expected: no new mypy errors against the Annex ledger; ruff clean after format.

- [ ] **Step 9: Commit**

```bash
cd backend && git add app/repositories/book_repo.py app/services/book_service.py app/schemas/book_schema.py app/tests/test_book_search.py
git commit -m "fix: map search file_type to book_type; move cover_url to BookRead"
```

---

### Task 1: `book_errors.py` + `ContentValidator`

> **Lint/type gate:** the new modules are new files — they ship clean (0/0); the final lint+commit step covers them, and no new violations in touched files.

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

**Why (learning):** The domain exception hierarchy and the upload gate are the two leaves every later module depends on. Both are pure Python — no HTTP, no `open()`, no DB — so they are unit-testable in isolation and the tree stays green.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_book_validator.py`. Five pure-Python cases to pin:
1. empty bytes → `InvalidBookFile`
2. `.exe` filename → `InvalidBookFile`
3. `b"not a real pdf"` named `.pdf` → `InvalidBookFile` (magic bytes)
4. oversized payload → `InvalidBookFile` — use `monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)` with a >10-byte payload
5. `b"%PDF-1.4 ..."` named `Report.PDF` → returns `"pdf"`; `b"PK\x03\x04 ..."` named `book.EPUB` → returns `"epub"` (magic sniffing only — stub bytes are enough)

Sample — the failure idiom:
```python
from app.services.book_errors import InvalidBookFile
from app.services.content_validator import ContentValidator

def test_empty_file_rejected() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"", "book.pdf")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_validator.py -v
```

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.book_errors'`. (Docker daemon required — the harness starts a `postgres:16-alpine` container even for these pure-Python tests.)

- [ ] **Step 3: Create the domain exception hierarchy**

Create `backend/app/services/book_errors.py`. Design: a base `BookError(Exception)` holding `detail: str`, defaulting from a per-class `default_detail`; four subclasses each setting only `default_detail`. Hint: the base's `__init__` takes an optional `detail` and falls back to `default_detail`; no HTTP types anywhere (Invariant 2 — the router translates).

- [ ] **Step 4: Create `ContentValidator`**

Create `backend/app/services/content_validator.py`. Validation order matters — guards run before any byte reaches disk:
1. empty bytes → reject
2. `len(file_bytes) > settings.MAX_UPLOAD_SIZE` → reject
3. extension not in `settings.ALLOWED_EXTENSIONS` → reject
4. magic-byte check → reject on mismatch
5. return the lowercase extension

Sample — the one non-obvious piece, magic bytes:
```python
_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF-",
    "epub": b"PK\x03\x04",
}
```
Hint: every rejection raises `InvalidBookFile("human explanation")`; the extension parsing uses `filename.rsplit(".", 1)`.

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

Expected: ruff clean after format; mypy reports no errors for these two files (0 new against the Annex).

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/services/book_errors.py app/services/content_validator.py app/tests/test_book_validator.py
git commit -m "feat: add book domain errors and ContentValidator upload gate"
```

---

### Task 2: `BookFileStorage` (incl. `resolve()` containment)

> **Lint/type gate:** ships clean (0/0) — the storage module is the pattern Tasks 3–4 copy; no new violations in touched files.

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

**Why (learning):** `resolve()` centralises path-traversal containment so the router can never open a book file except through the guard. A DB-supplied `file_path` joined naively to `UPLOAD_DIR` escapes via `..` — today the tree is safe only because the write path incidentally strips traversal. One guard, unit-testable in isolation, instead of duplicated per call site.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_book_storage.py`. Seven cases: traversal rejected (`resolve("../../../../etc/passwd")` raises `BookNotFound`); resolve of a saved path lands inside `tmp_path/books`; save returns a relative single-component name containing the uid and ending with the sanitized extension; a hostile filename (`"../../etc/evil; rm -rf.pdf"`) survives with no `..`, `/`, `\`, or space; `delete`/`delete_cover` on missing files are silent; `cover_dir` accessor returns the monkeypatched dir.

Sample — the fixture idiom (redirects the module's settings to a tmp dir for isolation):
```python
@pytest.fixture()
def storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BookFileStorage:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    return BookFileStorage()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_storage.py -v
```

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.book_file_storage'`.

- [ ] **Step 3: Create `BookFileStorage`**

Create `backend/app/services/book_file_storage.py`. Three pieces:
1. A `safe_filename(filename, uid)` helper — strip directory components (`Path(name).name`), sanitize the stem with `re.sub`, bind the uid, keep only `[a-z0-9]` in the extension.
2. `save` — mkdir parents, write bytes via the helper, return just the name (a relative single component — that's the containment property).
3. The C4 core — `resolve` must contain the result:

Sample — the containment check (mirror it in `delete_cover` against `COVER_DIR`):
```python
base = self.upload_dir.resolve()
resolved = (base / rel_path).resolve()
if not resolved.is_relative_to(base):
    raise BookNotFound(f"Invalid book file path: {rel_path!r}")
if not resolved.is_file():
    raise BookNotFound(f"Book file not found: {rel_path!r}")
return resolved
```

Hint: `delete` swallows `BookNotFound` and `OSError` (log at warning); `cover_dir` is a `@property`; imports are the S1 form `from app.config import settings`. Do **not** export from `app/services/__init__.py`.

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

Expected: ruff clean after format; mypy reports no errors for this file (0 new).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/book_file_storage.py app/tests/test_book_storage.py
git commit -m "feat: add BookFileStorage with UPLOAD_DIR traversal containment"
```

---

### Task 3: `EpubMetadataReader`

> **Lint/type gate:** ships clean (0/0); `-> BookMetadata | None` must be honored by annotation, not suppressed.

**Files:**
- Create: `backend/app/services/epub_metadata_reader.py`
- Test: `backend/app/tests/test_book_epub_reader.py`

**Interfaces:**
- Consumes: `pymupdf` (PyMuPDF), stdlib `logging`/`re`/`dataclasses`/`pathlib`. No `app.*` imports — pure leaf.
- Produces:
  - `@dataclass(frozen=True) BookMetadata` — `title: str | None`, `author: str | None`, `language: str | None`, `tags: list[str]`
  - `EpubMetadataReader.read(path: Path) -> BookMetadata | None` — returns `None` on a corrupt or missing file; never raises

**Why (learning):** Replaces the god class's epub-tag logic with a total function whose `None` return lets the service layer (Task 5) own the filename/user-input fallback.

**Naming contract — read carefully:** the dataclass field is **`tags`**, not `subjects`. Task 5b consumes `epub_meta.tags`. (An earlier draft of this plan named it `subjects`; that name is retired to match the shipped dataclass.)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_epub_reader.py`. The fixture builds a real minimal EPUB — an EPUB is a zip: uncompressed `mimetype` entry first, `META-INF/container.xml` pointing at an OPF, one spine item. Write a `_write_minimal_epub(path)` helper using `zipfile`. Cases: corrupt bytes → `None`; missing file → `None`; good EPUB → title `"Minimal Title"`, author `"Jane Doe"`.

Sample — the zip-writing idiom:
```python
with zipfile.ZipFile(path, "w") as z:
    z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", container)
    z.writestr("OEBPS/content.opf", opf)
    z.writestr("OEBPS/ch1.xhtml", chapter)
```
Hint: the OPF carries `<dc:title>`, `<dc:creator>`, `<dc:language>` with the `xmlns:dc="http://purl.org/dc/elements/1.1/"` namespace; container.xml's rootfile `full-path` is `OEBPS/content.opf`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_epub_reader.py -v
```

Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.services.epub_metadata_reader'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/epub_metadata_reader.py`. Import **`pymupdf`**, not the `fitz` alias the legacy `book_service.py` uses: only the `pymupdf` package ships a `py.typed` marker, so `import fitz` fails mypy `--strict` as `import-untyped`. The `pymupdf.open` constructor is untyped upstream — carry a targeted `# type: ignore[no-untyped-call]` at that call site; then read `doc.metadata` (a dict), catch `(RuntimeError, ValueError, OSError)` → log + `return None`.

Sample — the one genuinely fiddly line:
```python
tags = [t.strip() for t in re.split(r"[,;]+", subjects) if t.strip()]
```
Hint: `title = meta.get("title") or None` keeps empties honest; the dataclass field `tags` defaults to `default_factory=list`. Do **not** export from `app/services/__init__.py`.

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

> **Lint/type gate:** ships clean (0/0); `-> bool` must be typed to allow `False` (best-effort contract).

**Files:**
- Create: `backend/app/services/cover_generator.py`
- Test: `backend/app/tests/test_book_cover.py`

**Interfaces:**
- Consumes: `app.config.settings` (`MAX_COVER_SIZE: int`), `pymupdf`, stdlib `zipfile`/`re`/`xml.etree.ElementTree`/`logging`
- Produces:
  - `CoverGenerator.generate(source_path: Path, dest_dir: Path) -> bool` — writes the cover into the `dest_dir` **directory**, named `{source_path.stem}.png` (the stem is the book uid per Task 2's `save`). Returns `True` only when a cover lands within `settings.MAX_COVER_SIZE`; `False` on ANY failure; never raises.

**Why (learning):** Replaces `_generate_thumbnail` with the spec's `-> bool` contract: a stub or corrupt upload degrades to a missing cover, never a failed upload.

**Signature contract — read carefully:** the second parameter is a **directory** (`dest_dir`), and the method derives the filename from `source_path.stem`. Task 5b calls it as `generate(source_path, storage.cover_dir)`. (An earlier draft passed a full file path; that is retired.)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_book_cover.py`. The happy path builds a **real** one-page PDF in-fixture — stub bytes pass magic-byte validation but are unparseable, so the happy path needs a genuine document. Cases: corrupt PDF → `False`, dest stays empty; real PDF → `True` + `bk0001.png` exists and ≤ `MAX_COVER_SIZE`; EPUB with an OPF-declared cover image → `True`; EPUB with no images → `False`; `monkeypatch.setattr(settings, "MAX_COVER_SIZE", 1)` → `False`, dest empty.

Sample — the real-PDF generator and the pixel fixture (novel PyMuPDF idioms):
```python
def _write_real_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello cover")
    doc.save(str(path))
    doc.close()

def _png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2))
    return pix.tobytes("png")
```
Hint for the EPUB-with-cover fixture: the OPF declares `<meta name="cover" content="cover-img"/>` and a manifest `<item id="cover-img" href="images/cover.png" .../>`; zip `OEBPS/images/cover.png` with `_png_bytes()`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest app/tests/test_book_cover.py -v
```

Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.services.cover_generator'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/cover_generator.py`. Port from `_generate_thumbnail` in the old god class (read it for the logic — the *contract* here is what's re-specified): PDF → page-0 render at half scale; EPUB → OPF-declared cover, then XHTML `<img>` unwrap, then first-image fallback. **Deliberately dropped:** the filename-keyword heuristic and render-the-epub's-first-page. `generate` is the boundary: private helpers may raise, `generate` converts anything to a logged `False`.

Strategy sketch (write the bodies):
- `generate`: `try:` mkdir dest; dispatch on `source_path.suffix.lower()` (".pdf"/".epub"/else log+False); `except Exception: logger.exception(...); return False`
- `_from_pdf`: page-0 `get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5))`, save as `{stem}.png`, then size-check
- `_from_epub`: extract cover bytes → write `{stem}.png` → size-check
- `_keep_if_small_enough(dest) -> bool`: unlink + `False` when over `MAX_COVER_SIZE`
- EPUB internals: find OPF path from `META-INF/container.xml` (`_local_name` — strip `{ns}` XML namespaces); read `<meta name="cover">` → item id → href; read XHTML `<img src=...>` via regex; first-image fallback over `archive.namelist()`

Sample — the tricky bits to mirror (XML namespace stripping + in-archive `..` resolution):
```python
def _local_name(tag: str) -> str:
    """Strip an XML namespace: ``{ns}item`` -> ``item``."""
    return tag.rpartition("}")[2].lower()
```
and `_join(base, rel)` — split on `/`, pop on `..`, skip `.`/empty, join back.
Hint: `pymupdf.open(str(path))` needs `# type: ignore[no-untyped-call]`; callers use `doc.load_page(0)`. Do **not** export from `app/services/__init__.py`.

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

# PART B — Fused rewrite and final gate

**Part A is complete when Tasks 0–4 are green.** Each Part A module is a pure leaf — no HTTP, no router, no composition — and every one ships with passing unit tests. Task 5 is the single commit where the leaves are wired into a rewritten repo/service/router; do not start it until the Part A steps are green, because Task 5's red-first tests fail against the old tree and the Part A commits are what let you isolate a regression to wiring rather than to a leaf.

### Task 5: FUSED rewrite of `BookRepo` + `BookService` + `book_router` (single commit)

> **Lint/type gate — the big one:** `book_service.py` (15 ruff / 17 mypy), `book_router.py` (3 / 22), `book_repo.py` (2 / 1 — the B904 `raise` sites and the `query().first()` return) and `book_schema.py` reach 0/0 by this task's final lint step.

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

**Why (learning):** Fused into one commit on purpose: rewriting `BookRepo` deletes `search_books` and `get_all_books`, which `book_service.py:33,47` and `book_router.py:81` still call. Splitting the three files across commits leaves commits where `GET /books/search/` raises `AttributeError` at call time — and the old plan's import-only gate passes anyway. One commit keeps every point in history importable and runnable, which matters because `git pull && cat STATE.md` is the cross-machine resume path. Three separated steps (5a/5b/5c) with a mypy gate after each keep it reviewable; a single commit at the end. Red-first tests come first (5a-i) and fail against the old code — intended TDD ordering, not a broken gate.

- [ ] **Step 5a-i: Write the failing tests**

Extend `backend/app/tests/test_book_search.py` (append; keep the Task 0 test). These are repo-level — they pin SQL semantics, not HTTP. Three probes:
1. `test_search_tags_or_semantics_and_honest_total` — seed 2 books, tags `["math", "algebra"]` and `["math"]`; `search(BookSearchCriteria(tags=["Math", "ALGEBRA"]), limit=2, offset=0)` must give `total == 2` and exactly `{bk0001, bk0002}` (OR semantics, case-insensitive, honest count — the old code returned 3/1)
2. `test_search_metadata_containment` — seed with `metadata_={"publisher": "Penguin"}` vs `{"publisher": "Puffin"}`; filter `BookSearchCriteria(metadata_={"publisher": "Penguin"})` → only the first (Postgres `@>` containment, GIN-served)
3. `test_search_pagination_pages_are_disjoint_and_complete` — seed 5 books; `limit=2` at offsets 0/2/4 → page uid-sets are pairwise disjoint, union == all 5, `total == 5` on every page (explicit `ORDER BY` makes LIMIT/OFFSET stable)

Sample — the seeding idiom with 2.0 `select()`:
```python
tag = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
if tag is None:
    tag = Tag(name=name)
book.tags.append(tag)
```

Create `backend/app/tests/test_book_stream.py`. Note: conftest helpers (`setup_admin`/`login`/`auth_headers`) have been importable since hygiene S1 landed, but the two-line login flow is replicated inline anyway — deliberately, so the probe carries zero dependency on `conftest.py`'s internals and a helper signature change cannot confound a red-failure diagnosis. Cases: no Range → 200 + full body + `Accept-Ranges: bytes`; `Range: bytes=0-99` → 206 + `Content-Range: bytes 0-99/1024` + exact slice; `bytes=500-` → 206 + tail; `bytes=-500` → 206 + last 500 (C3 — Safari/pdf.js); `bytes=99-0` (start>end) → 416 + `Content-Range: bytes */1024`; `bytes=1024-` (start≥size) → 416 (clamping is WRONG); `bytes=0-99,200-299` (multi) → 200 full body; a DB `file_path` of `"../../../../etc/passwd"` → 404 (C4); unauthenticated → 401/403.

Sample — the layout: `CONTENT = bytes(range(256)) * 4` (1024 bytes, position-verifiable); a `seeded_file` fixture that monkeypatches `settings.UPLOAD_DIR` to a tmp dir, writes the file, inserts a `Book` row, and returns the admin headers.

Create `backend/app/tests/test_book_upload.py` (happy path with a **real** PDF built in-fixture; stub bytes only for the magic-byte rejection test):
1. `test_upload_pdf_happy_path` — POST `/books/upload` (multipart: `data={"title": "Real PDF", "tags": "math, algebra"}`, `files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")}`) → 200, `extension == "pdf"`, tags normalized; then `db.expire_all()` (identity-map trap) and assert the `Book` row's `file_path` exists under `settings.UPLOAD_DIR`
2. `test_upload_rejects_bad_magic_bytes` — stub bytes named `.pdf` → 400 **and nothing on disk** (validate-first)
3. `test_upload_requires_auth` → 401/403

Sample — the real-PDF body builder:
```python
def _make_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data
```

- [ ] **Step 5a-ii: Run the tests to verify they fail**

```bash
cd backend && uv run pytest app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py -v
```

Expected: FAIL. `test_search_*` fail with `AttributeError: 'BookRepo' object has no attribute 'search'`; stream/upload tests fail (no `/stream` route exists today; old code ignores `Range`; traversal goes unchecked; old upload response model has no `cover_url`). The point is red, not the shade of red. (Docker daemon required.)

- [ ] **Step 5a-iii: Rewrite `backend/app/repositories/book_repo.py`**

Full replacement. SQLAlchemy 2.0 throughout (Invariant 4). **This is the C1 fix — the measured SQL semantics are the point.** Read the old `search_books` and re-derive:
- `selectinload`, not `joinedload`: joinedload + LIMIT returned 1 book for limit=2
- `Book.tags.any(...)`, not `.join(Book.tags)`: the join fanned rows out and `count(*)` reported 3 for 2 books
- `@>` containment via `Book.metadata_.contains(criteria.metadata_)` for the JSONB filter
- explicit `ORDER BY (Book.created_at.desc(), Book.id.desc())`
- `total` counted over an ordering-stripped subquery: `select(func.count()).select_from(stmt.order_by(None).subquery())`

Sample — the search core:
```python
if criteria.tags:
    names = [t.strip().lower() for t in criteria.tags]
    stmt = stmt.where(Book.tags.any(Tag.name.in_(names)))
if criteria.metadata_:
    stmt = stmt.where(Book.metadata_.contains(criteria.metadata_))
```
Musts elsewhere: `get_book_by_uid -> Book | None` (`scalar_one_or_none`); `create_book`/`update_book` keep the `ValueError` contracts (duplicate uid / missing uid) but **drop the `try/except Exception` wrappers** — `IntegrityError` must reach the router intact (Invariant 2: the router maps it → 400); tag lookup by `Tag.name.ilike(...)`; `cleanup_orphan_tags` via `~Tag.books.any()`.

- [ ] **Step 5a-iv: Gate — mypy + repo-level search tests**

```bash
cd backend && uv run mypy app/repositories/book_repo.py --strict
cd backend && uv run pytest app/tests/test_book_search.py -v
```

Expected: mypy clean on this file (0 new). `test_book_search.py` fully PASS — **update the Task 0 test in place** to call the new API: `BookRepo(db).search(BookSearchCriteria(book_type="pdf"), limit=10, offset=0)` returning only `bk0001`. Do not keep a test for the deleted `search_books` method.

- [ ] **Step 5b-i: Rewrite `backend/app/services/book_service.py`**

Full replacement — 605 lines → thin orchestration (~130). No `HTTPException`, no `open()`, no PyMuPDF, no `print` (Invariants 1, 2). Validate-first, mutate-second. Constructor takes the five dependencies (repo, validator, storage, epub_reader, cover_generator). Methods map one-to-one to the Interfaces; the interesting one is `create_from_upload`, whose pipeline is:
1. `validator.validate(data, filename)` — reject before any byte reaches disk
2. title fallback: `metadata.title or Path(filename).stem` cleaned (replace `_`/`-` with space, title-case) — note `BookUpload.title` has `min_length=1`, so send `None` from the router for empty form fields
3. `book_uid = uuid.uuid4().hex[:8]`; `rel_path = storage.save(data, filename, book_uid)`
4. EPUB metadata prefill (best-effort): `epub_reader.read(storage.resolve(rel_path))`; merge author/language/tags without duplicating existing tag names
5. cover best-effort: `cover_generator.generate(resolve(rel_path), storage.cover_dir)`; `cover_name = f"{book_uid}.png" if cover_ok else None`
6. build `BookCreate(...)`, `repo.create_book(...)`; catch `ValueError` (duplicate uid) → `storage.delete(rel_path)` + raise `BookAlreadyExists` from it

Sample — the constructor contract:
```python
def __init__(self, book_repo: BookRepo, validator: ContentValidator,
             storage: BookFileStorage, epub_reader: EpubMetadataReader,
             cover_generator: CoverGenerator) -> None:
```
Musts: `get_book_by_uid`/`update_book`/`delete_book` raise `BookNotFound` on missing; `delete_book` removes the file and cover *then* the row; every failure path that already wrote to disk cleans up.

**Dropped, stated honestly:** (a) inline cover replacement on `PUT` — no image validator exists in the new module set, so the old cover-upload branch has no safe home; re-add with an image validator if wanted; (b) epub→pdf conversion and the `/read` endpoint — no converter module exists in the approved design; (c) the `BookUpload.book_type` form field is intentionally not honored on create — `book_type` is derived from `content_type`/extension, not client-supplied text.

- [ ] **Step 5b-ii: Gate — mypy + service grep**

```bash
cd backend && uv run mypy app/services/book_service.py --strict
cd backend && grep -n "HTTPException\|fitz\|open(" app/services/book_service.py
```

Expected: mypy clean on this file; grep prints **nothing** (the spec's `inspect.getsource` gate is replaced by this grep — `getsource` on the class misses module-level imports).

- [ ] **Step 5c-i: Rewrite `backend/app/api/book_router.py`**

Full replacement. `RoleChecker` on **every** endpoint including stream (`read_roles` = admin/teacher/student; `write_roles` = admin/teacher). `get_book_service` dependency wires the five modules. Error mapping table (Invariant 2): `InvalidBookFile`→400, `BookAlreadyExists`→409, `BookNotFound`→404, `IntegrityError`→400, `ValueError` (metadata build)→400. The `metadata` repeatable query param is parsed `key:value` → dict (400 on malformed). `MEDIA_TYPES = {"pdf": "application/pdf", "epub": "application/epub+zip"}`.

The stream endpoint's Range handling — the full grammar (write `_parse_range_header(range_header, size) -> tuple[int, int] | None`, raising an internal `_UnsatisfiableRange` for valid-but-unsatisfiable):

| Header | Result |
|---|---|
| absent / not `bytes=` / multi-range / malformed | `None` → 200 full body |
| `bytes=0-99` | 206, `Content-Range: bytes 0-99/{size}` |
| `bytes=500-` | 206 through `size-1` |
| `bytes=-500` | 206 last 500 bytes (C3; **suffix zero → 416**) |
| start > end, or start ≥ size | 416 + `Content-Range: bytes */{size}` (never clamp) |
| end beyond size | clamp end to `size-1` per RFC 7233 |

Sample — the two branches that gate everything:
```python
if not start_s:
    suffix = int(end_s)
    if suffix == 0:
        raise _UnsatisfiableRange
    return (max(size - suffix, 0), size - 1)
...
if start >= size or start > end:
    raise _UnsatisfiableRange
return (start, min(end, size - 1))
```
Hint: stream via a `StreamingResponse` over a chunked file iterator (`stream.seek(start)`, read `min(chunk_size, remaining)`); add `Accept-Ranges: bytes` and `Content-Disposition: inline` on every response; set `Content-Length` explicitly.

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

Expected: mypy clean on the three changed source files (0 new). Ruff clean after format. `B008` ignored — FastAPI's `Depends()` default-argument idiom trips it by design.

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
- Consumes: the Definition of Done command set from `AGENTS.md`; the Debt Coverage Annex ledger plus the hygiene plan's copy (auth/config/database rows) and the future audio/video/tag plan's rows; the S6 snapshot (36 ruff / 104 mypy errors repo-wide before this plan starts)
- Produces: a green, formatted, linted, type-scoped tree; refreshed graphify output; final commit

**Why (learning):** The refactor is only done when the repo's own Definition of Done has actually run and the output has been seen — a completion claim without command output is a guess. The `print(` sweep is the residual of the old plan's Task 16, folded in here: old `book_service.py` carried a dozen `print()` debug calls, and the sweep proves none survived the rewrite. mypy is scoped to changed files only — the Annex ledger tracks what belongs here versus other plans; pre-existing debt on other plans' files is logged in STATE.md, not fixed here.

- [ ] **Step 1: Format and lint**

```bash
cd backend && uv run ruff format .
cd backend && uv run ruff check . --fix --ignore B008
```

Expected: format reports files unchanged or reformats them — either is fine; `ruff check` ends with no remaining errors other than ledger rows owned by the hygiene plan or the future audio/video/tag plan. If `--fix` touches a file outside this plan's ledger, include it in the commit and note it.

- [ ] **Step 2: Type-check the changed files only**

```bash
cd backend && uv run mypy app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/services/book_errors.py app/services/content_validator.py app/services/book_file_storage.py app/services/epub_metadata_reader.py app/services/cover_generator.py app/schemas/book_schema.py --strict
```

Expected: 0 errors in these files. Do **not** run `mypy . --strict` as a gate — rows owned by the hygiene plan and the future audio/video/tag plan are out of scope (both are named owners in the Annex). If a changed file surfaces a pre-existing error in an untouched dependency, log it in STATE.md; do not fix the unrelated file.

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

Run `/audit` (invariant-auditor over the accumulated diff since Task 0) and `/verify` (full DoD). On PASS/PASS: confirm this plan's own files are clean (the Annex names which files still belong to other plans). Then invoke the `state` skill — record Tasks 0–6 complete in `STATE.md`, log the remaining errors on other plans' files (named in the Annex) under open items, and note the two dropped features (cover replacement on PUT; epub→pdf conversion + `/read`) so a future plan can resurrect them deliberately.

- [ ] **Step 7: Final commit**

```bash
cd backend && git add -A
git commit -m "chore: final gate — format, lint, scoped mypy, print sweep, graphify refresh"
```

---

## Learning Annex — cross-cutting concepts

Task-specific reasoning lives in each task's **Why (learning)** section. These are the themes that recur across this plan.

1. **Extensions lie; magic bytes don't.** A filename is user input masquerading as metadata. `.exe` renamed to `.pdf` sails past any extension-only check, and a stored file whose bytes are garbage 500s later at render time. ContentValidator sniffs the first bytes AND rejects before any byte reaches disk — validation is a gate, not a label.

2. **Containment is one gate, not a policy per call site.** The stream endpoint must never open a file except through `resolve()`. Centralizing the `..`-escape check in `BookFileStorage` makes the C4 fix unit-testable in isolation and makes it impossible for a future endpoint to forget the check — the same lesson as hygiene's `settings` anchoring: invariants belong in the layer that owns them.

3. **`-> bool` must be allowed to return `False`.** Cover generation is best-effort by contract: a stub or corrupt upload degrades to a missing cover, never a failed upload. The alternative — catch-and-raise — turns an expected degradation into a 500 that the fallback logic can never recover from. Exceptions are for exceptional cases.

4. **Red tests must name the defect.** Task 0's probe fails with `AttributeError: type object 'Book' has no attribute 'file_type'` — the exact failure mode it fixes. A test that fails for configuration reasons is worse than no test: it teaches you to ignore red. Every Step 2 here names the expected failure before the fix.

5. **Total functions own their fallback.** `EpubMetadataReader.read` returns `None` on any corrupt/missing input so the service layer — the one place with access to filename and user input — decides the fallback. A raising reader would force every caller to duplicate try/except; a `None`-returning one splits "did it parse" from "what do we do if not".

6. **One commit keeps history runnable.** `git pull && cat STATE.md` is the resume path across machines; a commit where `GET /books/search/` raises `AttributeError` at call time breaks it. Task 5 is fused on purpose: partway through rewriting `BookRepo`, the service and router that still call the old methods must be rewritten too — a split commit would leave a permanently broken checkout point for zero review benefit.

7. **Search semantics are measured, not assumed.** `joinedload` + LIMIT returned 1 book for `limit=2`; the tags join fanned rows out and `count(*)` reported 3 for 2 books; missing `ORDER BY` let Postgres repeat a row on one page and skip it on another. None of these were discoverable by reading code — each required a probe against postgres:16-alpine. The docstrings carry the measurements because the next refactor will re-derive the temptation.

8. **Tests protect behavior; migrations protect data — and neither is a stand-in for the other.** The harness keeps `create_all` while dev/prod move to Alembic (hygiene S5) precisely so a broken migration cannot masquerade as a behavior regression. This plan exploits the split in one direction: it touches no schema, so it ships without a migration, and the data in an existing `books` table survives the rewrite untouched.

## Deferred Work — preserved for a later pass

Cut from this plan to keep the scope on the book feature. Everything below was verified against the tree on 2026-08-20 and is **still open**. Nothing here is lost; it is a ready-to-execute backlog.

### D1: Audio / video / tag test suites + the delete-missing 500
- **Bug:** `audio_repo.py:17-22` `delete_audio` and `video_repo.py:18-23` `delete_video` dereference `None.deleted_at` when the id does not exist → 500. Fix: raise `ValueError(f"... {id} does not exist")`, map to 404 in `audio_router.py:122-126` and `video_router.py:111-114`.
- **Tests needed:** repo tests for soft-delete semantics (`deleted_at`) and API tests for upload / upload_multiple / list-excludes-deleted / patch / stream / delete-404.
- **Structure debt:** tag logic still lives inline in `tag_router.py` (Invariant 1) — a tag service + repo belong with these suites.
- **Note:** must run against Postgres via the testcontainers harness — JSONB/GIN are not expressible in SQLite.

### D2: Features dropped by design, for deliberate resurrection
- **Cover replacement on PUT** — no image validator exists in the Task 1–4 module set, so the old cover-upload branch had no safe home (Task 5b "Dropped, stated honestly" (a)). Re-add behind a PNG/JPEG magic-byte validator if wanted.
- **epub→pdf conversion + `GET /books/{uid}/read`** — no converter module exists in the approved design; Task 5c deletes `/read` and `/epub`. Resurrection requires a converter module and its security review, not the old inline code.

### D3: `TagRepo` SQLAlchemy 2.0 conversion
Task 5a rewrites `BookRepo` to 2.0 `select()` and retires the last `query()` call site in the book module. `TagRepo` remains legacy — a small follow-up on the same pattern, verifiable once D1's tag tests land, exactly as the auth tests made `a034adf` safe.

## Self-Review

- **Scope check:** the user asked for the book feature refactor. Part A (Tasks 0–4) is the defect hotfix plus the pure leaf modules; Part B (Tasks 5–6) is the fused rewrite and the Definition of Done gate. Audio/video/tag work and the dropped features are in the Deferred Work annex, preserved verbatim. The one crossover with hygiene is nothing this plan writes — Part A *consumes* S1's package markers, S3's anchored dirs, and the S2 single manifest.
- **Spec coverage:** C1 search fix → Task 5a ✓; C3 Range grammar → Task 5c + `test_book_stream.py` ✓; C4 traversal containment → Task 2 `resolve()` + Task 5c ✓; I1 `cover_url` on write schema → Task 0 ✓; I5 `ORDER BY` + disjoint pagination → Task 5a ✓; module decomposition (5 modules) → Tasks 1–4 + Task 5b ✓; `RoleChecker` → Task 5c ✓; error mapping router-only → Task 5c ✓.
- **Verified against the tree, 2026-08-20:** every defect, file, and line number in the Current State table was confirmed by grep/`wc -l` on this date; the stale claims in the previous revision and the 2026-07-03 ancestor are documented in the Corrections table (the ancestor was recovered via `git show 7ef380a^:docs/plans/2026-07-03-book-refactor-plan.md`).
- **Learner-edition review (2026-08-24):** full implementation blocks were removed per user request; contracts, Interfaces, expected outputs, red errors, run commands, commit messages, and the Learning Annex survive intact. The complete paste-ready revision lives in this file's git history before this edit and in the governing spec.
- **Type consistency:** `BookMetadata.tags` (not `subjects`) — Task 3 produces, Task 5b consumes ✓. `CoverGenerator.generate(source_path, dest_dir)` directory form — Task 4 produces, Task 5b calls `generate(resolve(rel_path), storage.cover_dir)` ✓. `BookFileStorage.cover_dir`/`delete_cover` — Task 2 produces, Task 5b consumes ✓. `Page[BookRead]` from `search` — Task 5a produces, Task 5c returns ✓. `BookService(...)` constructor with five dependencies — Task 5b defines, Task 5c `get_book_service` wires ✓.
- **Interface reconciliation note:** the three contributing batches were drafted independently and carried three cross-module mismatches (field name `subjects` vs `tags`; cover `dest_dir` directory vs file path; `cover_dir`/`delete_cover` referenced before they existed). All three are reconciled in this document: Task 2 exposes `cover_dir` + `delete_cover`, Task 3's field is `tags`, Task 4's `generate` takes a directory.
- **Known risks:** (1) Task 5's red-first tests run against the old tree and fail with legacy-shaped errors — that is intended TDD ordering, not a broken gate; (2) Part A asserts the modules stay out of `app/services/__init__.py` — an eager export there would import them before their tests exist; (3) `CoverGenerator._extract_epub_cover` opens the archive with stdlib `zipfile` — an EPUB with a malicious zip comment/bomb is bounded by `MAX_UPLOAD_SIZE` at the validator, but a follow-up could add zip member-size limits; (4) Task 5 relies on subtle SQL semantics (`selectinload`, `tags.any()`, `@>` containment) that were only verified against postgres:16-alpine — the repo docstrings carry the measurements so they survive.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-16-book-refactor.md`. Two execution options:

1. **Learner mode (current convention, 2026-08-24)** — the user implements each task themselves from the contracts, samples, and hints above; the agent reviews diffs, runs `/audit` + `/verify` before each commit, and never writes the implementation.
2. **Subagent-Driven** — dispatch a fresh subagent per task, review between tasks, fast iteration. Requires returning the full-code revision (git history) or writing from the spec.

Which approach?
