# Media Refactor + nginx Streaming + Criteria Entities — Implementation Plan (2026-09-01, learner edition, rev 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Learner mode (user-approved convention since 2026-08-24):** this plan carries the *contract* (signatures, case lists, expected red errors, gates) and *samples* of novel idioms — you write the implementation bodies yourself. Four load-bearing blocks are given in full because getting them wrong destroys data or breaks the deployment: the Alembic migration (Task 5), the X-Accel stream endpoint shape (Tasks 5/8), `nginx.conf` + `docker-compose.yml` (Task 9), and the entity repo lookup semantics (Task 3). TDD is binding (AGENTS.md): a step that says "write the failing test" must be red before you touch the implementation. Characterization pins (Part A) are the one deliberate exception — they assert *current* behavior and are witnessed green first.

> **Rev 2 (2026-09-01): rewritten to match the spec's same-day revision — audio module removed from scope** (user decision 2026-09-01). Audio stays legacy — untested, Python-streamed, zero-auth — until its own future plan. Nothing in this plan touches `audio_router.py`, `audio_repo.py`, `models/audio.py`, `models/audio_tag.py`, or `schemas/audio_schema.py`. Rev 1's audio pin/module tasks are gone; the standalone model-conversion task is gone (video's 2.0 conversion folds into its fused rewrite, per spec §5); the entity migration chains straight off baseline `70ee18aafdca` (no `audio.author_id` intermediate revision). Task numbering keeps the spec's own cross-reference ("the plan's Task 10 annex", spec §3) true.
>
> **Rev 3 (2026-09-01, same session): the former non-audio deferrals are scheduled as Part G (Tasks 11–16)** — user decisions: "fold them as follow-on tasks" and "tighten student read-only now." Part G runs after Task 10's contract freeze; every task is additive against the frozen React surface, red-first, with its own commit and same 0/0 gates.

**Goal:** Refactor books and video to the invariant shape in one pass — replacing all hand-rolled Python byte streaming with nginx X-Accel-Redirect, promoting `author`/`level`/`genre` to tag-like single-valued entities on books via one data-preserving Alembic migration, and renaming `book_type` → `genre` to kill the file-format conflation. Audio is explicitly out of scope.

**Architecture:** One plan replaces two (`2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md` — deleted in Task 10). Part A pins the video/tag legacy behavior; the rest rebuilds on top: entity modules (Author/Level/Genre) copied from the tag shape, book leaf modules + fused rewrite, tag/media rewrites, then the nginx service. Every in-scope stream endpoint becomes an auth + containment check that emits `X-Accel-Redirect` — the router never opens a file (Invariant 3). Schema changes run through Alembic with full data backfill. **Part G (Tasks 11–16) then clears the non-audio deferrals** — `vids`→`videos` rename, orphan cleanup, video posters, student read-only split, cover replacement on PUT, epub→pdf + `/read` — each a red-first follow-on underneath the frozen React contract (spec §9).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests, docker-compose for dev/prod), Alembic, nginx, uv, pytest/httpx, ruff, mypy.

**Governing spec:** `docs/superpowers/specs/2026-09-01-media-refactor-nginx-entities-design.md` (approved 2026-09-01, revised same day — audio out of scope). Read it first; where this plan and the spec disagree, the spec wins. The TDD process spec `2026-08-24-tdd-workflow-design.md` still governs execution order (pins green-first, fixes red-first).

## Global Constraints

Every task implicitly includes all of the following. Exact values copied from the spec(s).

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; no `docker compose up -d db` needed for tests. The harness (`backend/app/tests/conftest.py`) exposes `db`, `client`, `setup_paths`, and importable helpers `setup_admin`/`login`/`auth_headers`. `app.tests` is a package — never re-create its `__init__.py`
- One harness trap survives: **call `db.expire_all()` before reading via `db` after a write through `client`** — the long-lived session's identity map otherwise returns stale objects
- `ruff check` with `--ignore B008` on changed files; `mypy --strict` on changed files only, per the Debt Coverage Annex — touched files end at **0 ruff + 0 mypy**, and pre-existing errors in a touched file are that task's debt to clear. Log other plans' failures in STATE.md; do not fix unrelated files
- Characterization-first (TDD spec decision 2): Part A pins are **witnessed green on legacy code first**; every behavior *fix* gets a red-first probe that fails on legacy before implementation. Never delete a failing test to make the suite pass
- Commit after every task, **including the plan file tick in the same commit** (AGENTS.md); message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- **Locked decisions (user-approved 2026-09-01):** single-valued FK for author/level/genre (not M2M); all three on books only (audio out of scope — no `audio.author_id`); language stays a column; existing DB data must survive the migration (backfill); nginx fronts everything (only published port), backend unpublished; learner-edition format; delete the two old plans + `2026-08-16-book-refactor-design.md`
- **Audio out of scope (user decision 2026-09-01):** no audio pins, no audio tests, no audio fixes, no audio model/repo/schema/rewrite work. Audio's `/audio/` endpoints remain zero-auth — flag loudly in any deployment that matters until the future audio plan lands. Its known violations stay in `AGENTS.md`'s violating-today column
- **Test layout (user decision 2026-09-01):** auth tests live under `app/tests/auth/` (`test_auth_repo.py` + `test_auth_api.py`, split from the old monolithic `test_auth.py`); every test file this plan creates lives under `app/tests/media/`. Both subdirs are packages with `__init__.py`. The shared conftest stays at `app/tests/conftest.py` — import it as `from app.tests.conftest import ...`, unchanged
- **`uploads/vids` name stays** — the dir rename is deferred (spec §7), not this plan
- After the final task, run `graphify update .` (AST-only)
- Work tree note: the auth-test split (`D backend/app/tests/test_auth.py`, new `backend/app/tests/auth/`) plus doc edits to `AGENTS.md`/`STATE.md`/`.opencode/commands/done.md` are in-flight and uncommitted at plan start — they are the user's working state, not this plan's concern; leave them alone

## Corrections to the previous plans

The two replaced plans were audited against this spec (rev 2). Statements that are no longer true:

| # | Previous claim | Replacement ruling |
|---|---|---|
| 1 | Book plan Task 0: rename the `file_type` search param to `book_type` and map it to `Book.book_type` | **Moot.** The column is dropped, not renamed — `genre_id` replaces it. The Task 0 hotfix and its test die with the column; Task 5's search probes are the new equivalents |
| 2 | Book plan Task 5c + media plan Task 7: implement RFC 7233 Range in Python (8-row grammar table each) | **Deleted.** nginx implements Range natively. All Python Range parsers and their test tables are out; the stream contract becomes "204 + `X-Accel-Redirect` + `Content-Type` + `Accept-Ranges: bytes`" |
| 3 | Media plan Global Constraint: "No schema changes in this plan. Models convert with identical columns — zero Alembic delta" | **Superseded.** This plan *does* change schema: three new tables, `books` FK conversion + `book_type` drop. One hand-written migration (Task 5) carries it all — chained straight off baseline `70ee18aafdca` |
| 4 | Media plan pinned `book_type` as derived-from-MIME ("Task 5b: not honored on create — derived from content_type/extension") | **Wrong per user 2026-09-01:** `book_type` is the *genre* (novel, sci-fi), not the file format. The format is `extension`. Genre is user-supplied, not derived |
| 5 | Media plan video stream pins assert byte-for-byte bodies through `StreamingResponse` | **Flipped in Task 8:** pins change to 204 + redirect headers; byte assertions leave the suite (nginx's job — one compose integration check in Task 9 covers the bytes). Audio's stream stays the legacy generator (deferred) |
| 6 | Media plan Global Constraint: "uncommitted auth changes in flight" | **Stale.** Auth work landed; what remains uncommitted at plan start is the auth-test split + doc edits — not plan work |
| 7 | Media plan tasks 1–12 treat audio as in-scope (pins, 2.0 conversion, `audio.author_id`, fused rewrite, X-Accel) | **Reversed by the spec's same-day revision.** Audio is out of scope. Rev 1's audio task content lives in git history (`2026-08-26-audio-video-tag-refactor.md` at its pre-revision commit) and belongs to the future audio plan |
| 8 | Book plan Task 5c deleted `/books/{uid}/epub` and `/read` (epub→pdf conversion) | **Still true** — carried into this plan (book router rewrites the same way) and preserved in the Deferred annex |

## Current State (verified against the tree, 2026-09-01)

| Area | State | Where |
|---|---|---|
| Audio module | ⛔ **OUT OF SCOPE** — legacy 1.x, zero auth, inline DB + tag logic, CWD-relative literal, Python-streamed. Untouched by this plan; violations remain in AGENTS.md's violating-today column | `backend/app/api/audio_router.py` (178 lines), `audio_repo.py`, `models/audio.py` |
| Video endpoints | 🔴 6 endpoints, **zero auth**, inline DB + tag logic, **no extension validation** | `backend/app/api/video_router.py` (157 lines) |
| Tag endpoint | 🔴 `GET /tags/` only, zero auth, repo passthrough | `backend/app/api/tag_router.py:11-13` |
| Book module | 🔴 605-line `BookService` god class; `search_books` filters on nonexistent `Book.file_type` → 500; router has zero auth, no Range, no containment | `book_service.py`, `book_repo.py:122-123`, `book_router.py:47-189` |
| Streaming (in scope) | 🔴 Hand-rolled generators in the two in-scope routers: 3 book endpoints + 1 video endpoint | `book_router.py`, `video_router.py` |
| Delete-missing 500s (in scope) | 🔴 LIVE — `None.deleted_at` deref (video's; audio's stays, OOS) | `video_repo.py:22-27` |
| Models | 🔴 `Video`/`VideoTag` legacy 1.x `Column()`; Book already 2.0 with `book_type` column (MIME-junk values); Tag already 2.0. Audio models legacy (OOS) | `models/video.py`, `video_tag.py`, `book.py:42`, `tag.py` |
| Repos | 🔴 legacy `query()` ×2 in scope; dead code: `TagRepo.get_tag_by_id/create_tag`, `Video_Delete` | `video_repo.py`, `tag_repo.py`, `video_schema.py:21-23` |
| Naming (Inv 6) | 🔴 `Video_Repo`, `Video_Create`, `Video_View` (audio's stay legacy) | video module + schemas |
| Tests (Inv 5) | 🔴 zero for book/video/tag — suite has only the auth tests (split under `app/tests/auth/`, in flight) | `backend/app/tests/` |
| Whitelist constants | 🔴 `ALLOWED_VIDEO_EXTENSIONS` does not exist yet (added by Task 7's validator) | — |
| Anchored dirs | ✅ `UPLOAD_DIR`/`COVER_DIR`/`AUDIO_DIR`/`VIDEO_DIR` BASE_DIR-anchored; mkdir at import | `config.py:40-43`, `main.py` |
| Alembic | ✅ baseline `70ee18aafdca` applied; dev DB stamped; compose entrypoint runs `upgrade head` | `backend/migrations/` |
| Harness | ✅ testcontainers postgres:16-alpine, session-scoped, `create_all` per test | `backend/conftest.py` |

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/tests/media/test_video_repo.py`, `test_video_api.py` | Create | 1 | Video characterization pins |
| `backend/app/tests/media/test_tag_repo.py`, `test_tag_api.py` | Create | 2 | Tag characterization pins |
| `backend/app/models/author.py`, `level.py`, `genre.py` | Create | 3 | Three entity models, mirror of `Tag` |
| `backend/app/schemas/author_schema.py`, `level_schema.py`, `genre_schema.py` | Create | 3 | `EntityCreate`/`EntityRead` |
| `backend/app/repositories/author_repo.py`, `level_repo.py`, `genre_repo.py` | Create | 3 | `get_or_create_by_name`, `get_by_name`, `list_all` |
| `backend/app/services/author_service.py`, `level_service.py`, `genre_service.py` | Create | 3 | Thin `list()` seam |
| `backend/app/api/author_router.py`, `level_router.py`, `genre_router.py` | Create | 3 | `GET /authors/`, `/levels/`, `/genres/` |
| `backend/app/tests/media/test_entity_repos.py`, `test_entity_api.py` | Create | 3 | Entity unit + API tests |
| `backend/app/services/book_errors.py`, `content_validator.py` | Create | 4 | Book domain errors + upload gate |
| `backend/app/services/book_file_storage.py` | Create | 4 | bytes↔disk + `resolve()` containment |
| `backend/app/services/epub_metadata_reader.py` | Create | 4 | EPUB metadata leaf |
| `backend/app/services/cover_generator.py` | Create | 4 | Cover leaf, `-> bool`, never raises |
| `backend/app/tests/media/test_book_validator.py`, `test_book_storage.py`, `test_book_epub_reader.py`, `test_book_cover.py` | Create | 4 | Leaf unit tests |
| `backend/app/models/book.py` | Modify | 5 | Drop `book_type`; add `author_id`/`level_id`/`genre_id` FKs + relationships + `*_name` properties |
| `backend/app/schemas/book_schema.py` | Modify | 5 | `genre` replaces `book_type`; name resolution via `validation_alias`; `cover_url` → `BookRead` only |
| `backend/app/repositories/book_repo.py` | Rewrite | 5 | 2.0 `select()`; entity-filtered `search()` |
| `backend/app/services/book_service.py` | Rewrite | 5 | 605 → thin orchestration; entity name resolution on create/update |
| `backend/app/api/book_router.py` | Rewrite | 5 | RoleChecker everywhere, X-Accel stream, error mapping |
| `backend/migrations/versions/<hash>_authors_levels_genres.py` | Create | 5 | The data-preserving migration (full code below) |
| `backend/app/tests/media/test_book_search.py`, `test_book_stream.py`, `test_book_upload.py` | Create | 5 | Red-first probes |
| `backend/app/repositories/tag_repo.py` | Rewrite | 6 | 2.0 + `get_or_create_by_names`; dead methods deleted |
| `backend/app/services/tag_service.py` | Create | 6 | `list_tags()` |
| `backend/app/api/tag_router.py` | Rewrite | 6 | RoleChecker + service call |
| `backend/app/services/media_errors.py`, `media_validator.py` | Create | 7 | Media domain errors + video extension whitelist |
| `backend/app/services/media_file_storage.py` | Create | 7 | `save` / `resolve` / `delete` with containment |
| `backend/app/tests/media/test_media_validator.py`, `test_media_storage.py` | Create | 7 | Leaf unit tests |
| `backend/app/models/video.py`, `video_tag.py` | Rewrite | 8 | 2.0 `mapped_column()` — identical columns (spec §5: converted inside the fused rewrite) |
| `backend/app/repositories/video_repo.py`, `services/video_service.py`, `api/video_router.py`, `schemas/video_schema.py` | Rewrite | 8 | Video fused rewrite — 2.0, auth, whitelist, X-Accel |
| `backend/app/tests/media/test_media_stream.py` | Create | 8 | X-Accel contract probes (video) |
| `nginx/nginx.conf` | Create | 9 | The front proxy: `/api/`, `/static/covers/`, internal `/media/` |
| `docker-compose.yml` | Modify | 9 | Add nginx service; unpublish 8000 |
| `backend/app/main.py` | Modify | 9 | Remove `StaticFiles` covers mount |
| `docs/superpowers/specs/react-kickoff-annex.md` | Create | 10 | React integration decisions (spec §9) |
| `docs/superpowers/plans/2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md`, `docs/superpowers/specs/2026-08-16-book-refactor-design.md` | **Delete** | 10 | Superseded by this plan + spec |
| `AGENTS.md`, `README.md`, `STATE.md` | Modify | 10 | Point at the new plan; document nginx workflow |
| `backend/app/config.py`, `services/video_service.py`, nginx comment, migration `<hash>_video_dir_rename.py`, stream tests | Modify/Create | 11 | `vids` → `videos` rename + data migration |
| `backend/app/repositories/tag_repo.py`, `author_repo.py`, `level_repo.py`, `genre_repo.py`, `services/book_service.py`, `video_service.py`, tests | Modify | 12 | Orphan tag/entity cleanup after delete/update |
| `backend/app/services/video_metadata_reader.py`, `models/video.py`, `schemas/video_schema.py`, `services/video_service.py`, migration `<hash>_video_poster.py`, tests | Create/Modify | 13 | Video poster thumbnails (ffmpeg-optional) |
| `backend/app/api/video_router.py` | Modify | 14 | Student read-only: write endpoints → admin/teacher |
| `backend/app/services/image_validator.py`, `services/book_service.py`, `api/book_router.py`, tests | Create/Modify | 15 | Cover replacement on PUT (behind image validator) |
| `backend/app/services/epub_converter.py`, `services/book_service.py`, `api/book_router.py`, tests | Create/Modify | 16 | epub→pdf + `GET /books/{uid}/read` |

Audio files (`models/audio.py`, `audio_tag.py`, `repositories/audio_repo.py`, `api/audio_router.py`, `schemas/audio_schema.py`) appear nowhere in this table. Deliberate.

## Debt Coverage Annex (fresh-measured baseline, 2026-09-01)

Snapshot of the target files at plan start; every row is struck by a rewrite task. Callout rows belong to the hygiene plan's remaining debt — red on those files is expected, out of scope.

| File | ruff | mypy | Owning task |
|---|---|---|---|
| `app/api/video_router.py` | 0 | 15 | 8 (rewrite) |
| `app/api/tag_router.py` | 0 | 1 | 6 (rewrite) |
| `app/api/book_router.py` | 3 | 22 | 5 (rewrite) |
| `app/services/book_service.py` | 15 | 17 | 5 (rewrite) |
| `app/repositories/book_repo.py` | 2 | 1 | 5 (rewrite) |
| `app/schemas/book_schema.py` | 0 | 2 | 5 (rewrite) |
| `app/models/book.py`, `book_tag.py` | 0 | 3 | 5 |
| `app/models/tag.py` | 0 | 1 | 6 (touch — clear or log) |
| `app/repositories/video_repo.py` | 0 | 2 | 8 (rewrite) |
| `app/repositories/tag_repo.py` | 0 | 2 | 6 (rewrite) |
| `app/models/video.py`, `video_tag.py` | 0 | 4 | 8 (rewrite) |
| `app/schemas/video_schema.py` | 0 | 0 | 8 renames keep it at 0 |
| `app/api/audio_router.py` (0/19), `app/repositories/audio_repo.py` (0/5), `app/models/audio.py`+`audio_tag.py` (0/4) | — | — | **deferred — the future audio plan owns these; do not touch** |

> Re-measure at plan start with `uv run mypy <files> --strict`; if a number moved, update the row — the "strike the row" gate is 0/0 per file, whatever the starting value.

# PART A — Characterization pins

Part A pins current behavior — including its bugs — per the TDD-workflow spec's decision 2. Every pin is **witnessed green against the legacy code**: that is what makes it a pin rather than a wish. Bugs are pinned as-broken (`pytest.raises(...)`) and flipped red-first in Task 8. Legacy has no auth: Part A requests carry **no headers**; Task 8 adds `auth_headers` and the 401 guards. Uploads write to `VIDS_DIR`, bound once at module import (`video_router.py:17`) — pins must monkeypatch the module constant (`monkeypatch.setattr(video_router_module, "VIDS_DIR", tmp_path)`), not `settings.VIDEO_DIR`.

### Task 1: Video characterization pins

**Files:**
- Create: `backend/app/tests/media/test_video_repo.py`
- Create: `backend/app/tests/media/test_video_api.py`

**Interfaces:**
- Consumes: legacy `Video_Repo` (`create_video`, `delete_video`), `Video` model, `Video_Create`/`Video_View` schemas
- Produces: the video pinned-behavior statement, with these deliberate features: upload takes `title` **(required Form)** + optional `description`/`tags`; **no extension validation exists** (pinned as-is; Task 8 flips); content type from `mimetypes.guess_type(file_path)` with `application/octet-stream` fallback; unknown stream extensions resolve via `guess_type` (`.mp4` → `video/mp4`)

**Why (learning):** pins are written first because everything downstream is measured against them: the Task 8 rewrite runs the identical test files and must stay green except where a fix deliberately flips a pin. A pin that passes for the wrong reason teaches nothing — seed through the API where possible, assert both the response *and* the DB state.

Seeding idiom (sample — the body is yours):

```python
def _seed_video(db, *, title: str = "clip", file_path: str = "/tmp/nonexistent.mp4") -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid
```

Auth is absent on legacy — requests carry no headers.

- [x] **Step 1: Write `test_video_repo.py`** — three cases:
  1. `create_video` persists: row gets an id; `title`/`description`/`file_path` round-trip; `deleted_at` is `None`
  2. `delete_video` soft-deletes: `deleted_at` set (compare `datetime.now(UTC)` within a small delta), row still present in DB
  3. `delete_video` on a missing id **raises** — the bug pin: `with pytest.raises(AttributeError): Video_Repo(db).delete_video(999999)`

- [x] **Step 2: Write `test_video_api.py`** — case list (bodies yours):
  1. `GET /videos/` empty → `200 []`
  2. `GET /videos/` excludes a soft-deleted row (seed two, delete one via repo) — set assertion, no order
  3. Upload happy: `files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42 mock bytes", "video/mp4")}`, form `title="Intro"`, `description="first"`, `tags="lesson"` → `200`: `title == "Intro"` (form wins), `video_url == f"/videos/stream/{id}"`, tag linked; file under `monkeypatch.setattr(settings, "VIDEO_DIR", tmp_path)`
  4. Missing `title` → `422`
  5. `.txt` filename → **`200`** — the quirk pin (no validation exists). Comment: Task 8 flips to `400`
  6. `tags=" MATH , math "` → single tag, first-seen case reused when a pre-existing row exists
  7. `upload_multiple` valid pair → `200` list of two, title = filename stem
  8. `upload_multiple` with a `.txt` second file → **still `200` and both rows commit** today (no validation = no failure). Task 8's probe flips this
  9. `PATCH` title/description/tags replace; `tags=""` clears; omitted leaves; old `Tag` rows survive; missing id → `404` detail `Video not found`
  10. `DELETE /videos/{id}` → `200` pinned keys; excluded after; row kept
  11. `DELETE /videos/999999` → bug pin: `with pytest.raises(AttributeError)`
  12. `GET /videos/stream/{id}` (seed real file at `tmp_path`) → `200`, `Content-Type: video/mp4`, byte-for-byte
  13. `GET /videos/stream/999999` → `404` detail `Video not found`
  14. Stream soft-deleted → `200` (quirk pin)
  15. Missing file on disk → bug pin: `with pytest.raises(FileNotFoundError)` — **flip target for Task 8**

- [x] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/media/test_video_repo.py app/tests/media/test_video_api.py -v`. Expected: all pass (~18 tests). If a pin fails, fix the **pin** to match verified behavior and record the deviation at the bottom of this task; do not fix legacy code here.

- [x] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/media/test_video_repo.py app/tests/media/test_video_api.py && uv run ruff check app/tests/media/test_video_repo.py app/tests/media/test_video_api.py --ignore B008
git add backend/app/tests/media/test_video_repo.py backend/app/tests/media/test_video_api.py
git commit -m "test: pin video module behavior — list, upload, patch, delete, stream"
```

---

### Task 2: Tag characterization pins

**Files:**
- Create: `backend/app/tests/media/test_tag_repo.py`
- Create: `backend/app/tests/media/test_tag_api.py`

**Interfaces:**
- Produces: the pinned statement Task 6 preserves — `GET /tags/` is an unordered list of `{id, name}`; `get_tag_by_id` returns `None` on a missing id (legacy `.first()`); `create_tag` applies the `TagCreate` validator (whitespace collapse, charset, length). `get_tag_by_id` and `create_tag` are dead in the app today (only `tag_router → get_all_tags` calls `TagRepo`) — their pins become their deletion's justification

- [x] **Step 1: Write `test_tag_repo.py`:**
  1. `get_all_tags` returns seeded rows (three) — set of names
  2. `get_tag_by_id(seeded)` → row with `name`; `get_tag_by_id(999999)` → `None`
  3. `create_tag(TagCreate(name="  Math  "))` → stored `"Math"`; re-run with `"Math"` → unique-constraint `IntegrityError` (DB is the guarantee; `ilike` matching is UX)

- [x] **Step 2: Write `test_tag_api.py`:**
  1. `GET /tags/` empty → `200 []`
  2. `GET /tags/` with three seeded → `200`, set of `{id, name}`

- [x] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py -v`. Expected: all pass.

- [x] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py && uv run ruff check app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py --ignore B008
git add backend/app/tests/media/test_tag_repo.py backend/app/tests/media/test_tag_api.py
git commit -m "test: pin tag module behavior — list, lookup, create normalization"
```

# PART B — Entities

### Task 3: Entity modules — Author, Level, Genre (identical shape ×3)

> **Lint/type gate:** new files ship clean (0/0).

**Files:**
- Create: `backend/app/models/author.py`, `level.py`, `genre.py`
- Create: `backend/app/schemas/author_schema.py`, `level_schema.py`, `genre_schema.py`
- Create: `backend/app/repositories/author_repo.py`, `level_repo.py`, `genre_repo.py`
- Create: `backend/app/services/author_service.py`, `level_service.py`, `genre_service.py`
- Create: `backend/app/api/author_router.py`, `level_router.py`, `genre_router.py`
- Test: `backend/app/tests/media/test_entity_repos.py`, `test_entity_api.py`

**Interfaces:**

*Model* (use `Author` as the template — `Level`/`Genre` are renames):

```python
class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
```

Table names: `authors`, `levels`, `genres`. No relationships yet — the `Book.author/level/genre` relationships are added when the book model gains its FK columns (Task 5) and use `back_populates` then (the reciprocal `books: Mapped[list[Book]]` also lands in Task 5). Export all three from `models/__init__.py`.

*Schema* (per entity, e.g. `author_schema.py`):

```python
class AuthorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class AuthorRead(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
```

*Repo* — **this is the load-bearing contract; the exact semantics are the deliverable.** Two methods per entity (e.g. `author_repo.py`):

```python
class AuthorRepo:
    def __init__(self, db: Session) -> None: ...
    def get_by_name(self, name: str) -> Author | None:
        # case-insensitive match, stored case returned; None when absent.
        # Search filter semantics (Task 5): None -> WHERE false, never a create.
        return self.db.execute(
            select(Author).where(func.lower(Author.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Author:
        # Write path (Task 5). Reuse by case-insensitive match with STORED case;
        # create lowercased when absent. One query, then insert.
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        entity = Author(name=name.strip().lower())
        self.db.add(entity)
        self.db.commit()          # commit-stays-in-repo (legacy convention)
        self.db.refresh(entity)
        return entity

    def list_all(self) -> list[Author]:
        return list(self.db.scalars(select(Author).order_by(Author.name)).all())
```

The unique constraint is the DB guarantee; a concurrent double-create raises `IntegrityError`, which the consuming router maps to 400 (spec §5). Do **not** catch it here.

*Service* (thin layering seam): `class AuthorService` with `__init__(self, db: Session)` and `list_authors() -> list[AuthorRead]` mapping `AuthorRepo(db).list_all()`. Same shape for Level/Genre.

*Router* (e.g. `author_router.py`):

```python
router = APIRouter(prefix="/authors", tags=["authors"])

@router.get("/", response_model=list[AuthorRead])
def list_authors(
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])),
    db: Session = Depends(get_db),
):
    return AuthorService(db).list_authors()
```

No POST/PATCH/DELETE — entities are created implicitly by upload/update and listed; that is the entire surface (spec §4: "not a full feature").

**Why (learning):** three carbon-copy modules are the point, not the waste — each is *one* drill of the pattern `Tag` establishes, and `get_by_name`/`get_or_create_by_name` are the semantics Task 5 stands on. The search/write split matters: search must never create rows (searching for a nonexistent author returns zero books), writes may. `func.lower(Entity.name) == name` reproduces `ilike`'s case-insensitive match in 2.0 idiom so nothing stores `NULL` or a typo case. All three entities live on books only — with audio out of scope there is no `audio.author_id`, no `Author.audio_tracks`, no audio router consuming these.

- [ ] **Step 1: Write the failing tests**

`test_entity_repos.py` — parametrize over the three `(RepoClass, ModelClass)` pairs; cases:
1. `get_by_name("MATH")` after creating `Model(name="Math")` → returns the row (stored case `"Math"`); `get_by_name("missing")` → `None`
2. `get_or_create_by_name("  MATH ")` with existing `"Math"` → same row, no second insert (count == 1)
3. `get_or_create_by_name("Algebra")` fresh → creates row stored `"algebra"`, returns it
4. `list_all()` → sorted by name

`test_entity_api.py` — per prefix (`/authors/`, `/levels/`, `/genres/`); use `setup_admin(client, setup_paths)` + `login` + `auth_headers` (idiom from `app/tests/auth/test_auth_api.py`):
1. Authed `GET` → `200`, list of `{id, name}` (seed 2 rows per entity)
2. Unauthenticated `GET` → `401`

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/media/test_entity_repos.py app/tests/media/test_entity_api.py -v`. Expected: collection ERROR `ModuleNotFoundError: No module named 'app.models.author'`.

- [ ] **Step 3: Implement all fifteen files** per the Interfaces. The three routers join `api/__init__.py`, the repos join `repositories/__init__.py` (`__all__`), and `main.py` includes the routers.

- [ ] **Step 4: Verify green** — `cd backend && uv run pytest app/tests/media/test_entity_repos.py app/tests/media/test_entity_api.py -v`. Expected: all pass.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/models/__init__.py app/repositories/__init__.py app/api/__init__.py app/main.py app/tests/media/test_entity_repos.py app/tests/media/test_entity_api.py && uv run ruff check app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/models/__init__.py app/repositories/__init__.py app/api/__init__.py app/main.py app/tests/media/test_entity_repos.py app/tests/media/test_entity_api.py --ignore B008 && uv run mypy app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py --strict
```

Expected: 0/0 on all new files.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/author.py backend/app/models/level.py backend/app/models/genre.py backend/app/models/__init__.py backend/app/schemas/author_schema.py backend/app/schemas/level_schema.py backend/app/schemas/genre_schema.py backend/app/repositories/author_repo.py backend/app/repositories/level_repo.py backend/app/repositories/genre_repo.py backend/app/repositories/__init__.py backend/app/services/author_service.py backend/app/services/level_service.py backend/app/services/genre_service.py backend/app/api/author_router.py backend/app/api/level_router.py backend/app/api/genre_router.py backend/app/api/__init__.py backend/app/main.py backend/app/tests/media/test_entity_repos.py backend/app/tests/media/test_entity_api.py
git commit -m "feat: author/level/genre entities — tag-pattern modules with get_or_create_by_name"
```

---

# PART C — Book refactor

### Task 4: Book leaf modules (four sections, commit per section)

> **Lint/type gate:** each section ships clean (0/0). The old book plan's Tasks 1–4 folded into one task; boundaries unchanged, each section green independently.

**Why (learning):** leaf-first, exactly as the old plan: nothing imports them yet, the tree stays green after every section, and a regression in Task 5 isolates to *wiring* rather than to a leaf. Contracts below are the old plan's verbatim; the only change is import form (`from app.config import settings`).

- [ ] **Section A — `book_errors.py` + `ContentValidator`**
  - Files: create `backend/app/services/book_errors.py`, `content_validator.py`; test `backend/app/tests/media/test_book_validator.py`
  - Interfaces: `BookError(Exception)` with `detail: str` defaulting from per-class `default_detail`; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed`; `ContentValidator.validate(file_bytes: bytes, filename: str) -> str` returns lowercase extension, raises `InvalidBookFile` on empty bytes, oversized (>`settings.MAX_UPLOAD_SIZE`), disallowed extension (`settings.ALLOWED_EXTENSIONS`), or magic-byte mismatch (pdf: `b"%PDF-"`, epub: `b"PK\x03\x04"`)
  - Tests (bodies yours — old plan Task 1 case list): empty→raise; `.exe`→raise; `b"not a real pdf"` named `.pdf`→raise; oversize via `monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)`→raise; `b"%PDF-1.4..."` named `Report.PDF`→`"pdf"`; `b"PK\x03\x04..."`→`"epub"`. Red = `ModuleNotFoundError: app.services.book_errors`
  - Commit: `feat: add book domain errors and ContentValidator upload gate`

- [ ] **Section B — `BookFileStorage`**
  - Files: create `backend/app/services/book_file_storage.py`; test `backend/app/tests/media/test_book_storage.py`
  - Interfaces: `save(file_bytes, filename, uid) -> str` (relative single-component name under `UPLOAD_DIR`); `delete(rel_path) -> None`; `delete_cover(cover_name) -> None`; `resolve(rel_path) -> Path` raising `BookNotFound` on traversal (`is_relative_to` containment) or missing file; `cover_dir -> Path` property
  - Tests: 7 cases per old plan Task 2 (traversal raise, round-trip, hostile filename sanitization, silent deletes, cover_dir)
  - Commit: `feat: add BookFileStorage with UPLOAD_DIR traversal containment`

- [ ] **Section C — `EpubMetadataReader`**
  - Files: create `backend/app/services/epub_metadata_reader.py`; test `backend/app/tests/media/test_book_epub_reader.py`
  - Interfaces: `@dataclass(frozen=True) BookMetadata` — `title: str | None`, `author: str | None`, `language: str | None`, `tags: list[str]` (field named **`tags`**, not `subjects`); `EpubMetadataReader.read(path: Path) -> BookMetadata | None`, never raises. Import `pymupdf` (not `fitz` — mypy `--strict`), `# type: ignore[no-untyped-call]` at `pymupdf.open`
  - Tests: 3 cases (corrupt→None, missing→None, minimal EPUB fixture→title/author)
  - Commit: `feat: add EpubMetadataReader leaf module with EPUB metadata tests`

- [ ] **Section D — `CoverGenerator`**
  - Files: create `backend/app/services/cover_generator.py`; test `backend/app/tests/media/test_book_cover.py`
  - Interfaces: `generate(source_path: Path, dest_dir: Path) -> bool` — dest is a **directory**, name is `{source_path.stem}.png`; PDF → page-0 render; EPUB → OPF-declared cover → XHTML `<img>` → first-image fallback; `False` on any failure, never raises; size-check against `settings.MAX_COVER_SIZE`
  - Tests: 5 cases (corrupt PDF→False; real PDF→True + file ≤ MAX; EPUB-with-cover→True; EPUB-no-images→False; MAX_COVER_SIZE=1 monkeypatch→False)
  - Commit: `feat: add CoverGenerator leaf module with cover generation tests`

- [ ] **Section E: Full-suite smoke after all four sections** — `cd backend && uv run pytest -v`. Expected: everything green (`app/tests/auth/` + all new files).

- [ ] **Section F: Tick this task's box in the same commit** (if the plan file is committed with Section D, no separate commit needed — see Global Constraints).

---

### Task 5: FUSED book rewrite + the data-preserving migration (single commit)

> **Lint/type gate — the big one:** `book_service.py` (15/17), `book_router.py` (3/22), `book_repo.py` (2/1), `book_schema.py` (0/2), `models/book.py` (0/3) reach 0/0 by the final step.

**Files:**
- Modify: `backend/app/models/book.py`
- Modify: `backend/app/schemas/book_schema.py`
- Rewrite: `backend/app/repositories/book_repo.py`
- Rewrite: `backend/app/services/book_service.py`
- Rewrite: `backend/app/api/book_router.py`
- Create: `backend/migrations/versions/<hash>_authors_levels_genres.py`
- Test: `backend/app/tests/media/test_book_search.py`, `test_book_stream.py`, `test_book_upload.py` (Create)

**Interfaces:**

*Models* — `book.py` changes:
- **Drop** `book_type`; **add** `author_id`/`level_id`/`genre_id`:

```python
author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id", ondelete="SET NULL"), nullable=True)
level_id: Mapped[int | None] = mapped_column(ForeignKey("levels.id", ondelete="SET NULL"), nullable=True)
genre_id: Mapped[int | None] = mapped_column(ForeignKey("genres.id", ondelete="SET NULL"), nullable=True)
author: Mapped[Author | None] = relationship(back_populates="books")
level: Mapped[Level | None] = relationship(back_populates="books")
genre: Mapped[Genre | None] = relationship(back_populates="books")
```

- `Author`/`Level`/`Genre` models gain the reciprocal `books: Mapped[list[Book]]` relationships
- Add three plain properties (the schema's name-resolution hooks):

```python
@property
def author_name(self) -> str | None:
    return self.author.name if self.author else None
```

(same for `level_name`, `genre_name`)

*Schemas* — `BookBase` drops `author`/`level`/`book_type` fields. `BookCreate`/`BookUpdate`/`BookUpload` gain `author: str | None`, `level: str | None`, `genre: str | None` (raw names — the service resolves). `BookRead` exposes resolved names via the model properties — the novel idiom (Pydantic v2 `from_attributes` follows `validation_alias`):

```python
class BookRead(BookBase):
    id: int
    author: str | None = Field(default=None, validation_alias="author_name")
    level: str | None = Field(default=None, validation_alias="level_name")
    genre: str | None = Field(default=None, validation_alias="genre_name")
    created_at: datetime
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    @computed_field
    @property
    def cover_url(self) -> str | None:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"
```

`cover_url` lives on `BookRead` **only** (write schemas must not carry it). `BookSearchCriteria`: `q, author, level, genre, language, tags, extension, metadata_` (genre replaces book_type).

*Repo* — full 2.0 rewrite, old plan Task 5a semantics plus entities:

```python
def search(self, criteria: BookSearchCriteria, *, limit: int, offset: int) -> Page[BookRead]
```

- `selectinload` for `tags` **and** `author`/`level`/`genre` (joinedload + LIMIT truncation lesson)
- Entry points: `q` → `ilike` on title; `language`/`extension` → column eq; `tags` → `Book.tags.any(Tag.name.in_(...))` (OR semantics); `metadata_` → `Book.metadata_.contains(...)` (`@>`)
- **Author/level/genre filters:** resolve the name first via the entity repo's `get_by_name` (`AuthorRepo(db).get_by_name(criteria.author)`); a `None` resolution emits `WHERE false` (zero rows — spec §4); a resolved entity filters `Book.author_id == entity.id`
- `ORDER BY (Book.created_at.desc(), Book.id.desc())`; `total` over `stmt.order_by(None).subquery()` — honest count
- Also: `get_book_by_uid(book_uid) -> Book | None` (with the three selectinloads), `create_book(book_create) -> Book` (ValueError on dup uid; `IntegrityError` propagates), `update_book`, `delete_book`, `cleanup_orphan_tags`
- `create_book`/`update_book` build `model_dump(exclude={"tags"})` — no `cover_url` exclusion needed anymore (it left the write schemas)

*Service* — thin orchestration (~130 lines), old plan Task 5b plus entity resolution. Constructor: `(book_repo, validator, storage, epub_reader, cover_generator, author_repo, level_repo, genre_repo)`. `create_from_upload(metadata: BookUpload, filename, data, content_type) -> BookRead`:
1. `validator.validate` first — nothing on disk before this
2. title fallback: `metadata.title or Path(filename).stem` cleaned
3. `rel_path = storage.save(...)`
4. EPUB metadata prefill (best-effort): merge `author`/`language`/`tags` without duplicating tag names
5. resolve entities: `author_id = AuthorRepo.get_or_create_by_name(metadata.author).id` **only when** `metadata.author` is not None (same for level/genre); EPUB-prefilled author uses the same resolution
6. cover best-effort → `cover_name`
7. `BookCreate(...)`; `repo.create_book`; `ValueError` (dup uid) → `storage.delete` + raise `BookAlreadyExists`
- `update_book`, `delete_book` (file+cover then row), `get_book_by_uid`, `search`, `get_book_file(uid) -> Path` (via `storage.resolve`)
- **Deleted, stated honestly:** inline cover replacement on PUT; epub→pdf + `/read`

*Router* — full rewrite, old plan Task 5c minus Range parsing (nginx's job now), plus `genre` in forms:
- `RoleChecker` on every endpoint (read = admin/teacher/student, write = admin/teacher)
- `POST /books/upload` (multipart; form fields `title, author, level, genre, language, tags`), `GET /books/` (`Page[BookRead]`, `BookSearchCriteria` as query params), `GET /books/{uid}`, `PUT /books/{uid}`, `DELETE /books/{uid}` (204), `GET /books/{uid}/stream` → **X-Accel** (below). Deleted: `GET /books/search/`, `GET /books/{uid}/epub`, `/read`
- **The X-Accel stream endpoint — full code, this shape is the contract for Task 8 too:**

```python
from urllib.parse import quote

@router.get("/{book_uid}/stream")
def stream_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])),
) -> Response:
    media_path, media_type = svc.resolve_stream(book_uid)  # raises BookNotFound
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/books/{quote(media_path.name)}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )
```

`quote(media_path.name)` is baked into the contract — the basename, percent-encoded (see spec §5 for the latin-1/raw-space failure it prevents). The stream probes in `test_book_stream.py` assert the **quoted** form.

`BookService.resolve_stream(book_uid) -> tuple[Path, str]` — book missing → `BookNotFound`; `storage.resolve()` (containment + existence) → `BookNotFound`; media type from `MEDIA_TYPES = {"pdf": "application/pdf", "epub": "application/epub+zip"}` keyed by extension. Error mapping: `InvalidBookFile`→400, `BookAlreadyExists`→409, `BookNotFound`→404, `IntegrityError`→400, `ValueError`→400.

**The migration (full code — data-touching, no learner delegation).** Create `backend/migrations/versions/<hash>_authors_levels_genres.py` **by hand** (NOT autogenerate — autogenerate cannot do backfill). `down_revision` is the baseline `70ee18aafdca` — with audio out of scope there is no intermediate revision to chain through (spec §6):

```python
"""authors/levels/genres entities: books FK conversion, drop book_type

Revision ID: <your-hash>
Revises: 70ee18aafdca  (initial schema)
"""
from alembic import op
import sqlalchemy as sa

revision = "<your-hash>"
down_revision = "70ee18aafdca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.create_table(
        "levels",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.add_column("books", sa.Column("author_id", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("level_id", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("genre_id", sa.Integer(), nullable=True))

    # Backfill authors/levels from DISTINCT trimmed lowercased strings
    op.execute(
        "INSERT INTO authors (name) "
        "SELECT DISTINCT lower(trim(author)) FROM books "
        "WHERE author IS NOT NULL AND trim(author) <> ''"
    )
    op.execute(
        "UPDATE books SET author_id = a.id FROM authors a "
        "WHERE lower(trim(books.author)) = a.name"
    )
    op.execute(
        "INSERT INTO levels (name) "
        "SELECT DISTINCT lower(trim(level)) FROM books "
        "WHERE level IS NOT NULL AND trim(level) <> ''"
    )
    op.execute(
        "UPDATE books SET level_id = l.id FROM levels l "
        "WHERE lower(trim(books.level)) = l.name"
    )
    # Genres: backfill ONLY rows whose book_type is not a junk MIME value.
    # (The old file_type conflation wrote "application/pdf" here; extension already
    #  carries the format, so junk is discarded, per spec §4.)
    op.execute(
        "INSERT INTO genres (name) "
        "SELECT DISTINCT lower(trim(book_type)) FROM books "
        "WHERE book_type IS NOT NULL AND trim(book_type) <> '' "
        "AND book_type NOT LIKE '%/%'"
    )
    op.execute(
        "UPDATE books SET genre_id = g.id FROM genres g "
        "WHERE lower(trim(books.book_type)) = g.name"
    )

    op.drop_column("books", "author")
    op.drop_column("books", "level")
    op.drop_column("books", "book_type")

    op.create_foreign_key("fk_books_author_id_authors", "books", "authors", ["author_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_books_level_id_levels", "books", "levels", ["level_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_books_genre_id_genres", "books", "genres", ["genre_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.add_column("books", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("books", sa.Column("level", sa.String(length=100), nullable=True))
    op.add_column("books", sa.Column("book_type", sa.String(length=100), nullable=True))
    op.execute("UPDATE books SET author = a.name FROM authors a WHERE a.id = books.author_id")
    op.execute("UPDATE books SET level = l.name FROM levels l WHERE l.id = books.level_id")
    op.execute("UPDATE books SET book_type = g.name FROM genres g WHERE g.id = books.genre_id")
    op.drop_constraint("fk_books_author_id_authors", "books", type_="foreignkey")
    op.drop_constraint("fk_books_level_id_levels", "books", type_="foreignkey")
    op.drop_constraint("fk_books_genre_id_genres", "books", type_="foreignkey")
    op.drop_column("books", "author_id")
    op.drop_column("books", "level_id")
    op.drop_column("books", "genre_id")
    op.drop_table("genres")
    op.drop_table("levels")
    op.drop_table("authors")
```

Notes: the lowercased-name round-trip loss on `downgrade()` is the accepted display-case trade-off, locked in spec §4. The only schema this revision adds is the entity tables + book FKs — audio is untouched. Additionally: `sa.Column("name", ..., unique=True, index=True)` on the three entity tables is enough for the tasks that follow (no GIN/functional indexes needed — `get_by_name`'s `lower(name)` scan is fine at school-library cardinality; add `func.lower` indexes later if measurements demand — do NOT expand scope now).

**Why (learning):** one commit for the whole module plus its migration, for the old plan's fused-rewrite reason — split commits would leave `GET /books/search/` raising `AttributeError` at call time. The migration is in the *same* commit because the code and its schema are one unit: any checkout between the book rewrite and a later migration commit would have dev compose running new code against an old DB (no `genre_id` → `UndefinedColumn` at runtime). The compose entrypoint runs `alembic upgrade head` before uvicorn, so the same-commit migration is what keeps `git pull && cat STATE.md` resumable.

- [ ] **Step 5a-i: Write the failing tests**

**`test_book_search.py`** — repo-level probes, red against legacy `BookRepo` (`search` doesn't exist → `AttributeError`):
1. `test_search_genre_filter_and_entities` — seed `Author(name="Ada")`, `Genre(name="scifi")`, two books linked via `book.genre = g`; `search(BookSearchCriteria(genre="SCIFI"), limit=10, offset=0)` → only the scifi book, `total == 1`; the response's `genre == "scifi"`
2. `test_search_unknown_author_matches_nothing` — `search(BookSearchCriteria(author="nobody"))` → `total == 0` (the `WHERE false` contract)
3. `test_search_tags_or_semantics_and_honest_total` — old plan 5a probe 1 verbatim
4. `test_search_metadata_containment` — old plan 5a probe 2 verbatim
5. `test_search_pagination_pages_are_disjoint_and_complete` — old plan 5a probe 3 verbatim

**`test_book_stream.py`** — the X-Accel contract (seeded book whose file exists under a monkeypatched `UPLOAD_DIR`; auth via `auth_headers`):
1. `GET /books/{uid}/stream` authed → **204**, headers `X-Accel-Redirect == f"/media/books/{quote(uid)}.pdf"` (`from urllib.parse import quote`; asserts the percent-encoded form, pins encoding), `Content-Type: application/pdf`, `Accept-Ranges: bytes`; **body empty**
2. Missing book → 404
3. Poisoned row (`file_path == "../../../../etc/passwd"`) → 404 (containment — C4)
4. Row whose file is missing on disk → 404
5. Unauthenticated → 401
6. EPUB book → `Content-Type: application/epub+zip`

**`test_book_upload.py`** — old plan 5a-i list verbatim (real PDF happy path, bad-magic 400 with nothing on disk, auth required), plus: upload with form `genre="Sci-Fi"` → 200 and (`genre_id` linked): `db.expire_all()`, book row's `genre.name == "sci-fi"`; upload with `author="Ada Lovelace"` → `authors` row stored `"ada lovelace"`.

- [ ] **Step 5a-ii: Verify they fail** — `cd backend && uv run pytest app/tests/media/test_book_search.py app/tests/media/test_book_stream.py app/tests/media/test_book_upload.py -v`. Expected red: `AttributeError: 'BookRepo' object has no attribute 'search'`; stream tests 404-route-missing or 200-stream (either is fine — the point is red); upload probes fail (no genre resolution). Everything else (pins, auth, leaves) green.

- [ ] **Step 5b: Model + schemas** per Interfaces. Gate: `cd backend && uv run mypy app/models/book.py app/schemas/book_schema.py --strict` → 0. Run `uv run pytest -v` — expect ONLY the three probe files red; all other files green. The model change reads `author_id` before the migration exists → the testcontainers harness `create_all`s the column so tests stay green; dev compose is safe because the migration lands in this same commit.

- [ ] **Step 5c: Repo** per Interfaces. Gate: `cd backend && uv run mypy app/repositories/book_repo.py --strict && uv run pytest app/tests/media/test_book_search.py -v` → 0 mypy + search probes green.

- [ ] **Step 5d: Service** per Interfaces. Gate: `cd backend && uv run mypy app/services/book_service.py --strict` + `grep -n "HTTPException\|fitz\|open(" app/services/book_service.py` prints nothing.

- [ ] **Step 5e: Router** per Interfaces. Gate: `cd backend && uv run pytest -v` → all green.

- [ ] **Step 5f: Write the migration** (full code above) and verify it:
  1. Generate a fresh hash: `cd backend && uv run alembic revision --rev-id "$(uuidgen | cut -c1-12)" -m "authors levels genres entities"` then paste the body (or `--autogenerate` against an empty DB and *replace* the body — the backfill is hand-written either way)
  2. **Upgrade/downgrade round-trip on an empty DB:**

```bash
docker compose up -d db
docker compose exec db psql -U postgres -c "CREATE DATABASE jirani_migtest;" 2>/dev/null || true
docker compose exec db psql -U postgres -d jirani_migtest -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic downgrade -1
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic upgrade head
```

  Expected: all three succeed; `downgrade -1` restores `books.author/level/book_type` columns; final upgrade re-applies.
  3. **Data-preservation check against real dev data** (spec §6 — do not skip; this is the backfill's only safety net): back up the dev DB, upgrade a *copy*, assert the backfill.

```bash
docker compose exec db pg_dump -U postgres -d jirani_library > /tmp/jirani_backup.sql
docker compose exec db psql -U postgres -c "CREATE DATABASE jirani_bk;" 2>/dev/null || true
docker compose exec db psql -U postgres -d jirani_bk -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cat /tmp/jirani_backup.sql | docker compose exec -T db psql -U postgres -d jirani_bk
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_bk uv run alembic upgrade head
docker compose exec db psql -U postgres -d jirani_bk -c "
SELECT (SELECT count(*) FROM books) AS books,
       (SELECT count(*) FROM books WHERE author_id IS NOT NULL) AS with_author,
       (SELECT count(*) FROM authors) AS authors,
       (SELECT count(*) FROM books WHERE genre_id IS NOT NULL) AS with_genre,
       (SELECT count(*) FROM genres) AS genres;"
```

  Expected: `with_author` equals the number of books that had a non-empty `author` string pre-migration (compare against `jirani_library` counts before the upgrade run); `genres` matches non-junk `book_type` values. Mismatch → STOP, fix the SQL before anything else.
  4. Then apply to the dev DB itself: `cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_library uv run alembic upgrade head`

- [ ] **Step 5g: Full suite + lint + type**

```bash
cd backend && uv run ruff format app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/media/test_book_search.py app/tests/media/test_book_stream.py app/tests/media/test_book_upload.py && uv run ruff check app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/media/test_book_search.py app/tests/media/test_book_stream.py app/tests/media/test_book_upload.py --ignore B008 && uv run mypy app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py --strict && uv run pytest -v
```

Expected: 0/0 on all six; full suite green (auth + pins + leaves + entities + the three book probe files).

- [ ] **Step 5h: `/done` then commit** — dispatch the `invariant-auditor` on the diff (this task exceeds the ~50-line review threshold; the migration SQL especially). On PASS:

```bash
git add backend/app/models/book.py backend/app/models/author.py backend/app/models/level.py backend/app/models/genre.py backend/app/schemas/book_schema.py backend/app/repositories/book_repo.py backend/app/services/book_service.py backend/app/api/book_router.py backend/migrations backend/app/tests/media/test_book_search.py backend/app/tests/media/test_book_stream.py backend/app/tests/media/test_book_upload.py
git commit -m "refactor: book model on author/level/genre FKs, X-Accel stream, thin service; migration with data backfill"
```

---

# PART D — Tag + media leaves + video fused rewrite

### Task 6: Tag fused rewrite — 2.0 repo + service + router auth

> **Lint/type gate:** `tag_repo.py` (0/2), `tag_router.py` (0/1), `models/tag.py` (0/1) end at 0/0.

**Files:**
- Rewrite: `backend/app/repositories/tag_repo.py`
- Create: `backend/app/services/tag_service.py`
- Rewrite: `backend/app/api/tag_router.py`
- Test: `backend/app/tests/media/test_tag_repo.py`, `test_tag_api.py` (Modify)

**Interfaces:**
- `TagRepo.get_all_tags() -> list[Tag]` — 2.0 `select(Tag)`
- `TagRepo.get_or_create_by_names(names: list[str]) -> list[Tag]` — legacy semantics exactly, in one query plus inserts: case-insensitive match reuses **stored case**; missing names created **lowercased**; duplicates collapse; first-occurrence order. Match query: `select(Tag).where(func.lower(Tag.name).in_({n.strip().lower() for n in names}))`, then insert the misses. The old per-name `Tag.name.ilike(...)` loop in the video router dies when Task 8 lands — do not keep two implementations
- `get_tag_by_id` + `create_tag` **deleted** (dead — Task 2 pins justify). Their pin cases updated: `get_tag_by_id` cases removed, `create_tag` normalization case becomes a deleted pin (record in commit message)
- `TagService(db: Session)` with `list_tags() -> list[TagRead]`
- Router: `GET /tags/` keeps prefix + response model; gains `Depends(RoleChecker([admin, teacher, student]))`; calls the service; holds **no** queries

- [ ] **Step 1: Update Part A pins + never-test red**
  - `test_tag_api.py`: wrap every `get("/tags/")` in `headers=auth_headers(token)`; add unauthenticated → `401` probe
  - `test_tag_repo.py`: delete the `get_tag_by_id` cases and the unique-constraint case (dead-method pins)
  - Run: `cd backend && uv run pytest app/tests/media/test_tag_api.py -v`. Expected: the 401 probe **fails** (legacy returns 200 — red for the right reason); the 200 cases now 401 too (they lack headers until Step 3's rewrite — acceptable, same red)

- [ ] **Step 2: Implement** — repo, service, router per Interfaces.

- [ ] **Step 3: Verify green** — `cd backend && uv run pytest app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py -v`. Expected: all pass including 401.

- [ ] **Step 4: Format, lint, type**

```bash
cd backend && uv run ruff format app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py && uv run ruff check app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/media/test_tag_repo.py app/tests/media/test_tag_api.py --ignore B008 && uv run mypy app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/models/tag.py --strict
```

Expected: 0/0 (Annex tag rows struck).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/tag_repo.py backend/app/services/tag_service.py backend/app/api/tag_router.py backend/app/models/tag.py backend/app/tests/media/test_tag_repo.py backend/app/tests/media/test_tag_api.py
git commit -m "refactor: tag module — 2.0 repo, service layer, auth; drop dead get_tag_by_id/create_tag"
```

---

### Task 7: Media leaf modules — `media_errors.py`, `media_validator.py`, `MediaFileStorage`

> **Lint/type gate:** new files ship clean (0/0).

**Files:**
- Create: `backend/app/services/media_errors.py`, `media_validator.py`
- Create: `backend/app/services/media_file_storage.py`
- Test: `backend/app/tests/media/test_media_validator.py`, `test_media_storage.py` (Create)

**Interfaces** — verbatim from the old media plan Tasks 4–5, scoped to video:
- `MediaError(Exception)` — `__init__(detail: str | None = None)`, attribute `detail` falling back to class `default_detail`; `MediaNotFound` (`"Media not found"`), `InvalidMediaFile` (`"Invalid media file"`); no HTTP types
- `ALLOWED_VIDEO_EXTENSIONS: frozenset[str]` = `{"mp4","mov","avi","mkv","webm","m4v","ogv","wmv"}`. Do **not** add an audio whitelist here — audio is out of scope and its legacy `ALLOWED_AUDIO` constant stays live in `audio_router.py:17` until the future audio plan
- `validate_media(filename: str, *, allowed: frozenset[str]) -> str` — lowercase extension; `InvalidMediaFile(f"File type .{ext} not allowed")` on disallowed (same detail shape as the legacy audio message — the 400 that Task 8's flip pin asserts). The whitelist lives in the validator, not `config.py` (domain knowledge, not deployment settings — deliberate deviation from the book's `ContentValidator`, recorded so nobody "fixes" it)
- `MediaFileStorage(save_dir: Path)` — `save(file_bytes: bytes, filename: str) -> str` (`mkdir(parents=True, exist_ok=True)`, `{uuid4}_{filename}`, returns the **absolute** path string); `resolve(path: str) -> Path` raising `MediaNotFound` on (a) traversal — `is_relative_to` containment — or (b) `is_file()` false; relative stored paths join to `save_dir` (covers legacy rows holding `"uploads/vids/..."`); `delete(path: str) -> None` (resolve + `unlink(missing_ok=True)`)

- [ ] **Step 1: Write failing tests** — old media plan Task 4's six validator cases (parametrized over `ALLOWED_VIDEO_EXTENSIONS`) + Task 5's nine storage cases (traversal, round-trip, nested names, legacy relative form, missing file, silent delete). The disallowed-extension case asserts the exact detail `File type .txt not allowed`.

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/media/test_media_validator.py app/tests/media/test_media_storage.py -v`. Expected: `ModuleNotFoundError: app.services.media_validator`.

- [ ] **Step 3: Implement** per Interfaces.

- [ ] **Step 4: Verify green** — same command. Expected: all pass.

- [ ] **Step 5: Format, lint, type**

```bash
cd backend && uv run ruff format app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/tests/media/test_media_validator.py app/tests/media/test_media_storage.py && uv run ruff check app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/tests/media/test_media_validator.py app/tests/media/test_media_storage.py --ignore B008 && uv run mypy app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py --strict
```

Expected: 0/0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/media_errors.py backend/app/services/media_validator.py backend/app/services/media_file_storage.py backend/app/tests/media/test_media_validator.py backend/app/tests/media/test_media_storage.py
git commit -m "feat: media domain errors, video extension validator, MediaFileStorage"
```

---

### Task 8: Video fused rewrite — 2.0 models, service layer, auth, whitelist, X-Accel

> **Lint/type gate:** `video_router.py` (0/15), `video_repo.py` (0/2), `models/video.py`+`video_tag.py` (0/4 from the 2.0 conversion) end at 0/0.

**Files:**
- Rewrite: `backend/app/models/video.py`, `video_tag.py` (2.0 conversion — spec §5: inside the fused rewrite)
- Rewrite: `backend/app/repositories/video_repo.py`
- Create: `backend/app/services/video_service.py`
- Rewrite: `backend/app/api/video_router.py`
- Modify: `backend/app/schemas/video_schema.py` (renames + delete `Video_Delete`)
- Test: `test_video_repo.py`, `test_video_api.py` (Modify), `backend/app/tests/media/test_media_stream.py` (Create)

**Interfaces:**

*Models* — `Video`/`VideoTag` convert to 2.0 `Mapped[]`/`mapped_column()` with **identical columns** (no schema delta — no migration needed, the harness `create_all`s the same table). Table names unchanged: `"video"`, `"video_tags"` (matches the existing DB — do not "fix" the singular). `VideoTag`: `UniqueConstraint("video_id", "tag_id")`, `ondelete="CASCADE"` FKs.

*Schemas*: `VideoCreate` (rename of `Video_Create`), `VideoView` (`id, title, description, video_url, tags` — intentional view contract, no `file_path` leak); `Video_Delete` deleted (dead).

*Repo* — 2.0 `select()`: `create(video_create) -> Video`, `get_by_id(id) -> Video | None` (`selectinload(Video.tags)`), `list_active() -> list[Video]` (legacy listing semantics — soft-deleted excluded, no ORDER BY guarantee pinned), `soft_delete(id) -> Video | None` (`deleted_at` set; `None` when missing — missing is a return value, killing the live `None.deleted_at` 500).

*Service* — `VideoService(db)`:
- `list_videos()`, `upload(file_bytes, filename, *, title, description, tag_names) -> VideoView` (**`title` required**, `validate_media(..., allowed=ALLOWED_VIDEO_EXTENSIONS)` — the new whitelist), `upload_multiple(files) -> list[VideoView]` (validate-all-first, then persist — the partial-commit fix), `update(...)`, `soft_delete(id) -> VideoView` (missing → `MediaNotFound("Video not found")`), `resolve_stream(id) -> tuple[Path, str]` (row missing → `MediaNotFound("Video not found")`; `storage.resolve` → containment/missing → `MediaNotFound`; media type via `mimetypes.guess_type(path)` → `application/octet-stream` fallback — legacy pin preserved; **does not filter `deleted_at`** — the soft-deleted-stream quirk preserved). No author (spec §4).
- `TagRepo.get_or_create_by_names` (Task 6) replaces the inline `ilike` tag loop; the validator (Task 7) replaces the missing extension gate.

*Router* — prefix `/videos`, `RoleChecker([admin, teacher, student])` on **every** endpoint (the student read-only split for video lands in Task 14, Part G); `POST /upload` (multipart file + form `title: str = Form(...)` / `description` / `tags`), `POST /upload_multiple`, `PATCH /{id}`, `DELETE /{id}`, `GET /stream/{id}` → **the Task 5 X-Accel shape, `kind="vids"`** (Task 11 renames this kind to `videos`):

```python
from urllib.parse import quote

return Response(status_code=204, headers={
    "X-Accel-Redirect": f"/media/vids/{quote(media_path.name)}",
    "Content-Type": media_type,
    "Accept-Ranges": "bytes",
})
```

  The router holds no queries, no `open()`, no tag logic. Mapping: `InvalidMediaFile`/`IntegrityError`→400, `MediaNotFound`→404.

- [ ] **Step 1: Write the failing tests / update pins**

**Modify `test_video_api.py`:**
1. `auth_headers(token)` on every request + parametrized 401 guard (all six paths: `/`, `/upload`, `/upload_multiple`, `/patch`, `/delete`, `/stream`)
2. Flip bug pins (red on legacy): case 5 (`.txt` accepted) → `400` detail `File type .txt not allowed` (red on legacy 200); case 8 (partial-commit) → after failing batch, `GET /videos/` yields **zero** rows and zero files under patched `VIDEO_DIR`; case 11 delete-missing → 404 (legacy raises `AttributeError`); case 15 missing-file stream → 404 (legacy `FileNotFoundError`); case 14 (soft-deleted stream) stays; case 6 (tag reuse) stays
3. **Flip the stream pin** (case 12): `GET /videos/stream/{id}` → **204**, body empty, `X-Accel-Redirect == f"/media/vids/{quote(filename)}"` (quoted, same contract as Task 5), `Content-Type` per `guess_type`, `Accept-Ranges: bytes` — legacy returns 200+body → red
4. Strip `file_path`-specific asserts if any snuck in — the view contract exposes no paths

**Modify `test_video_repo.py`:** case 3 flips to `VideoRepo(db).soft_delete(999999) -> None` (legacy raises); class import becomes `VideoRepo`; `delete_video` calls become `soft_delete`.

**Create `test_media_stream.py`** (video cases): the X-Accel contract rows — 204 + `f"/media/vids/{quote(name)}"` (quoted, per Task 5) for mp4/mov/webm; 404 missing id; 404 missing disk file; 404 traversal-seeded `file_path`; 401 unauthenticated; one **spaced filename** (`"my clip.mp4"`) seeded at `tmp_path` asserting `X-Accel-Redirect == "/media/vids/my%20clip.mp4"` — the regression that guards the encoding. (No audio cases — audio's stream stays the legacy 200-with-body generator, unpinned and untouched.)

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/media/test_video_repo.py app/tests/media/test_video_api.py app/tests/media/test_media_stream.py -v`. Expected red, each for the right reason (401 vs legacy 200; `AttributeError` on delete-missing; both rows surviving the bad batch; `FileNotFoundError`; 200-with-body vs 204 asserts; `test_media_stream.py` collection ERROR on the missing `video_service` module — correct red for a new module). Everything else green.

- [ ] **Step 3: Convert the models to 2.0** per Interfaces (identical columns). Evidence of neutrality: `cd backend && uv run pytest app/tests/media/test_video_repo.py app/tests/media/test_video_api.py -v` — the unflipped pins stay green; only the deliberate Step-1 flips stay red. No migration — zero schema delta.

- [ ] **Step 4: Implement** — schemas renames → repo → service → router per Interfaces; add `VideoRepo` to `repositories/__init__.py`.

- [ ] **Step 5: Verify green** — `cd backend && uv run pytest app/tests/media/test_video_repo.py app/tests/media/test_video_api.py app/tests/media/test_media_stream.py -v`. Expected: all pass.

- [ ] **Step 6: Format, lint, type**

```bash
cd backend && uv run ruff format app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/media/test_video_api.py app/tests/media/test_video_repo.py app/tests/media/test_media_stream.py && uv run ruff check app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/media/test_video_api.py app/tests/media/test_video_repo.py app/tests/media/test_media_stream.py --ignore B008 && uv run mypy app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py --strict
```

Expected: 0/0 (Annex video rows struck).

- [ ] **Step 7: Commit** (one commit — the fused rewrite is one unit, models included)

```bash
git add backend/app/models/video.py backend/app/models/video_tag.py backend/app/repositories/video_repo.py backend/app/services/video_service.py backend/app/api/video_router.py backend/app/schemas/video_schema.py backend/app/repositories/__init__.py backend/app/tests/media/test_video_api.py backend/app/tests/media/test_video_repo.py backend/app/tests/media/test_media_stream.py
git commit -m "refactor: video module — 2.0 models, service layer, auth, whitelist, X-Accel stream, delete-404"
```

# PART E — nginx + integration

### Task 9: nginx fronts everything

> **Lint/type gate:** `main.py` modification keeps its current clean state; nginx config has no Python surface.

**Files:**
- Create: `nginx/nginx.conf`
- Modify: `docker-compose.yml`
- Modify: `backend/app/main.py` (remove the `StaticFiles` covers mount — nginx takes `/static/covers/` over; the `cover_url` computed field is untouched, same URL prefix)

**Interfaces:**
- `nginx:80` is the only published port. `backend` publishes nothing (internal docker network only).
- `/api/` strips the prefix → `http://backend:8000/`; `/docs` + `/` route to backend unchanged (general fallback location); `/static/covers/` public static; `/media/` **internal** alias (X-Accel target only — one location handles both kinds because the redirect URIs are `/media/books/…` and `/media/vids/…`; if audio later moves to X-Accel its `/media/audio/…` redirects resolve through the same alias with no config change)

**Full config — paste this** (the deployment correctness gate; not learner-delegated):

```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 60m;   # MAX_UPLOAD_SIZE is 50MB — leave headroom

    location = /api { return 302 /api/; }

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }

    # Public: book covers are browsable assets (same URL prefix as before,
    # same computed cover_url — only the server behind it changed).
    location /static/covers/ {
        alias /srv/uploads/covers/;
        add_header Cache-Control "public, max-age=86400";
    }

    # Internal: reachable ONLY via X-Accel-Redirect from the backend.
    # /media/books/x.pdf -> /srv/uploads/books/x.pdf
    # /media/vids/x.mp4  -> /srv/uploads/vids/x.mp4
    location /media/ {
        internal;
        alias /srv/uploads/;
    }

    # Everything else (/, /docs, /openapi.json, future routes) -> API.
    # (When the React integration lands — see the Task 10 annex — this
    #  block becomes try_files $uri $uri/ /index.html serving frontend/dist;
    #  /api/, /media/, /static/covers/ keep precedence.)
    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }
}
```

**Full compose — paste this:**

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: jirani_postgres
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    restart: unless-stopped
    environment:
      POSTGRES_DB: jirani_library
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d jirani_library"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: jirani_api
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/jirani_library
      DEBUG: "true"
      STUDENT_DEFAULT_PASSWORD: student123
      TEACHER_DEFAULT_PASSWORD: teacher123
    volumes:
      - ./uploads:/app/uploads

  nginx:
    image: nginx:1.27-alpine
    container_name: jirani_nginx
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./uploads:/srv/uploads:ro

volumes:
  postgres_data:
```

(The `db` keeps publishing `5432` — deliberate: Task 5's migration steps and `psql` debugging connect from the host. The `db:5432` publish and the `backend:8000` removal are the only port changes.)

**Why (learning):** three lessons. (1) **The `internal` directive is the security boundary.** A public `/media/` location would let anyone browse files directly and leak the naming scheme; `internal` means the only path to media is through a backend endpoint that already ran `RoleChecker` + `resolve()` containment. (2) **`alias` maps URI to filesystem; `proxy_pass` maps URI to upstream** — the two are not interchangeable, and a wrong `alias` is a silent content-leak. The `/media/` alias pairs with redirect URIs the backend builds from `media_path.name` only (a basename, already containment-checked) — the one-internal-location shape is spec §3. (3) **Streaming auth is layer-split.** FastAPI owns the decision (auth, row lookup, containment, 404), nginx owns the bytes (sendfile, Range). The 204 response's headers are the interface between the two — that is why the unit tests pin the header contract exactly.

- [ ] **Step 1: Add `nginx/nginx.conf`** (above).

- [ ] **Step 2: Update `docker-compose.yml`** (above — remove `ports: ["8000:8000"]` under backend, add the nginx service).

- [ ] **Step 3: Remove the StaticFiles mount in `main.py`** — delete the `app.mount("/static/covers", ...)` block and the now-unused `StaticFiles` import (ruff F401 will flag it). Keep the five `settings.*_DIR.mkdir` lines — the app still writes there.

- [ ] **Step 4: API smoke through nginx** — `docker compose up -d --build`, then:

```bash
curl -s http://localhost/ | grep -q "Welcome" && echo "root OK"
curl -s http://localhost/api/auth/login -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your admin password>"}' > /tmp/login.json
TOKEN=$(python3 -c "import json,sys; print(json.load(open('/tmp/login.json'))['access_token'])")
```

  Expected: `root OK`; login returns a token. (`/api/` prefix proves the strip works; a 404 at `http://localhost/api/` curl without prefix-strip would mean the proxy config is wrong.)

- [ ] **Step 5: The one Range integration check (replaces the deleted Python Range tables)** — upload or seed a small video file, then:

```bash
curl -s -D - -o /dev/null -H "Authorization: Bearer $TOKEN" \
  -H "Range: bytes=0-99" "http://localhost/api/videos/stream/<id>"
```

  Expected: `HTTP/1.1 206`, `Content-Range: bytes 0-99/<size>`, `Accept-Ranges: bytes`. Also try without `Range` → 200; a suffixed range `bytes=-500` → 206 tail. This proves nginx's RFC 7233 coverage — the behavior the pytest suite deliberately no longer owns (spec §6 mitigation). Record the output in the commit message body or STATE.md.

> Note for local dev without docker (plain `uv run uvicorn`): the 204+X-Accel endpoint has no nginx to serve the file, so media is unreachable — that is expected and per-spec. Local media testing goes through the compose stack; local *API* testing is unaffected (TestClient works without nginx).

- [ ] **Step 6: Format, lint, type** — `cd backend && uv run ruff format app/main.py && uv run ruff check app/main.py --ignore B008 && uv run mypy app/main.py --strict`. Expected: 0/0. Then `uv run pytest -v` — full suite green (nothing about nginx touches the tests).

- [ ] **Step 7: Commit**

```bash
git add nginx/nginx.conf docker-compose.yml backend/app/main.py
git commit -m "feat: nginx front proxy — X-Accel media, public covers, /api routing"
```

# PART F — React annex + final gate + old artifacts

### Task 10: React kickoff annex + final gate — DoD, removals, docs

**Files:**
- Create: `docs/superpowers/specs/react-kickoff-annex.md`
- Delete: `docs/superpowers/plans/2026-08-16-book-refactor.md`, `docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md`, `docs/superpowers/specs/2026-08-16-book-refactor-design.md`
- Modify: `AGENTS.md` (plan references + invariant table), `README.md`, `STATE.md`

**Why (learning):** a refactor plan is done when the DoD has actually run, the old artifacts can no longer be executed by accident (the `plan-auditor` reads both plan trees — stale plans with fresh checkboxes is how drift happens), the docs point at the one true plan, and the backend contract is frozen for React (§9). Deleting superseded docs is a contribution; git history is the archive (AGENTS.md). Note for this task: `frontend/` already exists in the tree (TypeScript + Vite, landed 2026-09-01, ahead of this plan closing) — the annex records actual decisions and current facts, not wishes.

- [ ] **Step 1: Write the React kickoff annex** — create `docs/superpowers/specs/react-kickoff-annex.md` with this content:

```markdown
# React Kickoff Annex — SPA integration decisions (2026-09-01)

Recorded by the media refactor plan's final task (spec §9). The frontend scaffold
(`frontend/`, TypeScript + Vite) landed in the tree 2026-09-01, ahead of plan close.
The backend contract below is frozen; React pins to it.

## Topology — same-origin (Option A, locked)

- The single `nginx:80` published port serves both API and SPA. The nginx config
  gains one block — the `frontend/dist` build output mounted into nginx at
  `/srv/frontend`, with `location /` replaced by:

  ```nginx
  location / {
      root /srv/frontend;
      try_files $uri $uri/ /index.html;
  }
  ```

  `/api/`, `/media/`, `/static/covers/` keep precedence (longer-prefix match).
  No CORS surface, no second published port. Backend is *not* restructured for this.

## Token strategy

- Login: `POST /api/auth/login` returns `{access_token, ...}`.
- Token stored in `localStorage`; every API call goes through a fetch wrapper
  adding `Authorization: Bearer <token>`.

## Role gating

- Role decoded from the JWT payload (`RoleChecker` mirrors it on the backend).
  UI routes gate on it client-side as UX — never as security.

## Media access

- `<img src="/static/covers/...">` works natively (covers are public).
- Protected streams (`/api/books/{uid}/stream`, `/api/videos/stream/{id}`):
  native `<video>/<embed>` tags cannot carry the `Authorization` header.
  Interim pattern (a): fetch with the wrapper into a blob URL
  (`URL.createObjectURL`), buffering the whole file client-side.
  Follow-up (b): a short-lived signed query ticket (`?ticket=`) as a later
  backend feature task — decided deliberately when the SPA media work lands,
  not silently.

## Error shape

- UI reads `{detail}` uniformly; the backend error mapping (Invariant 2)
  already guarantees that shape.

## Where things live

- `frontend/` gets its own convention section in `AGENTS.md` (added in the
  same commit as this annex); the backend advisory boundaries stay unchanged.

## Backend contract frozen surface (for the SPA to pin)

- Response schemas: `BookRead` (incl. `cover_url`), `VideoView`, `TagRead`,
  `AuthorRead`/`LevelRead`/`GenreRead`, `Page[T]`.
- Error body shape: `{detail: str}`.
- Auth: Bearer JWT with role claim.
- URL prefixes: `/api/`, `/media/` (internal-only), `/static/covers/` (public).
```

- [ ] **Step 2: Full DoD sweep**

```bash
cd backend && uv run ruff format . && uv run ruff check . --fix --ignore B008 && uv run pytest -v
```

  Expected: format clean; ruff shows only ledger rows owned by remaining hygiene/audio debt — if `--fix` touches a file outside this plan's map, include it in the commit and note it; full suite green (auth, video, tag, entity, book ×3, media leaf files).

- [ ] **Step 3: mypy --strict on every file this plan touched**

```bash
cd backend && uv run mypy app/models/author.py app/models/level.py app/models/genre.py app/models/book.py app/models/video.py app/models/video_tag.py app/models/tag.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/schemas/book_schema.py app/schemas/video_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/repositories/book_repo.py app/repositories/video_repo.py app/repositories/tag_repo.py app/repositories/__init__.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/services/book_service.py app/services/video_service.py app/services/tag_service.py app/services/book_errors.py app/services/content_validator.py app/services/book_file_storage.py app/services/epub_metadata_reader.py app/services/cover_generator.py app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/api/book_router.py app/api/video_router.py app/api/tag_router.py app/main.py --strict
```

  Expected: 0 errors — the Annex fully struck for this plan. **Audio files are deliberately absent** — their rows belong to the future audio plan. Do **not** run `mypy . --strict` as a gate; auth/config/database/audio files remain other plans' rows.

- [ ] **Step 4: Bug-inventory sweep** — `cd backend && grep -rn "uploads/vids\|uploads/audio" app/ --include='*.py' | grep -v tests` → no matches in this plan's touched files (no CWD-relative literals remain there — audio's literal is out of scope and may still match); `grep -rn "print(" app/services/ app/api/` → no matches in the touched files (legacy audio lines may match — out of scope), i.e. verify none of the touched files added any.

- [ ] **Step 5: `/done`** — dispatches `invariant-auditor` then `verifier` over the accumulated diff in one gate. On PASS proceed; a VIOLATION or failed run is a failed gate.

- [ ] **Step 6: Delete the superseded artifacts**

```bash
git rm docs/superpowers/plans/2026-08-16-book-refactor.md docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md docs/superpowers/specs/2026-08-16-book-refactor-design.md
```

- [ ] **Step 7: Update `AGENTS.md` references** (requires explicit user go-ahead — this file is the repo's contract)
  1. "Two plans are in flight" becomes `2026-08-15-codebase-hygiene` alone; the media refactor plan's main pass is **complete** — its Part G follow-ons (Tasks 11–16) remain open and are listed in STATE.md
  2. Any "book-refactor plan Task X is the reference pattern" wording → "the 2026-09-01 media refactor plan's Task 5" (the pattern survives, the file does not)
  3. The six-invariant "Violating today" column — book/video/tag rows are struck (layering, CWD-relative paths, 2.0, tests, naming). The **audio rows stay** (audio_router inline DB + tag logic, `Audio_Repo` naming, zero tests, CWD literal, Python streaming) with a pointer at the deferred audio plan; `/auth/reset-password` 500 stays if still true
  4. Add the `frontend/` convention note (per the annex's last bullet)

- [ ] **Step 8: Update README + STATE**

  README "Notes" gains: media is served by nginx (`docker compose up -d --build` brings it up; API at `/api/*`; protected media via X-Accel — never expose `/media/`). Troubleshooting entry: if API calls return 502 after a `backend` container restart, `docker compose restart nginx` — nginx caches the upstream's IP at startup and must be re-resolved. *(If README.md edits are outside your write permissions, put the exact sentences in a chat message for the user to paste.)* Then invoke the `state` skill: record the completed main pass, log the surviving annex rows (hygiene + audio debt), note the media-unreachable-without-nginx dev behavior and the loud zero-auth `/audio/` warning, and list the Part G follow-ons (Tasks 11–16) + the audio deferral as open items.

- [ ] **Step 9: Refresh the knowledge graph + final commit**

```bash
graphify update .
git add nginx/nginx.conf docker-compose.yml backend/app/main.py docs/superpowers/specs/react-kickoff-annex.md AGENTS.md README.md
git commit -m "chore: media refactor complete — final gate, react annex, removed superseded book/avt plans, docs updated"
```

  Tick every completed task box in **this** plan file before that commit (boxes checked in the same commit as their tasks per Global Constraints — any stragglers go here).

## Deferred Work — preserved for a later pass

Only two items stay deferred (user 2026-09-01 — everything else is now scheduled as Part G, below):

- **D0: Audio module refactor** — user-deferred 2026-09-01 (spec §7). `Audio`/`AudioTag`/`AudioRepo`/`audio_router` stay legacy 1.x with inline DB + zero tests + Python-streamed bytes + zero auth. Its own future plan picks it up; the pin case lists and rewrite task exist in git history (`2026-08-26-audio-video-tag-refactor.md` at its pre-revision commit). **Until that plan runs, `/audio/` endpoints remain zero-auth — flag loudly in any deployment that matters.** Audio's ruff/mypy debt rows (audio_router 0/19, audio_repo 0/5, models 0/4) were dropped from this plan's annex and belong to that plan
- **React follow-ups (annex):** signed-ticket streaming option (b), nginx `try_files` block, `frontend/` AGENTS.md convention — handled when the React track executes the Task 10 annex. Deferred deliberately, not lost

# PART G — Post-refactor follow-ons (the former deferrals, scheduled)

Part G runs **after** Task 10 (the anchor contract in the React annex). Every task here is additive against that frozen surface — the `BookRead`/`VideoView` shapes may gain fields, never lose or rename them, so the SPA keeps working across all of Part G. Same discipline as the main pass: TDD (a step that says red must visibly fail first), 0/0 lint/type on touched files, per-task commit with the plan tick. Each task ends with a full `cd backend && uv run pytest -v` that must be green.

### Task 11: `uploads/vids` → `uploads/videos` directory rename (data migration)

> **Lint/type gate:** touched files end 0/0; the migration must round-trip on the temp-DB harness.

**Files:**
- Modify: `backend/app/config.py` (`VIDEO_DIR: Path = BASE_DIR / "uploads" / "videos"`)
- Modify: `backend/app/services/video_service.py` (the X-Accel kind `"vids"` → `"videos"`, so URIs `/media/videos/…` still map through the nginx alias to the renamed dir)
- Create: `backend/migrations/versions/<hash>_video_dir_rename.py` — `down_revision = <task5-hash>` (head at this point; Task 13 chains off **this** hash)
- Modify: `backend/app/tests/media/test_video_api.py` (stream pin), `test_media_stream.py` (redirect URIs), and the `nginx/nginx.conf` comment block (Task 9's file — comment only, no behavior change)

**Interfaces:** the stored `file_path` values live in `video` rows; legacy forms are absolute (`/app/uploads/vids/…` in-container) or relative (`uploads/vids/…`) — both contain the substring `uploads/vids/`, so one `replace()` covers both. **Files must move on disk too**, not just strings: the operator step below is not optional.

- [ ] **Step 1: Operators' file move, done before any migration on the dev DB** — `docker compose down` → rename on the host volume: `mv uploads/vids uploads/videos` (if it doesn't exist yet, `mkdir -p uploads/videos` and stop — nothing to move) → `docker compose up -d`
- [ ] **Step 2: Red-first probes** — flip the stream assertions: `X-Accel-Redirect == f"/media/videos/{quote(filename)}"` and `test_media_stream.py`'s rows to `/media/videos/...`. Run `cd backend && uv run pytest app/tests/media/test_video_api.py app/tests/media/test_video_repo.py app/tests/media/test_media_stream.py -v` — expected red: the code still emits `/media/vids/`. Everything else green.
- [ ] **Step 3: The migration** (full code — data-touching, no learner delegation):

```python
"""video file paths: uploads/vids -> uploads/videos

Revision ID: <your-hash>
Revises: <task5-hash>  (authors/levels/genres)
"""
from alembic import op

revision = "<your-hash>"
down_revision = "<task5-hash>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE video SET file_path = replace(file_path, 'uploads/vids/', 'uploads/videos/') "
        "WHERE file_path LIKE '%uploads/vids/%'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE video SET file_path = replace(file_path, 'uploads/videos/', 'uploads/vids/') "
        "WHERE file_path LIKE '%uploads/videos/%'"
    )
```

- [ ] **Step 4: `config.py` + `video_service.py`** per Interfaces. Note the mkdir lines in `main.py` read `settings.VIDEO_DIR` — no edit needed there. Verify green — same command as Step 2, all pass now.
- [ ] **Step 5: Migration round-trip on a scratch DB** — same pattern as Task 5f step 2 (`jirani_migtest`-style DB): `upgrade head` → `downgrade -1` → `upgrade head`, all three succeed. Then apply to dev: `cd backend && uv run alembic upgrade head`.
- [ ] **Step 6: Sweeps** — `grep -rn "uploads/vids" backend/app/ --include='*.py'` → zero matches (the CWD-relative literal dies here for video; audio's sites are out of scope and may still match — verify none of the matches are in this task's touched files). `grep -rn "/media/vids/" backend/ nginx/` → only history/comments if any, no live code.
- [ ] **Step 7: Format, lint, type + commit** — same shape as the main pass (ruff format/check `--ignore B008`, mypy on the touched files, full `uv run pytest -v` green), then:

```bash
git add backend/app/config.py backend/app/services/video_service.py backend/migrations backend/app/tests/media/test_video_api.py backend/app/tests/media/test_media_stream.py nginx/nginx.conf
git commit -m "feat: rename uploads/vids to uploads/videos — config, X-Accel kind, data migration"
```

---

### Task 12: Orphan `Tag` + entity rows — cleanup after delete/update

> **Lint/type gate:** touched files end 0/0.

**Files:**
- Modify: `backend/app/repositories/tag_repo.py`, `author_repo.py`, `level_repo.py`, `genre_repo.py`
- Modify: `backend/app/services/book_service.py`, `video_service.py`
- Test: extend `backend/app/tests/media/test_book_upload.py` + `test_video_api.py` (or a new `test_orphan_cleanup.py` — either)

**Interfaces:**
- `TagRepo.delete_orphans() -> int` — deletes tags linked to **no** book and **no** video, returns the count. 2.0 shape, existence-based: `select(Tag).where(~Tag.books.any(), ~Tag.videos.any())` then `delete(Tag).where(... same ...)` — one query, no Python-side filtering (search semantics, not per-row loops)
- `AuthorRepo.delete_orphans() / LevelRepo.delete_orphans() / GenreRepo.delete_orphans() -> int` — entities whose `books` collection is empty (`~Author.books.any()`). Same pattern ×3
- `BookService`/`VideoService`: call `tag_repo.delete_orphans()` at the end of `delete_book` (after the row is gone), `update_book` and `VideoService.update` (after a link-set replacement), and `VideoService.soft_delete`. Entities: `BookService.delete_book` + `update_book` end with the three entity `delete_orphans()` (careful: only when the book's author/genre links changed — deleting a book calls all three; updating author/genre calls only the affected ones)
- **Never** call cleanup on read paths or search — search must never mutate (`get_by_name`'s WHERE-false contract stays pure)

**Why (learning):** the DB is the single truth for "orphaned": a tag with zero links is an orphan, period. Any Python-side "track what I just unlinked" logic re-implements link counting and drifts; the `NOT exists` query cannot.

- [ ] **Step 1: Red-first probes** — for each of these, assert the row is **gone** after the operation, run, witness red (the row survives today):
  1. Tag linked to exactly one book; admin `DELETE /books/{uid}` → `select(Tag)` count shows the tag row deleted
  2. Tag linked to two books; deleting one book → tag **survives** (never over-delete); deleting the second → gone
  3. Video's last-linked tag: `soft_delete` the video → tag gone (video link is the only one)
  4. Author row whose only book is deleted → `authors` row gone; an author linked to two books survives until the last book goes
  5. Search purity guard: `search(BookSearchCriteria(author="nobody"))` still returns zero rows and creates nothing after all of the above (the D0-class no-mutation rule)
- [ ] **Step 2: Implement** per Interfaces (repos first, service calls second).
- [ ] **Step 3: Verify green** — `cd backend && uv run pytest -v` — all pass.
- [ ] **Step 4: Format, lint, type + commit**:

```bash
git add backend/app/repositories/tag_repo.py backend/app/repositories/author_repo.py backend/app/repositories/level_repo.py backend/app/repositories/genre_repo.py backend/app/services/book_service.py backend/app/services/video_service.py <test files>
git commit -m "feat: orphan tag and entity cleanup after book/video delete and update"
```

---

### Task 13: Video poster thumbnails — ffmpeg-optional, never raises

> **Lint/type gate:** new files ship 0/0; `video_schema.py`/`models/video.py` touched rows cleared.

**Files:**
- Create: `backend/app/services/video_metadata_reader.py`; test `backend/app/tests/media/test_video_poster.py`
- Modify: `backend/app/models/video.py` (`poster_path` column — additive, nullable)
- Modify: `backend/app/schemas/video_schema.py` (`VideoView` gains `poster_url` — additive per the Part G preamble)
- Modify: `backend/app/services/video_service.py` (`upload`/`upload_multiple`: best-effort poster after save)
- Create: `backend/migrations/versions/<hash>_video_poster.py` — `down_revision = <task11-hash>` (chain order: task5 → task11 → **this**)
- Modify: `nginx/nginx.conf` comment only (posters live in `COVER_DIR`, served by the existing public `/static/covers/` alias — no new location)

**Interfaces:**
- `VideoMetadataReader.poster(source: Path, dest_dir: Path) -> str | None` — extracts a thumbnail via `ffmpeg -ss 1 -i <source> -frames:v 1 -vf scale=480:-2 <dest>/<uuid4>.jpg` as a **list of args** (never `shell=True` — the same no-shell rule as everywhere else); saves under `COVER_DIR` (name `{uuid4}.jpg`); returns the filename on success, `None` on **any** failure or when `shutil.which("ffmpeg")` is `None`. Never raises — the graceful read of reality: a deployment without ffmpeg simply has no posters
- `VideoService.upload`: after `MediaFileStorage.save`, call `poster(...)`; on a filename, set `poster_path` in the row. `VideoView.poster_url` is a computed field: `f"/static/covers/{poster_path}"` or `None` (same `computed_field` idiom as `BookRead.cover_url` — Task 5)
- Model column: `poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)`

- [ ] **Step 1: Red-first tests** (`test_video_poster.py`, new module → collection ERROR is the red):
  1. `ffmpeg` absent (`monkeypatch.setattr(shutil, "which", lambda _: None)`) → `None`, never raises
  2. Present + a fixture "ffmpeg" script in `tmp_path` that execs `cp <tiny-jpg> <dest-arg>` (a real tempfile JPEG: any 400-byte file will do — the function doesn't inspect bytes) → returns a filename, file exists in `dest_dir`
  3. Fixture ffmpeg `exit 1` → `None`
  4. Upload-flow probe (extend `test_video_api.py`): with a poster-fixture on the fake PATH, `POST /videos/upload` → `VideoView.poster_url == f"/static/covers/{name}"`
- [ ] **Step 2: Verify red** — collection ERROR for the new service module; the upload probe 200s today with `poster_url` absent.
- [ ] **Step 3: Migration** (hand-written, small):

```python
def upgrade() -> None:
    op.add_column("video", sa.Column("poster_path", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("video", "poster_path")
```

  Round-trip on the scratch-DB harness (up/down/up), then apply to dev.
- [ ] **Step 4: Implement** model → schema → service per Interfaces. Verify green; format/lint/type; commit:

```bash
git add backend/app/services/video_metadata_reader.py backend/app/models/video.py backend/app/schemas/video_schema.py backend/app/services/video_service.py backend/migrations backend/app/tests/media/test_video_poster.py backend/app/tests/media/test_video_api.py
git commit -m "feat: video poster thumbnails — ffmpeg-optional reader, poster_path column, VideoView.poster_url"
```

Note: audio ID3 metadata stays with D0 — this task is the video half of the old D3 deferral only.

---

### Task 14: Student read-only — video write endpoints → admin/teacher

> **Lint/type gate:** `video_router.py` stays 0/0.

**Files:**
- Modify: `backend/app/api/video_router.py` (this is the only in-scope router with write endpoints still open to students; the book router already gates write = admin/teacher since Task 5, and the entity/tag routers are GET-only)

**Interfaces:**
- Read endpoints unchanged: `GET /videos/`, `GET /videos/stream/{id}` → `RoleChecker([admin, teacher, student])`
- Write endpoints tighten: `POST /videos/upload`, `POST /videos/upload_multiple`, `PATCH /videos/{id}`, `DELETE /videos/{id}` → `RoleChecker([admin, teacher])`. Tokens carry the role in the JWT — no other backend change. (The audio endpoints stay zero-auth under D0 — the loud warning stands)

- [ ] **Step 1: Red-first probes** — login a student (harness idiom), then each of the four write verbs with the student token → assert `403` detail. Run → red: today every one returns 200/201/422-class responses because the guard list includes `student`.
- [ ] **Step 2: Implement** the four Depends-list changes.
- [ ] **Step 3: Verify green** — `cd backend && uv run pytest -v` — full suite incl. the new 403 probes and all existing admin/teacher write paths.
- [ ] **Step 4: Format, lint, type + commit**

```bash
git add backend/app/api/video_router.py backend/app/tests/media/test_video_api.py
git commit -m "feat: student read-only video endpoints — write verbs admin/teacher only"
```

Note to the React track: the SPA should hide upload/PATCH/DELETE UI behind the decoded role — the annex already says role gating is UX, this task makes the backend honestly enforce it.

---

### Task 15: Cover replacement on PUT — behind an image validator

> **Lint/type gate:** new files ship 0/0; `book_service.py`/`book_router.py` stay at their struck 0/0.

**Files:**
- Create: `backend/app/services/image_validator.py`; test `backend/app/tests/media/test_book_cover_replace.py`
- Modify: `backend/app/services/book_service.py`, `backend/app/api/book_router.py`

**Interfaces:**
- `InvalidImageError(BookError)` — detail `"Invalid image file"`; `ImageValidator.validate(file_bytes: bytes, filename: str) -> str` — returns the lowercase extension, raises `InvalidImageError` on: empty bytes, disallowed extension (against `settings.ALLOWED_IMAGE_EXTENSIONS` = `{jpg, jpeg, png, webp}`), ≥`settings.MAX_COVER_SIZE`, or magic-byte mismatch (jpeg `FF D8`, png `89 50 4E 47`, webp `RIFF…WEBP`; jpg/jpeg share magic). Sibling of `ContentValidator` (Task 4 Section A) — same validate-first, mutate-second shape, separate module because covers are images, not book files
- `BookService.update_book(uid, metadata, *, cover: bytes | None = None, cover_filename: str | None = None) -> BookRead` — when `cover` is present: validate **first**; then `storage.save_cover(uid, cover, ext)` → `{uid}.{ext}` in `COVER_DIR` (`save_cover` added to `BookFileStorage`, returns the relative name); **delete the old cover file if one existed**; set `cover_path`. When absent: cover untouched. Nothing lands on disk before validation (Invariant Best-Practice: validate first, mutate second)
- Router: `PUT /books/{uid}` becomes multipart (form fields stay `title, author, level, genre, language, tags`; plus optional `cover` `UploadFile`). Mapping: `InvalidImageError` → 400

- [ ] **Step 1: Red-first probes** — all three must fail today (the endpoint has no cover field):
  1. Admin `PUT /books/{uid}` with a real small PNG (`b"\x89PNG\r\n\x1a\n" + 100 padding bytes`) as `cover` → 200, `cover_url == f"/static/covers/{uid}.png"`, old cover file (seed one) removed from disk
  2. `.exe` magic with a `.png` name → 400 `Invalid image file`; `COVER_DIR` unchanged
  3. `PUT` with no `cover` → 200, `cover_url` unchanged
- [ ] **Step 2: Implement** validator → storage → service → router per Interfaces.
- [ ] **Step 3: Verify green** — `cd backend && uv run pytest -v` — all pass.
- [ ] **Step 4: Format, lint, type + commit**:

```bash
git add backend/app/services/image_validator.py backend/app/services/book_service.py backend/app/services/book_file_storage.py backend/app/api/book_router.py backend/app/tests/media/test_book_cover_replace.py
git commit -m "feat: cover replacement on PUT — ImageValidator gate, save_cover, optional multipart cover"
```

---

### Task 16: epub→pdf conversion + `GET /books/{uid}/read`

> **Lint/type gate:** new files ship 0/0; touched rows stay struck.

**Files:**
- Create: `backend/app/services/epub_converter.py`; test `backend/app/tests/media/test_book_read.py`
- Modify: `backend/app/services/book_service.py`, `backend/app/api/book_router.py`

**Interfaces:**
- `EpubConverter.convert(source: Path, dest_dir: Path) -> Path | None` — pymupdf (already a dependency, Task 4 Section C): `doc = pymupdf.open(source); pdf = doc.convert_to_pdf(); pdf.save(dest_dir / f"{source.stem}.read.pdf")` with the `# type: ignore[no-untyped-call]` idiom at the open; `None` on any failure, never raises. Callers cache: if the destination exists, skip the conversion
- `BookService.read_book(uid) -> tuple[Path, str]` — book row missing → `BookNotFound`; `.pdf` book → `(storage.resolve(...), "application/pdf")` (serve the original); epub → cached-or-convert `{uid}.read.pdf` **under `UPLOAD_DIR`** (so the nginx `/media/books/` alias serves it with zero config change — it's just another file in the books dir); conversion `None` → raise `BookNotFound("Book not readable")` (stays 404 — no new error mapping; the book exists, its render doesn't)
- Router: `GET /books/{uid}/read` → RoleChecker all three → the **Task 5 X-Accel shape** with kind `books`, `Content-Type: application/pdf`:

```python
from urllib.parse import quote

media_path, _ = svc.read_book(uid)
return Response(status_code=204, headers={
    "X-Accel-Redirect": f"/media/books/{quote(media_path.name)}",
    "Content-Type": "application/pdf",
    "Accept-Ranges": "bytes",
})
```

  (Resurrection of the endpoint deleted in Task 5 — now behind a real converter plus the same containment + auth the rest of the surface has.)

- [ ] **Step 1: Red-first probes** (`test_book_read.py`; the route is missing today → 404 is the red):
  1. Authed `GET /books/{uid}/read` on a PDF book → **204**, `X-Accel-Redirect == f"/media/books/{quote(uid)}.pdf"`, `Content-Type: application/pdf`, body empty
  2. EPUB book → 204, redirect `== f"/media/books/{quote(uid)}.read.pdf"`, **and the converted file exists** under the monkeypatched `UPLOAD_DIR`
  3. Converter failure (`monkeypatch` the converter to return `None`) → 404 detail `Book not readable`
  4. Second GET on the same EPUB → 204 and the converter **not called again** (spy/monkeypatch counts calls — the cache contract)
  5. Unauthenticated → 401
- [ ] **Step 2: Implement** converter → service → router per Interfaces.
- [ ] **Step 3: Verify green** — `cd backend && uv run pytest -v` — all pass.
- [ ] **Step 4: Format, lint, type + commit**:

```bash
git add backend/app/services/epub_converter.py backend/app/services/book_service.py backend/app/api/book_router.py backend/app/tests/media/test_book_read.py
git commit -m "feat: GET /books/{uid}/read — epub rendered to PDF via pymupdf, X-Accel served"
```

Note to the React track: this endpoint is the one in-browser reading uses; the SPA fetches or streams it like any other `/api/books/...` route — nothing in the annex changes.

## Self-Review

- **Spec coverage:** §1 goals (books + video only, nginx, entities) → Tasks 4/5/8/9 (refactor + nginx) and Tasks 3/5 (entities) ✓; §3 nginx topology → Task 9 with the one-`/media/`-location consolidation and the React `location /` fallback note ✓; §4 taxonomy + single-valued-FK semantics → Tasks 3/5 (books-only FK, `book_type`→`genre_id` rename, junk discarded); §4 entity semantics (case-insensitive reuse, lowercase create, GET-only, no PATCH/DELETE) → Task 3 ✓; §4 search (`WHERE false` on unknown name) → Task 5 repo + probe 2 ✓; §5 module architecture (entity modules, book changes, video changes, X-Accel contract, error mapping) → Tasks 3/4/5/8 ✓; §6 migration (single revision chained off baseline, data-preserved, tested on dev dump) → Task 5f steps 2–3 ✓; §6 testing strategy (pins green-first, red-first probes, no Python Range tests, one compose Range check) → Tasks 1/2/8/9 Step 5 ✓; §7 deferred → audio deferral only + the scheduled non-audio items are Part G ✓; §8 invariants → per-task lint/type gates + Task 10 Step 7's invariant-table update ✓; §9 React handoff (annex with topology/token/roles/media/error shape/location decisions) → Task 10 Step 1 ✓; **the former deferrals** → Part G Tasks 11–16, each red-first with a per-task commit, chained migrations (task5 → task11 → task13), additive-only schema/surface changes under the frozen contract ✓.

- **Placeholder scan:** no TBD/TODO. Contracts, case lists, and expected red errors are itemized; the four load-bearing blocks (migration, X-Accel endpoint shape, nginx.conf, compose) are full code. Learning-mode delegated bodies are the approved convention, not elision. The "old plan ... verbatim" references in Task 4 Sections B/C and Task 7 name the source tasks and carry their case counts; the source documents remain readable in git history until Task 10 deletes them.

- **Type consistency:** entity repos produce `get_by_name -> Entity | None` / `get_or_create_by_name -> Entity` (Task 3); Task 5 search consumes `get_by_name`, Task 5 writes consume `get_or_create_by_name` ✓. `BookRead` name fields via `validation_alias` = model `author_name`/`level_name`/`genre_name` properties, both halves in Task 5 ✓. `resolve_stream -> tuple[Path, str]` produced by Task 5 (`BookService`) and Task 8 (`VideoService`), consumed by their routers, both building `f"/media/{kind}/{quote(media_path.name)}"` with kinds `books`/`vids` matching the nginx `/media/` alias ✓. `MediaFileStorage(save_dir)` — Task 7 produces, Task 8 constructs `(settings.VIDEO_DIR)` ✓. `ALLOWED_VIDEO_EXTENSIONS` — Task 7 produces, Task 8 consumes ✓. Detail strings (`Video not found`, `File type .{ext} not allowed`) match Task 1's pinned strings and Task 8's flip asserts ✓. `TagRepo.get_or_create_by_names` — Task 6 produces, Task 8 consumes ✓. Task 1 pin numbering (15 cases) matches Task 8's flip references (cases 5, 8, 11, 12, 14, 15) ✓. Migration `down_revision = "70ee18aafdca"` — the only chain link, no audio revision ✓.

- **Known risks:** (1) Task 5 is the largest unit — mitigated by per-file gates 5b–5e, the fused-commit discipline, and the `/done` gate; (2) the backfill SQL is hand-written and data-touching — mitigated by the empty-DB round-trip **and** the preserved-data check on `jirani_bk` (5f steps 2–3), neither is skippable; (3) the auth addition on video/tag/book endpoints is behavior-breaking for token-less clients — deliberate, user-approved 2026-09-01; (4) Range behavior leaves pytest permanently — the Task 9 Step 5 curl is the standing mitigation, re-run it after any nginx.conf change; (5) a model change committed without its schema change breaks dev compose — only Task 5 changes schema and carries its migration in the same commit; Task 8's model conversion is zero-delta and needs none; (6) `get_or_create_by_names` must reproduce `ilike` semantics exactly or Task 1's tag-reuse pin (case 6) fails — that pin is the guard; (7) Task 1's cases 5/8/11/15 flip shape in Task 8 — a flip that breaks a different pin means the probe touched the wrong contract; re-read the pin list before "fixing" it; (8) the spec and this plan both carry uncommitted rev-2 edits at plan start — if the spec changes again, this plan follows; read it before starting each task; (9) Part G migrations must run in chain order (task5 → task11 → task13) and Task 11's **physical file move comes before its migration** — reversed order is a 404-on-every-video outage on dev; (10) Task 12's `delete_orphans` must be existence-based, never called from search/read paths — a mutation in a filter breaks the WHERE-false contract and the React search surface.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-01-media-refactor-nginx-entities.md` (rev 2 — audio out of scope). Two execution options:

1. **Learner mode (current convention)** — you implement each task from the contracts, samples, and hints; the agent reviews diffs and runs `/done` (audit + verify) before each commit, and never writes the implementation.
2. **Subagent-Driven** — dispatch a fresh subagent per task with two-stage review; each task brief must be self-contained (the Interfaces blocks above are the brief material).

Which approach?



