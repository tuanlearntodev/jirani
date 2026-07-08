# Morning Briefing — Wednesday, July 08 2026

## Urgent (Overdue from last session)
Yesterday's plan was to fix Task 2 (`backend/app/models/book.py`). **Nothing happened** — no new commits since `8eaf4fe`, and `book.py` is byte-for-byte the same broken partial (confirmed by reading it). All four planned steps are still open:

- [ ] **1. Imports + class header** — NOT done. Still imports `Column, Integer, String` (1.x leftovers); no `TimestampMixin` base, no `JSONB`, no `Index`/`text`, no `uuid`.
- [ ] **2. Columns per spec** — NOT done. Still has `file_type` (must drop); `author`/`level`/`book_type` still `nullable=False` (must be `Mapped[str | None]`); no `language`; no `metadata_` JSONB; no `created_at`/`updated_at`.
- [ ] **3. `themes` relationship + GIN index** — NOT done. No `themes` relationship, no `__table_args__` GIN index.
- [ ] **4. Lint + typecheck + commit** — NOT done. No commit exists for Task 2.

Also still overdue from STATE.md Next Steps:
- [ ] Commit `scripts/` + `STATE.md` (untracked) — Next Steps #4.
- [ ] Push `refactor` branch to origin — blocked on git credential helper.

## Done So Far
- Auth refactor complete: Tasks 13–19 (`/setup` endpoint, AuthRepo, RoleChecker, bulk user creation, auth router redesign) — commits `47909fe`…`ffb44e8`.
- Opencode tooling configured: 5 MCPs (context7, gh_grep, memory, playwright, sequential-thinking), `state` skill, morning-briefing automation — commit `8eaf4fe`.
- Zero-config deployment (auto-generated `SECRET_KEY`, no `.env`) — commits `0057e1a`, `497ebb7`.
- Book refactor Task 1 (read existing code) — understood; Task 2 attempted but left broken and uncommitted.

## Next Up
**Task 2 — Rewrite `Book` model (SQLAlchemy 2.0 + JSONB)** (`docs/plans/2026-07-03-book-refactor-plan.md:89`). First incomplete task; `book.py` must be fixed to spec before Tasks 3–17 can build on it. 15 of 17 tasks remain after this.

## Today's Plan (30 min)
Rewrite `backend/app/models/book.py` to match the Task 2 spec, then lint + commit.

- [ ] **1. Imports + class header (~10 min)** — Replace 1.x imports with `Mapped`/`mapped_column`; add `TimestampMixin` from `app.models.base` (first base), `JSONB` from `sqlalchemy.dialects.postgresql`, `Index`/`text` from `sqlalchemy`, stdlib `uuid`. `class Book(TimestampMixin, Base):`.
  Verify: `cd backend && python3 -c "import app.models.book; print('OK')"`
- [ ] **2. Columns per spec (~10 min)** — Drop `file_type`. Keep `id`, `uid` (String(36) full UUID4, unique+indexed, nullable=False), `title` (String(255), nullable=False, indexed). Add `author`/`level`/`book_type`/`language` as `Mapped[str | None]` (index level/book_type/language, NOT author). Keep `cover_path`, `file_path`, `extension`. Add `metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))`.
  Verify: `cd backend && python3 -c "from app.models.book import Book; print(sorted(Book.__table__.columns.keys()))"` → must include `metadata`, `language`, `created_at`, `updated_at`; must NOT include `file_type`.
- [ ] **3. `themes` relationship + GIN index (~5 min)** — Add `themes = relationship("Theme", secondary="book_themes", back_populates="books")` (string ref — `Theme` model lands in Task 3). Add `__table_args__ = (Index("ix_books_metadata_gin", "metadata_", postgresql_using="gin"),)`.
  Verify: `cd backend && python3 -c "from app.models.book import Book; print(Book.__table_args__); print('themes' in [r.key for r in Book.__mapper__.relationships])"` → tuple with GIN index; `True`.
- [ ] **4. Lint + typecheck + commit (~5 min)** — `ruff format . && ruff check . --fix && mypy . --strict`, then `git add backend/app/models/book.py && git commit -m "refactor: rewrite Book model in SQLAlchemy 2.0 with JSONB metadata and themes relationship"`.
  Verify: `git log --oneline -1` shows the new commit; `git status --short backend/app/models/book.py` is clean.

## Reminders
- [ ] Set up Alembic migrations (replaces manual DROP TABLE workflow) — priority: low, added: 2026-07-08
- [ ] Add StorageService/StorageRepo abstraction for file I/O — priority: low, added: 2026-07-08
- [ ] Normalize repo naming: `Video_Repo` → `VideoRepo` — priority: low, added: 2026-07-08
- [ ] Configure git credential helper to avoid push hanging on other machine — priority: medium, added: 2026-07-08

## Blockers / Warnings
- **Task 2 has now been skipped two briefings running.** `book.py` is an uncommitted broken partial — every Task 2 step is still open. This is the critical path; Tasks 3–17 are blocked on it. Make today the day it lands.
- **`python` not on PATH; only `python3` (3.14.4).** The plan's verify snippets use `python` — use `python3` instead, or add a shim/alias so the plan commands work as written.
- **`backend/app/models/tag.py` modified but uncommitted** — Task 2 should NOT touch `tag.py`. Review the diff before committing so a stray change doesn't ride along.
- **`scripts/` and `todos/` untracked** — morning-briefing tooling + `STATE.md` not yet committed (Next Steps #4). Worth committing today so the automation is version-controlled.
- **`refactor` branch unpushed** — no remote backup; another machine can't `git pull` the book/auth work. Blocked on git credential helper (see Reminders).
- **`graphify` CLI not on PATH** — `graphify query`/`graphify update` fail (`command not found`); `graphify-out/` files are dirty from auto-regen but the tool isn't wired up. Don't rely on graphify until it's installed.
- **`docs/plans/...` and `docs/specs/...` modified but uncommitted** — plan/spec edits not yet saved; review and commit with the next book work.
