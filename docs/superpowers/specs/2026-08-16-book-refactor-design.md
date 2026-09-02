# Book Refactor — Design (revision of the 2026-07-03 effort)

**Status:** approved 2026-08-16. Supersedes `docs/specs/2026-07-03-book-refactor-design.md` and the remainder of `docs/plans/2026-07-03-book-refactor-plan.md`.

**Goal:** Finish the book feature refactor — streaming, epub + pdf CRUD, extensible search — on PostgreSQL, correcting four Critical defects found by review of the original plan and dropping the tasks that the tree has outgrown.

**Why a revision rather than an edit:** the 2026-07-03 plan is partially executed (Tasks 2–5 landed), six weeks stale in its facts, and overlaps an untracked newer plan. Five of its seventeen tasks are obsolete or superseded, and three of its verification gates are false-greens or false-reds. Renumbering in place would leave gaps and preserve stale teaching notes; a fresh document scoped to the surviving work is cheaper to execute and to review.

---

## Current State (verified against the tree, 2026-08-16)

| Area | State | Evidence |
|---|---|---|
| `Book` model — 2.0 `Mapped[]` + JSONB + GIN | ✅ done | commit `ff0adec`; columns verified, no `file_type` attribute |
| `BookTag` — 2.0, `is_active` dropped | ✅ done | commit `ff0adec` |
| Book tables rebuilt in Postgres | ✅ done | STATE.md:13 |
| Book schemas — layered, `BookSearchCriteria`, PEP 695 `Page[T]` | ✅ done | commit `ec4495a`; verified importable, renders `Page_BookRead_` in OpenAPI |
| `Tag` model 2.0 | ✅ done (bonus) | commits `c35a17c`, `b5fb6f4` |
| Test harness — testcontainers Postgres | ✅ committed | `backend/conftest.py`, `backend/app/tests/conftest.py` (`361bb48`) |
| Five service modules | ❌ absent | `backend/app/services/` holds only `auth_service.py`, `book_service.py` |
| `BookRepo` search | 🔴 broken | queries `Book.file_type`, which does not exist → `AttributeError` |
| `BookService` upload | 🔴 broken | `file_type=` passed to `BookCreate` at `:226` (silently dropped) and read from the model at `:326` (`AttributeError`); also threaded through the `search_books` signature at `:40,48` |
| `book_router` | 🔴 unguarded | no `RoleChecker`, no Range support, no pagination, no traversal containment |
| `BookService` size | 605 lines | measured; the old plan's "567" is stale |
| Repo-wide lint/type debt | 103 mypy errors / 24 files; 120 ruff errors | measured baseline, out of scope |

---

## Scope

### In scope

The still-valid book domain work from old Tasks 6–12, revised, plus a hotfix for the live `file_type` breakage.

### Out of scope, with reasons

Numbers in the left column are the **old** plan's; "new Task N" always refers to the sequence in this document.

| Old task | Disposition | Reason |
|---|---|---|
| 1 — read existing code | Drop | One-off orientation, already performed |
| 2, 3, 5 | Done | Committed and verified |
| 4 — `DROP TABLE` + `create_all` | Obsolete | Hygiene S5 removes `create_all` from `main.py`; the workflow would silently no-op |
| 13 — update `main.py` | Superseded | Hygiene S1 and S5 both edit `main.py`; the task's premise ("should need no changes") is false |
| 14 — create `conftest.py` | Superseded | The file exists (`361bb48`); executing this task overwrites the auth harness, and its own `DROP DATABASE` inside a transaction raises `ActiveSqlTransaction` |
| 15 — book tests | Handed to hygiene D1 | D1's repo/api split matches the `test_auth.py` convention. Harvest old Task 15's 27 case names first, including four auth-guard cases D1 omits |
| 16 — logging pass | Drop | New Tasks 2, 4 and 5 each already mandate `logging.getLogger(__name__)`; the old task's grep misses two of the five files it names. Its residual value — one repo-wide `print(` sweep — folds into new Task 6 |

### External prerequisites

Noted, not duplicated as tasks:

- **Hygiene S1** — creates `backend/app/tests/__init__.py`; changes `from app import settings` to `from app.config import settings`. If skipped, modules written here use an import path S1 later removes. Both forms are stated where relevant.
- **Hygiene S5** — Alembic adoption. No impact on this work (no schema changes here). Recorded so nobody reaches for old Task 4's `DROP TABLE` procedure.

Neither blocks Task 0 or Tasks 1–4.

---

## Architecture

Five focused modules replace the 605-line `BookService` god class. Each answers: what it does, how you use it, what it depends on.

| Module | Purpose | Interface | Depends on |
|---|---|---|---|
| `services/book_errors.py` | Domain exception hierarchy | `BookError` base; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed` | nothing |
| `services/content_validator.py` | Is this upload an acceptable book? | `validate(file_bytes, filename) -> str` returns the extension; raises `InvalidBookFile` | `book_errors` |
| `services/book_file_storage.py` | Bytes ↔ disk, path safety | `save(bytes, filename, uid) -> str`; `delete(rel_path) -> None`; `resolve(rel_path) -> Path` | `config.settings`, `book_errors` |
| `services/epub_metadata_reader.py` | Title/author/language from EPUB | `read(path) -> BookMetadata \| None` | PyMuPDF |
| `services/cover_generator.py` | First-page thumbnail | `generate(src, dest) -> bool`; returns `False` on failure, never raises | PyMuPDF, `logging` |

`BookService` afterwards is orchestration only — no `HTTPException`, no `open()`, no PyMuPDF. It composes the four modules plus `BookRepo` and raises `book_errors` types. `book_router` is the sole translator to HTTP, satisfying Invariant 2.

### Two boundary changes from the original design

**`BookFileStorage.resolve()` is new and load-bearing.** A DB-supplied `file_path` joined to `UPLOAD_DIR` escapes the directory via `..` — verified resolving to `/Users/tu4n/Documents/etc/passwd`. Today the tree is safe only because `safe_filename` incidentally strips traversal on the write path. Centralising containment in `resolve()` means the router cannot open a book file without passing the check, and the guard is unit-testable in isolation instead of duplicated per call site.

**`CoverGenerator.generate` returns `bool` and never raises.** Matches the AGENTS.md rule that a function typed `-> bool` must be able to return `False`, and lets an unparseable PDF degrade to a missing cover rather than failing the upload.

---

## Data Flow

### Search

`GET /books/` → router builds `BookSearchCriteria` → `BookService.search(criteria)` → `BookRepo.search(criteria) -> Page[BookRead]` → response.

```python
stmt = select(Book).options(selectinload(Book.tags))
if criteria.tags:
    names = [t.lower() for t in criteria.tags]
    stmt = stmt.where(Book.tags.any(Tag.name.in_(names)))
if criteria.metadata_:
    stmt = stmt.where(Book.metadata_.contains(criteria.metadata_))
total = session.execute(
    select(func.count()).select_from(stmt.order_by(None).subquery())
).scalar_one()
stmt = stmt.order_by(Book.created_at.desc(), Book.id.desc()).limit(limit).offset(offset)
items = session.execute(stmt).scalars().all()
```

Three corrections over the original, each measured against live `postgres:16-alpine`:

- `selectinload`, not `joinedload` — a second query, immune to `LIMIT` fanout. The original returned **1 book for `limit=2`**.
- `Book.tags.any(...)`, not `.join(Book.tags)` — no row multiplication, so `count(*)` is honest. The original reported **`total=3` when 2 books matched**.
- explicit `ORDER BY` — Postgres guarantees no ordering without it, so `LIMIT/OFFSET` can repeat a row on one page and skip another.

The original plan's teaching note that `.unique()` solves this is wrong and is removed: `.unique()` deduplicates Python-side rows, it does not fix `LIMIT`.

**Semantics, previously unspecified:**

- **Tags: OR.** `?tags=math&tags=algebra` returns books tagged either. Names are lowercased before comparison.
- **Metadata: containment (`@>`).** `metadata_={"publisher": "Penguin"}` becomes `Book.metadata_.contains(...)`, served by the existing GIN index. Exposed as a repeatable `?metadata=key:value` param parsed into a dict by the router — making the design's extensibility claim true through HTTP, which it was not before.

**`cover_url` moves off `BookBase`.** It is currently a `@computed_field` on `BookBase`, inherited by `BookCreate`, so `Book(**model_dump())` raises `TypeError: 'cover_url' is an invalid keyword argument`. It is **moved to `BookRead` only** — it is response shaping and has no business on a write schema. This edits a completed task (old Task 5, commit `ec4495a`) and is folded into Task 0. It permanently removes the footgun rather than guarding against it with `exclude={"tags", "cover_url"}` at every write call site. Once moved, write paths need only `exclude={"tags"}`.

### Upload

router → `BookService.create_from_upload` → `ContentValidator.validate` → `BookFileStorage.save` → `EpubMetadataReader.read` (epub only) → `CoverGenerator.generate` (best-effort) → `BookRepo.create`.

Validate-then-mutate: every guard runs before any byte reaches disk, so a rejected upload leaves nothing behind.

An empty form field submits `""`, not `None`, and `BookUpload.title` carries `min_length=1` — so `""` raises `ValidationError` before the filename-fallback validator runs. The router must send `None` for the fallback path.

### Streaming — RFC 7233

| Request | Response |
|---|---|
| `bytes=0-99` | 206, `Content-Range: bytes 0-99/1000` |
| `bytes=500-` | 206, through `size-1` |
| `bytes=-500` | 206, last 500 bytes |
| `start > end`, or `start >= size` | 416, `Content-Range: bytes */1000` |
| malformed, or multi-range (`bytes=0-99,200-299`) | 200, full body |

`Accept-Ranges: bytes` on all responses. Byte ranges are inclusive.

The original spec — "parse `bytes=start-end`, clamp to file bounds" — 500s on `bytes=-500`, a legal suffix range that Safari and pdf.js both emit. "Clamp the start" is also wrong and is removed: an out-of-range start is unsatisfiable, not clampable.

### Error mapping

Router only: `BookNotFound` → 404, `InvalidBookFile` → 400, `BookAlreadyExists` → 409, `IntegrityError` → 400.

### Authorization

`RoleChecker([...])` on every endpoint including stream and download — verified present at `dependencies/auth.py:44-51`. It raises 403 itself on a wrong role; the 401 for an absent or invalid token comes from `get_current_user`, which it depends on. Book access is role-gated, not owner-gated: this is a shared library, so any authenticated reader may fetch any book. Intentional, stated here because the original spec had no security section at all.

---

## Task Sequence

Bottom-up, leaf-first. Tasks 1–4 are pure additions — nothing imports them yet, so the tree stays green after every commit.

| Task | Content | Commits |
|---|---|---|
| 0 | `file_type` hotfix: `book_repo.py:107,122-123`, `book_service.py:40,48,226,326`; move `cover_url` from `BookBase` to `BookRead` | 1 |
| 1 | `book_errors.py` + `ContentValidator` | 1 |
| 2 | `BookFileStorage` (incl. `resolve()` containment) | 1 |
| 3 | `EpubMetadataReader` | 1 |
| 4 | `CoverGenerator` | 1 |
| 5 | **Fused:** `BookRepo` + `BookService` + `book_router` | 1 |
| 6 | Final gate: format, lint, types, `print(` sweep, full suite, graph refresh | 1 |

**Why Task 5 is fused.** Rewriting `BookRepo` deletes `search_books` and `get_all_books`, which `book_service.py:33,47` and `book_router.py:81` still call. Splitting the three files across commits leaves several commits where `GET /books/search/` raises `AttributeError` — and the original plan's import-only gate passes anyway, because the breakage is at call time. One commit keeps every point in history importable and runnable, which matters because `git pull && cat STATE.md` is the cross-machine resume path. Task 5 is structured as three clearly separated steps to stay reviewable.

**Task 0 first** so the tree is green before refactoring begins, rather than carrying the live `file_type` breakage through six more commits. Task 5 would eventually fix it as a side effect of rewriting both files, but that leaves shipped 500-error paths live for the duration.

---

## Verification

Every task ends with `uv run ruff format`, `uv run ruff check <files> --ignore B008`, `uv run mypy <files> --strict`, and at least one probe that observes real behavior.

Scoped to changed files against the measured baseline (103 mypy errors / 24 files, 120 ruff errors). The original Task 17's `mypy . --strict` presented that debt as a gate to pass, making the task unbounded.

### Replaced gates

| Original gate | Defect | Replacement |
|---|---|---|
| `python -c "from app.repositories.book_repo import BookRepo"` | Passes while `GET /books/search/` raises `AttributeError` — import succeeds, call fails | `mypy --strict` on changed files + behavioral probe |
| `assert 'HTTPException' not in inspect.getsource(BookService)` | `getsource` on a class returns the body only, not imports; passes a module-level import | `grep -n "HTTPException" app/services/book_service.py`, expect no output |
| `GET /books` → expect 401 | Returns **307**; curl does not follow redirects, so it reads as broken auth | `GET /books/` with trailing slash |

### Red-first probes

Each fails against the original plan's code and pins one Critical fix:

1. **Search correctness.** Two books, tagged `[math, algebra]` and `[math]`; query both tags. Assert `total == 2` and `limit=2` yields 2 distinct uids. Original: `total=3`, 1 item.
2. **Suffix range.** `Range: bytes=-500` → assert 206 and `len(body) == 500`. Original: `ValueError`.
3. **Traversal containment.** `file_path = "../../../../etc/passwd"` → assert 404. Original: resolves outside `UPLOAD_DIR`.

Probe 1 goes red against an unimplemented `search()`. That is intended TDD ordering, not a broken gate.

### Test placement

The three probes are book-domain correctness and ship with this work. Broader coverage belongs to hygiene D1 (`test_book_repo.py` + `test_book_api.py`), seeded with the 27 harvested case names. Two D1 corrections carry over:

- Generate real PDFs for happy-path tests (`fitz.open(); doc.new_page(); doc.tobytes()`); reserve stub bytes for the magic-byte rejection test. A stub trailer passes magic-byte validation but is unparseable, so cover generation yields `None` and any `cover_url` assertion fails for an unrelated reason.
- Pagination tests assert disjoint, complete uid sets across pages, not just item counts — counts alone pass against a missing `ORDER BY`.

### Harness notes

Uses the committed testcontainers fixtures (`db`, `client`, `setup_paths`, and helpers `setup_admin`/`login`/`auth_headers`). Docker daemon required; no `docker compose up -d db`.

Two documented traps:

- Call `db.expire_all()` before reading via `db` after a write through `client` — the long-lived session's identity map otherwise returns stale objects (measured).
- Never add `backend/app/tests/__init__.py` by hand. It makes `app.tests.conftest` a package import, which triggers `app/__init__.py`'s eager `from .database import ...` at collection time and builds the engine from the default `DATABASE_URL` before the container starts. Hygiene S1 handles this deliberately.

---

## Corrections to Carry Into the Old Documents

The 2026-07-03 plan gets a header marking it superseded, and these are recorded so its stale teaching notes are not trusted:

- **GIN index instruction is wrong.** The plan says twice to reference the Python attribute `metadata_` in `Index()`. That raises `ConstraintColumnNotFoundError` — `Index()` takes DB column names. The committed model correctly uses `"metadata"`, meaning the implementer already worked around wrong instructions.
- **`joinedload` + `LIMIT`** on a collection is the defect in Critical 1, not a best practice.
- **`asyncio.get_event_loop()`** is soft-deprecated on Python 3.13. Use `await asyncio.to_thread(fn, *args)`.
- **Stale facts:** `BookService` is 605 lines, not 567; the `CoverGenerator` source range is 397–589, and the plan's "397-548" truncates mid-block, dropping the filename-heuristic and first-image fallbacks its own step list requires; column widths are `String(100)`, not `String(50)`/`String(10)`; `title` is not indexed.
- **Task count:** STATE.md says 16 tasks; the file has 17 headings. Renumbering after the themes removal never happened, so "12 of 16 remaining" is arithmetically wrong.
- **`file_type` drop mechanism:** `BookCreate` has no explicit `extra="ignore"`; the drop is Pydantic v2's default behavior. Same outcome, different cause than the hygiene plan states.

---

## Risks

1. **Task 5 is the largest unit** — three files in one commit. Mitigated by three separated steps and a gate after each file, with a single commit at the end.
2. **`cover_url` move touches a completed task** — editing old Task 5's output (commit `ec4495a`) means the schema diff must keep every existing read response identical. Verified by the `Page_BookRead_` OpenAPI snapshot plus a `BookRead.model_dump()` field-set assertion.
3. **Hygiene S1 ordering** — if S1 lands after this work, the settings import path changes under these modules. Both forms are stated; the diff is mechanical.
4. **Range implementation is subtle** — the 416 path and suffix ranges are easy to get wrong. Probe 2 covers the suffix case; the plan will enumerate the full table as assertions.
