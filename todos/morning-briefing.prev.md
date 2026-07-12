Morning briefing written to `todos/morning-briefing.md`.

**TL;DR:** Task 5 still completely overdue — zero progress since July 9. The lingering uncommitted `TYPE_CHECKING` guard changes in `book.py`/`book_tag.py` should be committed first thing, then tackle the schema rewrite.
but the session apparently spent no time on the refactor.

- ❌ Read current `book_schema.py`, plan layered schemas
- ❌ Write `BookBase`, `BookRead`, `BookCreate`, `BookUpdate`, `BookUpload`, `BookSearchCriteria`, `Page[T]`
- ❌ Update `schemas/__init__.py` exports
- ❌ Verify with REPL snippet
- ❌ `ruff format . && ruff check . --fix`
- ❌ Commit

Additionally, uncommitted `TYPE_CHECKING` guard changes in `book.py` / `book_tag.py` are lingering from before the July 9 commits — commit or discard before starting new work.

## Done So Far

- [x] **Task 1:** Read and understand existing code
- [x] **Task 2:** Rewrite `Book` model — SQLAlchemy 2.0 + JSONB + GIN index
- [x] **Task 3:** Clean up `BookTag` — 2.0 style, dropped `is_active`
- [x] **Task 4:** Drop and rebuild book tables in Postgres
- [x] **Bonus:** Tag model 2.0 style, `TYPE_CHECKING` guard (partial — in working tree), removed themes, Postgres-only

## Next Up

**Task 5: Rewrite book schemas (layered + `BookSearchCriteria` + `Page`)** — `docs/plans/2026-07-03-book-refactor-plan.md:230`

## Today's Plan (30 min)

- [ ] Commit the uncommitted TYPE_CHECKING guard changes (`backend/app/models/book.py`, `backend/app/models/book_tag.py`): `git add backend/app/models/ && git commit -m "refactor: add TYPE_CHECKING guard to Book model imports"`
- [ ] Read `backend/app/schemas/book_schema.py` current state; cross-reference plan hints for `Base → Create → Read → Update` layering, `BookSearchCriteria`, `Page[T]`, `cover_url` as `computed_field`
- [ ] Write `BookBase`, `BookRead`, `BookCreate`, `BookUpdate`, `BookUpload`, `BookSearchCriteria`, `Page[T]` in `book_schema.py`; remove `BookDetail`
- [ ] Update `backend/app/schemas/__init__.py` exports
- [ ] **Verify:** `python -c "from app.schemas import BookBase, BookRead, BookCreate, BookUpdate, BookUpload, BookSearchCriteria, Page; c = BookSearchCriteria(q='alice', tags=['math'], metadata_={'publisher': 'Penguin'}); print(c.model_dump()); p = Page[BookRead](items=[], total=0, limit=20, offset=0); print(p.model_dump()); print('OK')"` then `ruff format . && ruff check . --fix` then `git commit -m "refactor: rewrite book schemas with layering, search criteria, and pagination"`

## Reminders

- Set up Alembic migrations — low priority
- Add StorageService/StorageRepo abstraction for file I/O — low priority
- Normalize repo naming: `Video_Repo` → `VideoRepo` — low priority
- Configure git credential helper to avoid push hanging on other machine — medium priority

## Blockers / Warnings

- **Uncommitted `book.py` / `book_tag.py` changes** — TYPE_CHECKING guard is in working tree but not in HEAD. These should have been part of `b5fb6f4` but the commit only fixed Tag's side, not Book's. Commit first thing to avoid confusion.
- `graphify-out/` files modified (auto-regenerated) — safe to ignore.
- Docker Postgres must be running for schema verification — `docker compose up -d db` if not already up.
