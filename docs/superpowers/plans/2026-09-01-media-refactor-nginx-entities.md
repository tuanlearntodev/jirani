# Media Refactor + nginx Streaming + Criteria Entities — Implementation Plan (2026-09-01, learner edition)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Learner mode (user-approved convention since 2026-08-24):** this plan carries the *contract* (signatures, case lists, expected red errors, gates) and *samples* of novel idioms — you write the implementation bodies yourself. Four load-bearing blocks are given in full because getting them wrong destroys data or breaks the deployment: the Alembic migration (Task 7), the X-Accel stream endpoint shape (Tasks 7/10/11), `nginx.conf` + `docker-compose.yml` (Task 12), and the entity repo lookup semantics (Task 4). TDD is binding (AGENTS.md): a step that says "write the failing test" must be red before you touch the implementation. Characterization pins (Part A) are the one deliberate exception — they assert *current* behavior and are witnessed green first.

**Goal:** Refactor books, audio, and video to the invariant shape in one pass — replacing all hand-rolled Python byte streaming with nginx X-Accel-Redirect, promoting `author`/`level`/`genre` to tag-like single-valued entities via one data-preserving Alembic migration, and renaming `book_type` → `genre` to kill the file-format conflation.

**Architecture:** One plan replaces two (`2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md` — deleted in Task 13). Part A pins the audio/video/tag legacy behavior; Parts B–F rebuild on top: entity modules (Author/Level/Genre) copied from the tag shape, book leaf modules + fused rewrite, tag/media fused rewrites, then the nginx service. Every media stream endpoint becomes an auth+containment check that emits `X-Accel-Redirect` — the router never opens a file (Invariant 3). Schema changes run through Alembic (hygiene S5) with full data backfill.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests, docker-compose for dev/prod), Alembic, nginx, uv, pytest/httpx, ruff, mypy.

**Governing spec:** `docs/superpowers/specs/2026-09-01-media-refactor-nginx-entities-design.md` (approved 2026-09-01). Read it first; where this plan and the spec disagree, the spec wins. The TDD process spec `2026-08-24-tdd-workflow-design.md` still governs execution order (pins green-first, fixes red-first).

## Global Constraints

Every task implicitly includes all of the following. Exact values copied from the spec(s).

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; no `docker compose up -d db` needed for tests. The harness (`backend/app/tests/conftest.py`) exposes `db`, `client`, `setup_paths`, and importable helpers `setup_admin`/`login`/`auth_headers`. `app.tests` is a package — never re-create its `__init__.py`
- One harness trap survives: **call `db.expire_all()` before reading via `db` after a write through `client`** — the long-lived session's identity map otherwise returns stale objects
- `ruff check` with `--ignore B008` on changed files; `mypy --strict` on changed files only, per the Debt Coverage Annex — touched files end at **0 ruff + 0 mypy**, and pre-existing errors in a touched file are that task's debt to clear. Log other plans' failures in STATE.md; do not fix unrelated files
- Characterization-first (TDD spec decision 2): Part A pins are **witnessed green on legacy code first**; every behavior *fix* gets a red-first probe that fails on legacy before implementation. Never delete a failing test to make the suite pass
- Commit after every task, **including the plan file tick in the same commit** (AGENTS.md); message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- **Locked decisions (user-approved 2026-09-01):** single-valued FK for author/level/genre (not M2M); genre on books only, author on books+audio, level on books, language stays a column; existing DB data must survive the migration (backfill); nginx fronts everything (only published port), backend unpublished; learner-edition format; delete the two old plans + `2026-08-16-book-refactor-design.md`
- **`uploads/vids` name stays** — the dir rename is deferral D1, not this plan
- After the final task, run `graphify update .` (AST-only)
- Work tree note: an unrelated local change to `.gitignore` (adds `docs/codebase-structure.txt`) is sitting uncommitted — leave it alone

## Corrections to the previous plans

The two replaced plans were audited against this spec. Statements that are no longer true:

| # | Previous claim | Replacement ruling |
|---|---|---|
| 1 | Book plan Task 0: rename the `file_type` search param to `book_type` and map it to `Book.book_type` | **Moot.** The column is dropped, not renamed — `genre_id` replaces it. The Task 0 hotfix and its test die with the column; Task 7's search probes are the new equivalents |
| 2 | Book plan Task 5c + media plan Task 7: implement RFC 7233 Range in Python (8-row grammar table each) | **Deleted.** nginx implements Range natively. All Python Range parsers and their test tables are out; the stream contract becomes "204 + `X-Accel-Redirect` + `Content-Type` + `Accept-Ranges: bytes`" |
| 3 | Media plan Global Constraint: "No schema changes in this plan. Models convert with identical columns — zero Alembic delta" | **Superseded.** This plan *does* change schema: three new tables, `books` FK conversion + `book_type` drop, `audio.author_id`. One hand-written migration (Task 7) carries it all |
| 4 | Media plan pinned `book_type` as derived-from-MIME ("™ Task 5b: not honored on create — derived from content_type/extension") | **Wrong per user 2026-09-01:** `book_type` is the *genre* (novel, sci-fi), not the file format. The format is `extension`. Genre is user-supplied, not derived |
| 5 | Media plan audio/video stream pins assert byte-for-byte bodies through `StreamingResponse` | **Flipped in Tasks 10/11:** pins change to 204 + redirect headers; byte assertions leave the suite (nginx's job — one compose integration check in Task 12 covers the bytes) |
| 6 | Media plan Global Constraint: "uncommitted auth changes in flight" | **Stale.** Auth/hygiene work landed (commits `97eba20`, `c7fcfb6`); working tree is clean except the unrelated `.gitignore` line |
| 7 | Book plan Task 5c deleted `/books/{uid}/epub` and `/read` (epub→pdf conversion) | **Still true** — carried into this plan (book router rewrites the same way) and preserved in the Deferred annex |

## Current State (verified against the tree, 2026-09-01)

| Area | State | Where |
|---|---|---|
| Audio endpoints | 🔴 6 endpoints, **zero auth**, inline DB + tag logic, CWD-relative literal at line 91 | `backend/app/api/audio_router.py` (177 lines) |
| Video endpoints | 🔴 6 endpoints, **zero auth**, inline DB + tag logic, **no extension validation** | `backend/app/api/video_router.py` (157 lines) |
| Tag endpoint | 🔴 `GET /tags/` only, zero auth, repo passthrough | `backend/app/api/tag_router.py:11-13` |
| Book module | 🔴 605-line `BookService` god class; `search_books` filters on nonexistent `Book.file_type` → 500; router has zero auth, no Range, no containment | `book_service.py`, `book_repo.py:122-123`, `book_router.py:47-189` |
| Streaming | 🔴 All hand-rolled: `audio_router.py:170-177` generator loop; 3 book endpoints; video same | three routers |
| Delete-missing 500s | 🔴 LIVE — `None.deleted_at` deref | `audio_repo.py:20-25`, `video_repo.py:22-27` |
| Models | 🔴 Audio/Video/AudioTag/VideoTag legacy 1.x `Column()`; Book already 2.0 with `book_type` column (MIME-junk values); Tag already 2.0 | `models/audio.py`, `video.py`, `audio_tag.py`, `video_tag.py`, `book.py:42`, `tag.py` |
| Repos | 🔴 legacy `query()` ×3; dead code: `AudioRepo.update_audio`, `TagRepo.get_tag_by_id/create_tag`, `Video_Delete` | repos, `video_schema.py:21-23` |
| Naming (Inv 6) | 🔴 `Audio_Repo`, `Video_Repo`, `Audio_Create`, `Audio_View`, `Video_Create`, `Video_View` | audio/video modules + schemas |
| Tests (Inv 5) | 🔴 zero for book/audio/video/tag — suite has only `test_auth.py` | `backend/app/tests/` |
| Whitelist constants | ✅ `ALLOWED_AUDIO = {"mp3","mp4","wav","ogg","m4a","aac","flac"}` | `audio_router.py:17` |
| Anchored dirs | ✅ `UPLOAD_DIR`/`COVER_DIR`/`AUDIO_DIR`/`VIDEO_DIR` BASE_DIR-anchored; mkdir at import | `config.py:40-43`, `main.py` |
| Alembic | ✅ baseline `70ee18aafdca` applied; dev DB stamped; compose entrypoint runs `upgrade head` | `backend/migrations/` |
| Harness | ✅ testcontainers postgres:16-alpine, session-scoped, `create_all` per test | `backend/conftest.py` |

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/tests/test_audio_repo.py`, `test_audio_api.py` | Create | 1 | Audio characterization pins (incl. bug pins) |
| `backend/app/tests/test_video_repo.py`, `test_video_api.py` | Create | 2 | Video characterization pins |
| `backend/app/tests/test_tag_repo.py`, `test_tag_api.py` | Create | 3 | Tag characterization pins |
| `backend/app/models/author.py`, `level.py`, `genre.py` | Create | 4 | Three entity models, mirror of `Tag` |
| `backend/app/schemas/author_schema.py`, `level_schema.py`, `genre_schema.py` | Create | 4 | `EntityCreate`/`EntityRead` |
| `backend/app/repositories/author_repo.py`, `level_repo.py`, `genre_repo.py` | Create | 4 | `get_or_create_by_name`, `get_by_name`, `list_all` |
| `backend/app/services/author_service.py`, `level_service.py`, `genre_service.py` | Create | 4 | Thin `list()` seam |
| `backend/app/api/author_router.py`, `level_router.py`, `genre_router.py` | Create | 4 | `GET /authors/`, `/levels/`, `/genres/` |
| `backend/app/tests/test_entity_repos.py`, `test_entity_api.py` | Create | 4 | Entity unit + API tests |
| `backend/app/models/audio.py`, `audio_tag.py`, `video.py`, `video_tag.py` | Modify | 5 | 2.0 `mapped_column()`; audio gains `author_id` |
| `backend/app/services/book_errors.py`, `content_validator.py` | Create | 6 | Book domain errors + upload gate |
| `backend/app/services/book_file_storage.py` | Create | 6 | bytes↔disk + `resolve()` containment |
| `backend/app/services/epub_metadata_reader.py` | Create | 6 | EPUB metadata leaf |
| `backend/app/services/cover_generator.py` | Create | 6 | Cover leaf, `-> bool`, never raises |
| `backend/app/tests/test_book_validator.py`, `test_book_storage.py`, `test_book_epub_reader.py`, `test_book_cover.py` | Create | 6 | Leaf unit tests |
| `backend/app/models/book.py` | Modify | 7 | Drop `book_type`; add `author_id`/`level_id`/`genre_id` FKs + relationships + `*_name` properties |
| `backend/app/schemas/book_schema.py` | Modify | 7 | `genre` replaces `book_type`; name resolution via `validation_alias`; `cover_url` → `BookRead` only |
| `backend/app/repositories/book_repo.py` | Rewrite | 7 | 2.0 `select()`; entity-filtered `search()` |
| `backend/app/services/book_service.py` | Rewrite | 7 | 605 → thin orchestration; entity name resolution on create/update |
| `backend/app/api/book_router.py` | Rewrite | 7 | RoleChecker everywhere, X-Accel stream, error mapping |
| `backend/migrations/versions/<hash>_authors_levels_genres.py` | Create | 7 | The data-preserving migration (full code below) |
| `backend/app/tests/test_book_search.py`, `test_book_stream.py`, `test_book_upload.py` | Create | 7 | Red-first probes |
| `backend/app/repositories/tag_repo.py` | Rewrite | 8 | 2.0 + `get_or_create_by_names`; dead methods deleted |
| `backend/app/services/tag_service.py` | Create | 8 | `list_tags()` |
| `backend/app/api/tag_router.py` | Rewrite | 8 | RoleChecker + service call |
| `backend/app/services/media_errors.py`, `media_validator.py` | Create | 9 | Media domain errors + extension whitelists |
| `backend/app/services/media_file_storage.py` | Create | 9 | `save` / `resolve` / `delete` with containment |
| `backend/app/tests/test_media_validator.py`, `test_media_storage.py` | Create | 9 | Leaf unit tests |
| `backend/app/repositories/audio_repo.py`, `services/audio_service.py`, `api/audio_router.py`, `schemas/audio_schema.py` | Rewrite | 10 | Audio fused rewrite — 2.0, auth, X-Accel, author link |
| `backend/app/repositories/video_repo.py`, `services/video_service.py`, `api/video_router.py`, `schemas/video_schema.py` | Rewrite | 11 | Video fused rewrite — mirror + whitelist + X-Accel |
| `backend/app/tests/test_media_stream.py` | Create | 10, 11 | X-Accel contract probes (audio + video) |
| `nginx/nginx.conf` | Create | 12 | The front proxy: `/api/`, `/static/covers/`, internal `/media/` |
| `docker-compose.yml` | Modify | 12 | Add nginx service; unpublish 8000 |
| `backend/app/main.py` | Modify | 12 | Remove `StaticFiles` covers mount |
| `docs/superpowers/plans/2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md`, `docs/superpowers/specs/2026-08-16-book-refactor-design.md` | **Delete** | 13 | Superseded by this plan + spec |
| `AGENTS.md`, `README.md`, `STATE.md` | Modify | 13 | Point at the new plan; document nginx workflow |

## Debt Coverage Annex (fresh-measured baseline, 2026-09-01)

Snapshot of the target files at plan start; every row is struck by a rewrite task. Callout rows belong to the hygiene plan's remaining debt — red on those files is expected, out of scope.

| File | ruff | mypy | Owning task |
|---|---|---|---|
| `app/api/audio_router.py` | 0 | 19 | 10 (rewrite) |
| `app/api/video_router.py` | 0 | 15 | 11 (rewrite) |
| `app/api/tag_router.py` | 0 | 1 | 8 (rewrite) |
| `app/api/book_router.py` | 3 | 22 | 7 (rewrite) |
| `app/services/book_service.py` | 15 | 17 | 7 (rewrite) |
| `app/repositories/book_repo.py` | 2 | 1 | 7 (rewrite) |
| `app/schemas/book_schema.py` | 0 | 2 | 7 (rewrite) |
| `app/models/book.py`, `book_tag.py` | 0 | 3 | 7 |
| `app/models/tag.py` | 0 | 1 | 8 (touch — clear or log) |
| `app/repositories/audio_repo.py` | 0 | 5 | 10 (rewrite) |
| `app/repositories/video_repo.py` | 0 | 2 | 11 (rewrite) |
| `app/repositories/tag_repo.py` | 0 | 2 | 8 (rewrite) |
| `app/models/audio.py`, `audio_tag.py`, `video.py`, `video_tag.py` | 0 | 4 | 5 (2.0 conversion) |
| `app/schemas/audio_schema.py`, `video_schema.py` | 0 | 0 | 10/11 renames keep them at 0 |

> Re-measure at plan start with `uv run mypy <files> --strict`; if a number moved, update the row — the "strike the row" gate is 0/0 per file, whatever the starting value.

# PART A — Characterization pins

Part A pins current behavior — including its bugs — per the TDD-workflow spec's decision 2. Every pin is **witnessed green against the legacy code**: that is what makes it a pin rather than a wish. Bugs are pinned as-broken (`pytest.raises(...)`) and flipped red-first in Parts D/E. Legacy has no auth: Part A requests carry **no headers**; Tasks 10–11 add `auth_headers` and the 401 guards. The single-upload path reads `settings.AUDIO_DIR` per call, so `monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)` works there; the literal-path bug site (`audio_router.py:91`) ignores the patch — pins touching `upload_multiple` assert DB rows, never the filesystem.

### Task 1: Audio characterization pins

**Files:**
- Create: `backend/app/tests/test_audio_repo.py`
- Create: `backend/app/tests/test_audio_api.py`

**Interfaces:**
- Consumes: legacy `Audio_Repo` (`create_audio`, `delete_audio`), `Audio` model, `Audio_Create`/`Audio_View` schemas, harness fixtures `db`, `client`, `monkeypatch`, `tmp_path`
- Produces: the pinned-behavior statement Tasks 10 must preserve — soft delete excludes from list but keeps the row; stream serves soft-deleted rows (quirk pin); DELETE returns 200 with `id`/`title`/`description`/`audio_url`/`tags` (the incidental `file_path`/`created_at`/`deleted_at` leak is **not** pinned); DELETE missing id raises `AttributeError` (bug pin); `upload_multiple` persists earlier files before a later failure (bug pin)

**Why (learning):** pins are written first because everything downstream is measured against them: the Task 10 rewrite runs the identical test files and must stay green except where a fix deliberately flips a pin. A pin that passes for the wrong reason teaches nothing — seed through the API where possible, assert both the response *and* the DB state.

Seeding idioms (samples — the bodies are yours):

```python
def _seed_audio(db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3") -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track
```

Auth is absent on legacy — requests carry no headers.

- [ ] **Step 1: Write `test_audio_repo.py`** — three cases:
  1. `create_audio` persists: row gets an id; `title`/`description`/`file_path` round-trip; `deleted_at` is `None`
  2. `delete_audio` soft-deletes: `deleted_at` set (compare `datetime.now(UTC)` within a small delta), row still present in DB
  3. `delete_audio` on a missing id **raises** — the bug pin: `with pytest.raises(AttributeError): Audio_Repo(db).delete_audio(999999)`

- [ ] **Step 2: Write `test_audio_api.py`** — case list (bodies yours):
  1. `GET /audio/` empty table → `200`, `[]`
  2. `GET /audio/` excludes a soft-deleted track (seed two, delete one via repo) — set assertion, no order
  3. `POST /audio/upload` happy: `files={"file": ("song.mp3", b"\xff\xfbID3 mock audio bytes", "audio/mpeg")}`, `data={"tags": "math, algebra"}` → `200`: `title == "song"` (filename stem), `audio_url == f"/audio/stream/{id}"`, `tags == [{"id", "name": "math"}, {"id", "name": "algebra"}]` in order; file bytes under `monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)` named `{uuid4}_{filename}`
  4. Upload with `tags=" math ,, MATH "` → single tag, stored **lowercase** `"math"`
  5. Existing mixed-case tag: pre-create `Tag(name="Math")`, upload `tags="MATH"` → the existing `"Math"` reused (case-insensitive), no second row
  6. `.txt` filename → `400` detail `File type .txt not allowed`, `tmp_path` contains **no** file
  7. Extensionless filename → `400`
  8. `POST /audio/upload_multiple` (two files, second `.txt`, no tags param) → `400`; then `GET /audio/` returns exactly **one** track — the partial-commit bug pin (DB side effect only, no filesystem assert)
  9. `POST /audio/upload_multiple` (two valid) → `200` list of two, title = filename stem
  10. `PATCH /audio/{id}` `title`/`description`/`tags="bass"` → `200`; tag set **replaced**; old `Tag` rows survive in DB
  11. `PATCH` `tags=""` → cleared; `tags` omitted → untouched
  12. `PATCH /audio/999999` → `404` detail `Audio not found`
  13. `DELETE /audio/{id}` → `200` with pinned keys; excluded from list after; row kept with `deleted_at`
  14. `DELETE /audio/999999` → bug pin: `with pytest.raises(AttributeError): client.delete("/audio/999999")` — the harness's `raise_server_exceptions=True` surfaces the deref. **Flip target for Task 10**
  15. `GET /audio/stream/{id}` (seed real file at `tmp_path`) → `200`, `Content-Type: audio/mpeg`, body byte-for-byte
  16. `GET /audio/stream/999999` → `404` detail `Audio not found`
  17. Stream of a **soft-deleted** track → `200` (quirk pin — kept through Task 10)
  18. Stream whose file is missing on disk → bug pin: `with pytest.raises(FileNotFoundError)` — **flip target for Task 10**

- [ ] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py -v`. Expected: all pass (~21 tests). If a pin fails, fix the **pin** to match verified behavior and record the deviation at the bottom of this task; do not fix legacy code here.

- [ ] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/test_audio_repo.py app/tests/test_audio_api.py && uv run ruff check app/tests/test_audio_repo.py app/tests/test_audio_api.py --ignore B008
git add backend/app/tests/test_audio_repo.py backend/app/tests/test_audio_api.py
git commit -m "test: pin audio module behavior — list, upload, patch, delete, stream"
```

---

### Task 2: Video characterization pins

**Files:**
- Create: `backend/app/tests/test_video_repo.py`
- Create: `backend/app/tests/test_video_api.py`

**Interfaces:**
- Consumes: legacy `Video_Repo` (`create_video`, `delete_video`), `Video` model, `Video_Create`/`Video_View` schemas
- Produces: the video pinned-behavior statement, mirroring Task 1 with four deliberate deltas: upload takes `title` **(required Form)** + optional `description`/`tags`; **no extension validation exists** (pinned as-is; Task 11 flips); content type from `mimetypes.guess_type(file_path)` with `application/octet-stream` fallback; unknown stream extensions resolve via `guess_type` (`.mp4` → `video/mp4`)

- [ ] **Step 1: Write `test_video_repo.py`** — mirror Task 1 Step 1: create persists, delete soft-deletes, delete-missing raises `AttributeError` (bug pin).

- [ ] **Step 2: Write `test_video_api.py`** — mirror Task 1 Step 2 with the deltas:
  1. `GET /videos/` empty → `200 []`; excludes soft-deleted
  2. Upload happy: `files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42 mock bytes", "video/mp4")}`, form `title="Intro"`, `description="first"`, `tags="lesson"` → `200`: `title == "Intro"` (form wins), `video_url == f"/videos/stream/{id}"`, tag linked; file under `monkeypatch.setattr(settings, "VIDEO_DIR", tmp_path)`
  3. Missing `title` → `422`
  4. `.txt` filename → **`200`** — the quirk pin (no validation exists). Comment: Task 11 flips to `400`
  5. `tags=" MATH , math "` → single tag, first-seen case reused when a pre-existing row exists
  6. `upload_multiple` valid pair → `200` list of two, title = filename stem
  7. `upload_multiple` with a `.txt` second file → **still `200` and both rows commit** today (no validation = no failure). Task 11's probe flips this
  8. `PATCH` title/description/tags replace; `tags=""` clears; omitted leaves; old `Tag` rows survive; missing id → `404` detail `Video not found`
  9. `DELETE /videos/{id}` → `200` pinned keys; excluded after; row kept
  10. `DELETE /videos/999999` → bug pin: `with pytest.raises(AttributeError)`
  11. `GET /videos/stream/{id}` → `200`, `Content-Type: video/mp4`, byte-for-byte
  12. `GET /videos/stream/999999` → `404` detail `Video not found`
  13. Stream soft-deleted → `200` (quirk pin)
  14. Missing file on disk → bug pin: `with pytest.raises(FileNotFoundError)`

- [ ] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/test_video_repo.py app/tests/test_video_api.py -v`. Expected: all pass.

- [ ] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/test_video_repo.py app/tests/test_video_api.py && uv run ruff check app/tests/test_video_repo.py app/tests/test_video_api.py --ignore B008
git add backend/app/tests/test_video_repo.py backend/app/tests/test_video_api.py
git commit -m "test: pin video module behavior — list, upload, patch, delete, stream"
```

---

### Task 3: Tag characterization pins

**Files:**
- Create: `backend/app/tests/test_tag_repo.py`
- Create: `backend/app/tests/test_tag_api.py`

**Interfaces:**
- Produces: the pinned statement Task 8 preserves — `GET /tags/` is an unordered list of `{id, name}`; `get_tag_by_id` returns `None` on a missing id (legacy `.first()`); `create_tag` applies the `TagCreate` validator (whitespace collapse, charset, length). `get_tag_by_id` and `create_tag` are dead in the app today (only `tag_router → get_all_tags` calls `TagRepo`) — their pins become their deletion's justification

- [ ] **Step 1: Write `test_tag_repo.py`:**
  1. `get_all_tags` returns seeded rows (three) — set of names
  2. `get_tag_by_id(seeded)` → row with `name`; `get_tag_by_id(999999)` → `None`
  3. `create_tag(TagCreate(name="  Math  "))` → stored `"Math"`; re-run with `"Math"` → unique-constraint `IntegrityError` (DB is the guarantee; `ilike` matching is UX)

- [ ] **Step 2: Write `test_tag_api.py`:**
  1. `GET /tags/` empty → `200 []`
  2. `GET /tags/` with three seeded → `200`, set of `{id, name}`

- [ ] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/test_tag_repo.py app/tests/test_tag_api.py -v`. Expected: all pass.

- [ ] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/test_tag_repo.py app/tests/test_tag_api.py && uv run ruff check app/tests/test_tag_repo.py app/tests/test_tag_api.py --ignore B008
git add backend/app/tests/test_tag_repo.py backend/app/tests/test_tag_api.py
git commit -m "test: pin tag module behavior — list, lookup, create normalization"
```

# PART B — Entities + schema models

### Task 4: Entity modules — Author, Level, Genre (identical shape ×3)

> **Lint/type gate:** new files ship clean (0/0).

**Files:**
- Create: `backend/app/models/author.py`, `level.py`, `genre.py`
- Create: `backend/app/schemas/author_schema.py`, `level_schema.py`, `genre_schema.py`
- Create: `backend/app/repositories/author_repo.py`, `level_repo.py`, `genre_repo.py`
- Create: `backend/app/services/author_service.py`, `level_service.py`, `genre_service.py`
- Create: `backend/app/api/author_router.py`, `level_router.py`, `genre_router.py`
- Test: `backend/app/tests/test_entity_repos.py`, `backend/app/tests/test_entity_api.py`

**Interfaces:**

*Model* (use `Author` as the template — `Level`/`Genre` are renames):

```python
class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
```

Table names: `authors`, `levels`, `genres`. No relationships yet — `Book.author`/`Audio.author` relationships are added when those models gain their FK columns (Tasks 5/7) and use `back_populates` then. Export all three from `models/__init__.py`.

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
        # Search filter semantics (Task 7): None -> WHERE false, never a create.
        return self.db.execute(
            select(Author).where(func.lower(Author.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Author:
        # Write path (Tasks 7/10). Reuse by case-insensitive match with STORED case;
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

**Why (learning):** three carbon-copy modules are the point, not the waste — each is *one* drill of the pattern `Tag` establishes, and `get_by_name`/`get_or_create_by_name` are the semantics Tasks 7 and 10 stand on. The search/write split matters: search must never create rows (searching for a nonexistent author returns zero books), writes may. `func.lower(Entity.name) == name` reproduces `ilike`'s case-insensitive match in 2.0 idiom so nothing stores `NULL` or a typo case.

- [ ] **Step 1: Write the failing tests**

`test_entity_repos.py` — parametrize over the three `(RepoClass, ModelClass)` pairs; cases:
1. `get_by_name("MATH")` after creating `Model(name="Math")` → returns the row (stored case `"Math"`); `get_by_name("missing")` → `None`
2. `get_or_create_by_name("  MATH ")` with existing `"Math"` → same row, no second insert (count == 1)
3. `get_or_create_by_name("Algebra")` fresh → creates row stored `"algebra"`, returns it
4. `list_all()` → sorted by name

`test_entity_api.py` — per prefix (`/authors/`, `/levels/`, `/genres/`); use `setup_admin(client, setup_paths)` + `login` + `auth_headers` (idiom from `test_auth.py`):
1. Authed `GET` → `200`, list of `{id, name}` (seed 2 rows per entity)
2. Unauthenticated `GET` → `401`

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/test_entity_repos.py app/tests/test_entity_api.py -v`. Expected: collection ERROR `ModuleNotFoundError: No module named 'app.models.author'`.

- [ ] **Step 3: Implement all fifteen files** per the Interfaces. The three routers join `api/__init__.py`, the repos join `repositories/__init__.py` (`__all__`), and `main.py` includes the routers.

- [ ] **Step 4: Verify green** — `cd backend && uv run pytest app/tests/test_entity_repos.py app/tests/test_entity_api.py -v`. Expected: all pass.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/models/__init__.py app/repositories/__init__.py app/api/__init__.py app/main.py app/tests/test_entity_repos.py app/tests/test_entity_api.py && uv run ruff check app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/models/__init__.py app/repositories/__init__.py app/api/__init__.py app/main.py app/tests/test_entity_repos.py app/tests/test_entity_api.py --ignore B008 && uv run mypy app/models/author.py app/models/level.py app/models/genre.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py --strict
```

Expected: 0/0 on all new files.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/author.py backend/app/models/level.py backend/app/models/genre.py backend/app/models/__init__.py backend/app/schemas/author_schema.py backend/app/schemas/level_schema.py backend/app/schemas/genre_schema.py backend/app/repositories/author_repo.py backend/app/repositories/level_repo.py backend/app/repositories/genre_repo.py backend/app/repositories/__init__.py backend/app/services/author_service.py backend/app/services/level_service.py backend/app/services/genre_service.py backend/app/api/author_router.py backend/app/api/level_router.py backend/app/api/genre_router.py backend/app/api/__init__.py backend/app/main.py backend/app/tests/test_entity_repos.py backend/app/tests/test_entity_api.py
git commit -m "feat: author/level/genre entities — tag-pattern modules with get_or_create_by_name"
```

---

### Task 5: Audio/Video models → 2.0 + `audio.author_id`

> **Lint/type gate:** 0 mypy errors on the four model files (Annex rows struck).

**Files:**
- Modify: `backend/app/models/audio.py`, `audio_tag.py`, `video.py`, `video_tag.py`

**Interfaces:**
- `Audio`/`Video` convert to 2.0 `Mapped[]`/`mapped_column()` with **identical columns** plus one addition: `Audio` gains `author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id", ondelete="SET NULL"), nullable=True)` and `author: Mapped[Author | None] = relationship(back_populates="audio_tracks")`. `Author` gains the reciprocal `audio_tracks: Mapped[list[Audio]] = relationship(back_populates="author")` (add to `author.py`)
- Table names unchanged: `"audio"`, `"video"` (matches the existing DB — do not "fix" the singular)
- `AudioTag`/`VideoTag`: 2.0, `UniqueConstraint("audio_id", "tag_id")` / video equivalent, `ondelete="CASCADE"` FKs

**Why (learning):** pure syntax conversion + one nullable FK is behavior-neutral — the Part A pins must stay green against the converted models, which is what makes this a safe standalone task instead of being fused into Task 10. The dev DB lacks `author_id` until Task 7's migration lands, but nothing queries it until Task 10, so both harness (`create_all`) and dev compose stay healthy in between.

- [ ] **Step 1: Convert the models** per the Interfaces. `models/__init__.py` already exports all four — no edit needed.

- [ ] **Step 2: Verify pins stay green** — `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_video_repo.py -v`. Expected: both files still pass (columns identical, behavior untouched).

- [ ] **Step 3: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/models/audio.py app/models/audio_tag.py app/models/video.py app/models/video_tag.py app/models/author.py && uv run ruff check app/models/audio.py app/models/audio_tag.py app/models/video.py app/models/video_tag.py app/models/author.py --ignore B008 && uv run mypy app/models/audio.py app/models/audio_tag.py app/models/video.py app/models/video_tag.py app/models/author.py --strict
```

Expected: 0/0.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/audio.py backend/app/models/audio_tag.py backend/app/models/video.py backend/app/models/video_tag.py backend/app/models/author.py
git commit -m "refactor: SQLAlchemy 2.0 models for audio/video + audio author FK"
```

# PART C — Book refactor

### Task 6: Book leaf modules (four sections, commit per section)

> **Lint/type gate:** each section ships clean (0/0). The old book plan's Tasks 1–4 folded into one task; boundaries unchanged, each section green independently.

**Why (learning):** leaf-first, exactly as the old plan: nothing imports them yet, the tree stays green after every section, and a regression in Task 7 isolates to *wiring* rather than to a leaf. Contracts below are the old plan's verbatim; the only change is import form (`from app.config import settings`).

- [ ] **Section A — `book_errors.py` + `ContentValidator`**
  - Files: create `backend/app/services/book_errors.py`, `content_validator.py`; test `backend/app/tests/test_book_validator.py`
  - Interfaces: `BookError(Exception)` with `detail: str` defaulting from per-class `default_detail`; `BookNotFound`, `InvalidBookFile`, `BookAlreadyExists`, `CoverGenerationFailed`; `ContentValidator.validate(file_bytes: bytes, filename: str) -> str` returns lowercase extension, raises `InvalidBookFile` on empty bytes, oversized (>`settings.MAX_UPLOAD_SIZE`), disallowed extension (`settings.ALLOWED_EXTENSIONS`), or magic-byte mismatch (pdf: `b"%PDF-"`, epub: `b"PK\x03\x04"`)
  - Tests (bodies yours — old plan Task 1 case list): empty→raise; `.exe`→raise; `b"not a real pdf"` named `.pdf`→raise; oversize via `monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)`→raise; `b"%PDF-1.4..."` named `Report.PDF`→`"pdf"`; `b"PK\x03\x04..."`→`"epub"`. Red = `ModuleNotFoundError: app.services.book_errors`
  - Commit: `feat: add book domain errors and ContentValidator upload gate`

- [ ] **Section B — `BookFileStorage`**
  - Files: create `backend/app/services/book_file_storage.py`; test `backend/app/tests/test_book_storage.py`
  - Interfaces: `save(file_bytes, filename, uid) -> str` (relative single-component name under `UPLOAD_DIR`); `delete(rel_path) -> None`; `delete_cover(cover_name) -> None`; `resolve(rel_path) -> Path` raising `BookNotFound` on traversal (`is_relative_to` containment) or missing file; `cover_dir -> Path` property
  - Tests: 7 cases per old plan Task 2 (traversal raise, round-trip, hostile filename sanitization, silent deletes, cover_dir)
  - Commit: `feat: add BookFileStorage with UPLOAD_DIR traversal containment`

- [ ] **Section C — `EpubMetadataReader`**
  - Files: create `backend/app/services/epub_metadata_reader.py`; test `backend/app/tests/test_book_epub_reader.py`
  - Interfaces: `@dataclass(frozen=True) BookMetadata` — `title: str | None`, `author: str | None`, `language: str | None`, `tags: list[str]` (field named **`tags`**, not `subjects`); `EpubMetadataReader.read(path: Path) -> BookMetadata | None`, never raises. Import `pymupdf` (not `fitz` — mypy `--strict`), `# type: ignore[no-untyped-call]` at `pymupdf.open`
  - Tests: 3 cases (corrupt→None, missing→None, minimal EPUB fixture→title/author)
  - Commit: `feat: add EpubMetadataReader leaf module with EPUB metadata tests`

- [ ] **Section D — `CoverGenerator`**
  - Files: create `backend/app/services/cover_generator.py`; test `backend/app/tests/test_book_cover.py`
  - Interfaces: `generate(source_path: Path, dest_dir: Path) -> bool` — dest is a **directory**, name is `{source_path.stem}.png`; PDF → page-0 render; EPUB → OPF-declared cover → XHTML `<img>` → first-image fallback; `False` on any failure, never raises; size-check against `settings.MAX_COVER_SIZE`
  - Tests: 5 cases (corrupt PDF→False; real PDF→True + file ≤ MAX; EPUB-with-cover→True; EPUB-no-images→False; MAX_COVER_SIZE=1 monkeypatch→False)
  - Commit: `feat: add CoverGenerator leaf module with cover generation tests`

- [ ] **Section E: Full-suite smoke after all four sections** — `cd backend && uv run pytest -v`. Expected: everything green (`test_auth.py` + all new files).

- [ ] **Section F: Tick this task's box in the same commit** (if the plan file is committed with Section D, no separate commit needed — see Global Constraints).

---

### Task 7: FUSED book rewrite + the data-preserving migration (single commit)

> **Lint/type gate — the big one:** `book_service.py` (15/17), `book_router.py` (3/22), `book_repo.py` (2/1), `book_schema.py` (0/2), `models/book.py` (0/3) reach 0/0 by the final step.

**Files:**
- Modify: `backend/app/models/book.py`
- Modify: `backend/app/schemas/book_schema.py`
- Rewrite: `backend/app/repositories/book_repo.py`
- Rewrite: `backend/app/services/book_service.py`
- Rewrite: `backend/app/api/book_router.py`
- Create: `backend/migrations/versions/<hash>_authors_levels_genres.py`
- Test: `backend/app/tests/test_book_search.py`, `test_book_stream.py`, `test_book_upload.py` (Create)

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
- **The X-Accel stream endpoint — full code, this shape is the contract for Tasks 10/11 too:**

```python
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
            "X-Accel-Redirect": f"/media/books/{media_path.name}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )
```

`BookService.resolve_stream(book_uid) -> tuple[Path, str]` — book missing → `BookNotFound`; `storage.resolve()` (containment + existence) → `BookNotFound`; media type from `MEDIA_TYPES = {"pdf": "application/pdf", "epub": "application/epub+zip"}` keyed by extension. Error mapping: `InvalidBookFile`→400, `BookAlreadyExists`→409, `BookNotFound`→404, `IntegrityError`→400, `ValueError`→400.

`. . .` — **the migration (full code — data-touching, no learner delegation).** Create `backend/migrations/versions/<hash>_authors_levels_genres.py` **by hand** (NOT autogenerate — autogenerate cannot do backfill). `revision = None, down_revision = "70ee18aafdca"`:

```python
"""authors/levels/genres entities: books FK conversion, drop book_type, audio author

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
    op.add_column("audio", sa.Column("author_id", sa.Integer(), nullable=True))

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
    op.create_foreign_key("fk_audio_author_id_authors", "audio", "authors", ["author_id"], ["id"], ondelete="SET NULL")


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
    op.drop_constraint("fk_audio_author_id_authors", "audio", type_="foreignkey")
    op.drop_column("books", "author_id")
    op.drop_column("books", "level_id")
    op.drop_column("books", "genre_id")
    op.drop_column("audio", "author_id")
    op.drop_table("genres")
    op.drop_table("levels")
    op.drop_table("authors")
```

Note: `audio.author_id` (model-side since Task 5) gets its `add_column` in this same revision — the `op.add_column("audio", ...)` line above runs before the FK line, and `downgrade()` drops the FK first, then the column (already ordered correctly). Additionally: `sa.Column("name", ..., unique=True, index=True)` on the three entity tables is enough for the tasks that follow (no GIN/functional indexes needed — `get_by_name`'s `lower(name)` scan is fine at school-library cardinality; add `func.lower` indexes later if measurements demand — do NOT expand scope now).

**Why (learning):** one commit for the whole module plus its migration, for the old plan's fused-rewrite reason — split commits would leave `GET /books/search/` raising `AttributeError` at call time. The migration is in the *same* commit because the code and its schema are one unit: any checkout between the book rewrite and a later migration commit would have dev compose running new code against an old DB (no `genre_id` → `UndefinedColumn` at runtime). The compose entrypoint runs `alembic upgrade head` before uvicorn, so the same-commit migration is what keeps `git pull && cat STATE.md` resumable.

- [ ] **Step 7a-i: Write the failing tests**

**`test_book_search.py`** — repo-level probes, red against legacy `BookRepo` (`search` doesn't exist → `AttributeError`):
1. `test_search_genre_filter_and_entities` — seed `Author(name="Ada")`, `Genre(name="scifi")`, two books linked via `book.genre = g`; `search(BookSearchCriteria(genre="SCIFI"), limit=10, offset=0)` → only the scifi book, `total == 1`; the response's `genre == "scifi"`
2. `test_search_unknown_author_matches_nothing` — `search(BookSearchCriteria(author="nobody"))` → `total == 0` (the `WHERE false` contract)
3. `test_search_tags_or_semantics_and_honest_total` — old plan 5a probe 1 verbatim
4. `test_search_metadata_containment` — old plan 5a probe 2 verbatim
5. `test_search_pagination_pages_are_disjoint_and_complete` — old plan 5a probe 3 verbatim

**`test_book_stream.py`** — the X-Accel contract (seeded book whose file exists under a monkeypatched `UPLOAD_DIR`; auth via `auth_headers`):
1. `GET /books/{uid}/stream` authed → **204**, headers `X-Accel-Redirect == f"/media/books/{uid}.pdf"`, `Content-Type: application/pdf`, `Accept-Ranges: bytes`; **body empty**
2. Missing book → 404
3. Poisoned row (`file_path == "../../../../etc/passwd"`) → 404 (containment — C4)
4. Row whose file is missing on disk → 404
5. Unauthenticated → 401
6. EPUB book → `Content-Type: application/epub+zip`

**`test_book_upload.py`** — old plan 5a-i list verbatim (real PDF happy path, bad-magic 400 with nothing on disk, auth required), plus: upload with form `genre="Sci-Fi"` → 200 and `("genre_id" linked)`: `db.expire_all()`, book row's `genre.name == "sci-fi"`; upload with `author="Ada Lovelace"` → `authors` row stored `"ada lovelace"`.

- [ ] **Step 7a-ii: Verify they fail** — `cd backend && uv run pytest app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py -v`. Expected red: `AttributeError: 'BookRepo' object has no attribute 'search'`; stream tests 404-route-missing or 200-stream (either is fine — the point is red); upload probes fail (no genre resolution). Everything else (pins, auth, leaves) green.

- [ ] **Step 7b: Model + schemas** per Interfaces. Gate: `cd backend && uv run mypy app/models/book.py app/schemas/book_schema.py --strict` → 0. Run `uv run pytest -v` — expect ONLY the three probe files red; all other files green.

- [ ] **Step 7c: Repo** per Interfaces. Gate: `cd backend && uv run mypy app/repositories/book_repo.py --strict && uv run pytest app/tests/test_book_search.py -v` → 0 mypy + search probes green.

- [ ] **Step 7d: Service** per Interfaces. Gate: `cd backend && uv run mypy app/services/book_service.py --strict` + `grep -n "HTTPException\|fitz\|open(" app/services/book_service.py` prints nothing.

- [ ] **Step 7e: Router** per Interfaces. Gate: `cd backend && uv run pytest -v` → all green.

- [ ] **Step 7f: Write the migration** (full code above) and verify it:
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

- [ ] **Step 7g: Full suite + lint + type**

```bash
cd backend && uv run ruff format app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py && uv run ruff check app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py app/tests/test_book_search.py app/tests/test_book_stream.py app/tests/test_book_upload.py --ignore B008 && uv run mypy app/models/book.py app/schemas/book_schema.py app/repositories/book_repo.py app/services/book_service.py app/api/book_router.py --strict && uv run pytest -v
```

Expected: 0/0 on all six; full suite green (auth + pins + leaves + entities + the three book probe files).

- [ ] **Step 7h: `/audit` then commit** — dispatch the `invariant-auditor` on the diff (this task exceeds the ~50-line review threshold; the migration SQL especially). On PASS:

```bash
git add backend/app/models/book.py backend/app/models/author.py backend/app/models/level.py backend/app/models/genre.py backend/app/schemas/book_schema.py backend/app/repositories/book_repo.py backend/app/services/book_service.py backend/app/api/book_router.py backend/migrations backend/app/tests/test_book_search.py backend/app/tests/test_book_stream.py backend/app/tests/test_book_upload.py
git commit -m "refactor: book model on author/level/genre FKs, X-Accel stream, thin service; migration with data backfill"
```

---

# PART D — Tag + media leaves + fused rewrites

### Task 8: Tag fused rewrite — 2.0 repo + service + router auth

> **Lint/type gate:** `tag_repo.py` (0/2), `tag_router.py` (0/1), `models/tag.py` (0/1) end at 0/0.

**Files:**
- Rewrite: `backend/app/repositories/tag_repo.py`
- Create: `backend/app/services/tag_service.py`
- Rewrite: `backend/app/api/tag_router.py`
- Test: `backend/app/tests/test_tag_repo.py`, `test_tag_api.py` (Modify)

**Interfaces:**
- `TagRepo.get_all_tags() -> list[Tag]` — 2.0 `select(Tag)`
- `TagRepo.get_or_create_by_names(names: list[str]) -> list[Tag]` — legacy semantics exactly, in one query plus inserts: case-insensitive match reuses **stored case**; missing names created **lowercased**; duplicates collapse; first-occurrence order. Match query: `select(Tag).where(func.lower(Tag.name).in_({n.strip().lower() for n in names}))`, then insert the misses. The old per-name `Tag.name.ilike(...)` loop in the routers dies here — do not keep two implementations
- `get_tag_by_id` + `create_tag` **deleted** (dead — Task 3 pins justify). Their pin cases updated: `get_tag_by_id` cases removed, `create_tag` normalization case becomes a deleted pin (record in commit message)
- `TagService(db: Session)` with `list_tags() -> list[TagRead]`
- Router: `GET /tags/` keeps prefix + response model; gains `Depends(RoleChecker([admin, teacher, student]))`; calls the service; holds **no** queries

- [ ] **Step 1: Update Part A pins + never-test red**
  - `test_tag_api.py`: wrap every `get("/tags/")` in `headers=auth_headers(token)`; add unauthenticated → `401` probe
  - `test_tag_repo.py`: delete the `get_tag_by_id` cases and the unique-constraint case (dead-method pins)
  - Run: `cd backend && uv run pytest app/tests/test_tag_api.py -v`. Expected: the 401 probe **fails** (legacy returns 200 — red for the right reason); the 200 cases now 401 too (they lack headers until Step 4's rewrite — acceptable, same red)

- [ ] **Step 2: Implement** — repo, service, router per Interfaces.

- [ ] **Step 3: Verify green** — `cd backend && uv run pytest app/tests/test_tag_repo.py app/tests/test_tag_api.py -v`. Expected: all pass including 401.

- [ ] **Step 4: Format, lint, type**

```bash
cd backend && uv run ruff format app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/test_tag_repo.py app/tests/test_tag_api.py && uv run ruff check app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/test_tag_repo.py app/tests/test_tag_api.py --ignore B008 && uv run mypy app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/models/tag.py --strict
```

Expected: 0/0 (Annex tag rows struck).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/tag_repo.py backend/app/services/tag_service.py backend/app/api/tag_router.py backend/app/models/tag.py backend/app/tests/test_tag_repo.py backend/app/tests/test_tag_api.py
git commit -m "refactor: tag module — 2.0 repo, service layer, auth; drop dead get_tag_by_id/create_tag"
```

---

### Task 9: Media leaf modules — `media_errors.py`, `media_validator.py`, `MediaFileStorage`

> **Lint/type gate:** new files ship clean (0/0).

**Files:**
- Create: `backend/app/services/media_errors.py`, `media_validator.py`
- Create: `backend/app/services/media_file_storage.py`
- Test: `backend/app/tests/test_media_validator.py`, `test_media_storage.py` (Create)

**Interfaces** — verbatim from the old media plan Tasks 4–5:
- `MediaError(Exception)` — `__init__(detail: str | None = None)`, attribute `detail` falling back to class `default_detail`; `MediaNotFound` (`"Media not found"`), `InvalidMediaFile` (`"Invalid media file"`); no HTTP types
- `ALLOWED_AUDIO_EXTENSIONS: frozenset[str]` = `{"mp3","mp4","wav","ogg","m4a","aac","flac"}` (verbatim `audio_router.py:17`); `ALLOWED_VIDEO_EXTENSIONS` = `{"mp4","mov","avi","mkv","webm","m4v","ogv","wmv"}`
- `validate_media(filename: str, *, allowed: frozenset[str]) -> str` — lowercase extension; `InvalidMediaFile(f"File type .{ext} not allowed")` on disallowed (verbatim legacy detail so Task 1 pin 6 survives the move). The whitelists live in the validator, not `config.py` (domain knowledge, not deployment settings — deliberate deviation from the book's `ContentValidator`, recorded so nobody "fixes" it)
- `MediaFileStorage(save_dir: Path)` — `save(file_bytes: bytes, filename: str) -> str` (`mkdir(parents=True, exist_ok=True)`, `{uuid4}_{filename}`, returns the **absolute** path string); `resolve(path: str) -> Path` raising `MediaNotFound` on (a) traversal — `is_relative_to` containment — or (b) `is_file()` false; relative stored paths join to `save_dir` (covers legacy rows holding `"uploads/audio/..."`); `delete(path: str) -> None` (resolve + `unlink(missing_ok=True)`)

- [ ] **Step 1: Write failing tests** — old media plan Task 4's six validator cases + Task 5's nine storage cases (traversal, round-trip, nested names, legacy relative form, missing file, silent delete).

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/test_media_validator.py app/tests/test_media_storage.py -v`. Expected: `ModuleNotFoundError: app.services.media_validator`.

- [ ] **Step 3: Implement** per Interfaces.

- [ ] **Step 4: Verify green** — same command. Expected: all pass.

- [ ] **Step 5: Format, lint, type**

```bash
cd backend && uv run ruff format app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/tests/test_media_validator.py app/tests/test_media_storage.py && uv run ruff check app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/tests/test_media_validator.py app/tests/test_media_storage.py --ignore B008 && uv run mypy app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py --strict
```

Expected: 0/0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/media_errors.py backend/app/services/media_validator.py backend/app/services/media_file_storage.py backend/app/tests/test_media_validator.py backend/app/tests/test_media_storage.py
git commit -m "feat: media domain errors, extension validator, MediaFileStorage"
```

---

### Task 10: Audio fused rewrite — 2.0, service layer, auth, author link, X-Accel

> **Lint/type gate:** `audio_router.py` (0/19), `audio_repo.py` (0/5), `models/audio.py`+`audio_tag.py` (0/0 since Task 5) end at 0/0.

**Files:**
- Rewrite: `backend/app/repositories/audio_repo.py`
- Create: `backend/app/services/audio_service.py`
- Rewrite: `backend/app/api/audio_router.py`
- Modify: `backend/app/schemas/audio_schema.py` (renames)
- Test: `backend/app/tests/test_media_stream.py` (Create), `test_audio_repo.py`, `test_audio_api.py` (Modify)

**Interfaces:**
- Schemas: `AudioCreate` (rename of `Audio_Create`), `AudioView` (`id, title, description, audio_url, tags` — intentional view contract, no `file_path` leak)
- `AudioRepo` — 2.0 `select()`: `create(audio_create) -> Audio`, `get_by_id(id) -> Audio | None` (`selectinload(Audio.tags)`), `list_active() -> list[Audio]` (no ORDER BY — pinned), `soft_delete(id) -> Audio | None` (`deleted_at` set; `None` when missing — missing is a return value). `update_audio` **deleted** (dead)
- `AudioService(db)` — `list_tracks()`, `upload(file_bytes, filename, tag_names, author: str | None) -> AudioView` (validate → `MediaFileStorage(settings.AUDIO_DIR).save` → create with title=stem → `TagRepo.get_or_create_by_names` → **author resolution: `AuthorRepo(db).get_or_create_by_name(author).id` when non-None** → link), `upload_multiple(files) -> list[AudioView]` (validate-all-first, one commit — the partial-commit fix), `update(id, *, title, description, tag_names, author) -> AudioView` (tri-state tags: None=leave, []... clear, list=replace), `soft_delete(id) -> AudioView` (missing → `MediaNotFound("Audio not found")`), `resolve_stream(id) -> tuple[Path, str]` (row missing → `MediaNotFound("Audio not found")`; `storage.resolve` → containment/missing → `MediaNotFound`; media type from the legacy extension map with `audio/mpeg` default; **does not filter `deleted_at`** — pin 17's quirk preserved)
- Router — prefix `/audio`: `RoleChecker([admin, teacher, student])` on **every** endpoint; `POST /upload` (multipart file + `tags` + **new optional form field `author`**), `POST /upload_multiple`, `PATCH /{id}` (form `title`/`description`/`tags`/`author`), `DELETE /{id}`, `GET /stream/{id}` → **the Task 7 X-Accel shape, `kind="audio"`**:

```python
return Response(status_code=204, headers={
    "X-Accel-Redirect": f"/media/audio/{media_path.name}",
    "Content-Type": media_type,
    "Accept-Ranges": "bytes",
})
```

  The router holds no queries, no `open()`, no tag logic. Mapping: `InvalidMediaFile`/`IntegrityError`→400, `MediaNotFound`→404.

- [ ] **Step 1: Update Part A pins + write red-first probes**

**Modify `test_audio_api.py`:**
1. `auth_headers(token)` on every request + parametrized 401 guard (all six paths: `/`, `/upload`, `/upload_multiple`, `/patch`, `/delete`, `/stream`)
2. Flip bug pins (red on legacy): case 14 delete-missing → waits 404 (legacy raises `AttributeError`); case 8 partial-commit → after failing batch, `GET /audio/` yields **zero** rows and zero files under patched `AUDIO_DIR`; case 18 missing-file stream → 404 (legacy `FileNotFoundError`); case 17 (soft-deleted stream 200) stays; case 5 (tag reuse) stays
3. **Flip the stream pins** (cases 15): `GET /audio/stream/{id}` → **204**, body empty, `X-Accel-Redirect == f"/media/audio/{filename}", `Content-Type` per extension map, `Accept-Ranges: bytes` — legacy returns 200+body → red
4. Strip `file_path`-specific asserts if any snuck in — the view contract exposes no paths
5. Add: upload with `author="Ada"` → `200` and `authors` gains row `"ada"` (red: legacy ignores the form field)

**Modify `test_audio_repo.py`:** case 3 flips to `AudioRepo(db).soft_delete(999999) -> None` (legacy raises); class import becomes `AudioRepo`; `delete_audio` calls become `soft_delete`.

**Create `test_media_stream.py`** (audio cases): the X-Accel contract rows — 204 + `f"/media/audio/{name}"` for mp3/wav/ogg/m4a; 404 missing id; 404 missing disk file; 404 traversal-seeded `file_path`; 401 unauthenticated.

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py app/tests/test_media_stream.py -v`. Expected red, each for the right reason (401 vs legacy 200; `AttributeError` on delete-missing; one surviving row; `FileNotFoundError`; 200-with-body vs 204 asserts). Everything else green.

- [ ] **Step 3: Implement** — schemas renames → repo → service → router (per Interfaces; the X-Accel endpoint is the only novel code — mirror Task 7's). Add `AudioRepo` to `repositories/__init__.py`.

- [ ] **Step 4: Verify green** — `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py app/tests/test_media_stream.py -v`. Expected: all pass.

- [ ] **Step 5: Format, lint, type**

```bash
cd backend && uv run ruff format app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py app/tests/test_audio_api.py app/tests/test_audio_repo.py app/tests/test_media_stream.py && uv run ruff check app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py app/tests/test_audio_api.py app/tests/test_audio_repo.py app/tests/test_media_stream.py --ignore B008 && uv run mypy app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py --strict
```

Expected: 0/0 (Annex audio rows struck).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/audio.py backend/app/models/audio_tag.py backend/app/repositories/audio_repo.py backend/app/services/audio_service.py backend/app/api/audio_router.py backend/app/schemas/audio_schema.py backend/app/repositories/__init__.py backend/app/tests/test_audio_api.py backend/app/tests/test_audio_repo.py backend/app/tests/test_media_stream.py
git commit -m "refactor: audio module — 2.0, service layer, auth, author link, X-Accel stream, delete-404"
```

---

### Task 11: Video fused rewrite — mirror of audio + whitelist + X-Accel

> **Lint/type gate:** `video_router.py` (0/15), `video_repo.py` (0/2) end at 0/0.

**Files:**
- Rewrite: `backend/app/repositories/video_repo.py`
- Create: `backend/app/services/video_service.py`
- Rewrite: `backend/app/api/video_router.py`
- Modify: `backend/app/schemas/video_schema.py` (renames + delete `Video_Delete`)
- Test: `test_video_repo.py`, `test_video_api.py`, `test_media_stream.py` (Modify)

**Interfaces** — the Task 10 mirror with the video deltas:
- Schemas: `VideoCreate`, `VideoView`; `Video_Delete` deleted
- `VideoRepo` — same shapes as `AudioRepo`
- `VideoService` — `list_videos()`, `upload(file_bytes, filename, *, title, description, tag_names) -> VideoView` (**`title` required**, `validate_media(..., allowed=ALLOWED_VIDEO_EXTENSIONS)` — the new whitelist), `upload_multiple` (validate-all-first), `update(...)`, `soft_delete(...)` (`MediaNotFound("Video not found")`), `resolve_stream(...)` (media type via `mimetypes.guess_type(path)` → `application/octet-stream` fallback — legacy pin preserved; soft-deleted quirk preserved). No author (spec §4)
- Router — prefix `/videos`, RoleChecker everywhere, form `title: str = Form(...)` / `description` / `tags`, `GET /stream/{id}` → X-Accel with `kind="vids"` → `f"/media/vids/{media_path.name}"`

- [ ] **Step 1: Update pins + probes** — mirror Task 10 Step 1 with the video flips: case 4 (`.txt` accepted) → `400` detail `File type .txt not allowed` (red on legacy 200); case 7 (partial-commit) → zero rows/bytes on failure; delete-missing → 404; missing-file → 404; stream pins → 204 + `X-Accel-Redirect` (red on legacy 200+body); `test_media_stream.py` gains the video parametrization.

- [ ] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/test_video_repo.py app/tests/test_video_api.py app/tests/test_media_stream.py -v`. Expected red per flip list; audio rows stay green from Task 10.

- [ ] **Step 3: Implement** — schemas → repo → service → router per Interfaces; add `VideoRepo` to `repositories/__init__.py`.

- [ ] **Step 4: Verify green** — same command. Expected: all pass.

- [ ] **Step 5: Format, lint, type**

```bash
cd backend && uv run ruff format app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/test_video_api.py app/tests/test_video_repo.py app/tests/test_media_stream.py && uv run ruff check app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/test_video_api.py app/tests/test_video_repo.py app/tests/test_media_stream.py --ignore B008 && uv run mypy app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py --strict
```

Expected: 0/0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/video.py backend/app/models/video_tag.py backend/app/repositories/video_repo.py backend/app/services/video_service.py backend/app/api/video_router.py backend/app/schemas/video_schema.py backend/app/repositories/__init__.py backend/app/tests/test_video_api.py backend/app/tests/test_video_repo.py backend/app/tests/test_media_stream.py
git commit -m "refactor: video module — 2.0, service layer, auth, whitelist, X-Accel stream, delete-404"
```

# PART E — nginx + integration

### Task 12: nginx fronts everything

> **Lint/type gate:** `main.py` modification keeps its current clean state; nginx config has no Python surface.

**Files:**
- Create: `nginx/nginx.conf`
- Modify: `docker-compose.yml`
- Modify: `backend/app/main.py` (remove the `StaticFiles` covers mount — nginx takes `/static/covers/` over; the `cover_url` computed field is untouched, same URL prefix)

**Interfaces:**
- `nginx:80` is the only published port. `backend` publishes nothing (internal docker network only).
- `/api/` strips the prefix → `http://backend:8000/`; `/docs` + `/` route to backend unchanged (general fallback location); `/static/covers/` public static; `/media/` **internal** alias (X-Accel target only — one location handles all three kinds because the redirect URIs are `/media/books/…`, `/media/audio/…`, `/media/vids/…`)

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
    # /media/books/x.pdf  -> /srv/uploads/books/x.pdf
    # /media/audio/x.mp3  -> /srv/uploads/audio/x.mp3
    # /media/vids/x.mp4   -> /srv/uploads/vids/x.mp4
    location /media/ {
        internal;
        alias /srv/uploads/;
    }

    # Everything else (/, /docs, /openapi.json, future routes) -> API.
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

(The `db` keeps publishing `5432` — deliberate: Task 7's migration steps and `psql` debugging connect from the host. The `db:5432` publish and the `backend:8000` removal are the only port changes.)

**Why (learning):** three lessons. (1) **The `internal` directive is the security boundary.** A public `/media/` location would let anyone browse files directly and leak the naming scheme; `internal` means the only path to media is through a backend endpoint that already ran `RoleChecker` + `resolve()` containment. (2) **`alias` maps URI to filesystem; `proxy_pass` maps URI to upstream** — the two are not interchangeable, and a wrong `alias` is a silent content-leak. The `/media/` alias pairs with redirect URIs the backend builds from `media_path.name` only (a basename, already containment-checked) — the one-internal-location shape is a deliberate consolidation of the spec §3 sketch. (3) **Streaming auth is layer-split.** FastAPI owns the decision (auth, row lookup, containment, 404), nginx owns the bytes (sendfile, Range). The 204 response's headers are the interface between the two — that is why the unit tests pin the header contract exactly.

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

- [ ] **Step 5: The one Range integration check (replaces the deleted Python Range tables)** — upload or seed a small media file, then:

```bash
curl -s -D - -o /dev/null -H "Authorization: Bearer $TOKEN" \
  -H "Range: bytes=0-99" "http://localhost/api/audio/stream/<id>"
```

  Expected: `HTTP/1.1 206`, `Content-Range: bytes 0-99/<size>`, `Accept-Ranges: bytes`. Also try without `Range` → 200; a suffixed range `bytes=-500` → 206 tail. This proves nginx's RFC 7233 coverage — the behavior the pytest suite deliberately no longer owns (spec §6 mitigation). Record the output in the commit message body or STATE.md.

> Note for local dev without docker (plain `uv run uvicorn`): the 204+X-Accel endpoint has no nginx to serve the file, so media is unreachable — that is expected and per-spec. Local media testing goes through the compose stack; local *API* testing is unaffected (TestClient works without nginx).

- [ ] **Step 6: Format, lint, type** — `cd backend && uv run ruff format app/main.py && uv run ruff check app/main.py --ignore B008 && uv run mypy app/main.py --strict`. Expected: 0/0. Then `uv run pytest -v` — full suite green (nothing about nginx touches the tests).

- [ ] **Step 7: Commit**

```bash
git add nginx/nginx.conf docker-compose.yml backend/app/main.py
git commit -m "feat: nginx front proxy — X-Accel media, public covers, /api routing"
```

# PART F — Final gate + old artifacts

### Task 13: Final gate — DoD, removals, docs

**Files:**
- Delete: `docs/superpowers/plans/2026-08-16-book-refactor.md`, `docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md`, `docs/superpowers/specs/2026-08-16-book-refactor-design.md`
- Modify: `AGENTS.md` (plan references), `README.md`, `STATE.md`

**Why (learning):** a refactor plan is done when the DoD has actually run, the old artifacts can no longer be executed by accident (the `plan-auditor` reads both plan trees — stale plans with fresh checkboxes is how drift happens), and the docs point at the one true plan. Deleting superseded docs is a contribution; git history is the archive (AGENTS.md).

- [ ] **Step 1: Full DoD sweep**

```bash
cd backend && uv run ruff format . && uv run ruff check . --fix --ignore B008 && uv run pytest -v
```

  Expected: format clean; ruff shows only ledger rows owned by remaining hygiene debt (auth/config/database files) — if `--fix` touches a file outside this plan's map, include it in the commit and note it; full suite green (auth, entity, book ×3, tag, media, audio, video files).

- [ ] **Step 2: mypy --strict on every file this plan touched**

```bash
cd backend && uv run mypy app/models/author.py app/models/level.py app/models/genre.py app/models/book.py app/models/audio.py app/models/audio_tag.py app/models/video.py app/models/video_tag.py app/models/tag.py app/schemas/author_schema.py app/schemas/level_schema.py app/schemas/genre_schema.py app/schemas/book_schema.py app/schemas/audio_schema.py app/schemas/video_schema.py app/repositories/author_repo.py app/repositories/level_repo.py app/repositories/genre_repo.py app/repositories/book_repo.py app/repositories/audio_repo.py app/repositories/video_repo.py app/repositories/tag_repo.py app/repositories/__init__.py app/services/author_service.py app/services/level_service.py app/services/genre_service.py app/services/book_service.py app/services/audio_service.py app/services/video_service.py app/services/tag_service.py app/services/book_errors.py app/services/content_validator.py app/services/book_file_storage.py app/services/epub_metadata_reader.py app/services/cover_generator.py app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/api/author_router.py app/api/level_router.py app/api/genre_router.py app/api/book_router.py app/api/audio_router.py app/api/video_router.py app/api/tag_router.py app/main.py --strict
```

  Expected: 0 errors — the Annex fully struck for this plan. Do **not** run `mypy . --strict` as a gate; auth/config/database files remain the hygiene plan's rows.

- [ ] **Step 3: Bug-inventory sweep** — `cd backend && grep -rn "uploads/audio\|uploads/vids" app/ --include='*.py' | grep -v tests` → no output (no CWD-relative literals remain); `grep -rn "print(" app/services/ app/api/` → no output (old god-class debug calls dead).

- [ ] **Step 4: `/audit` + `/verify`** — dispatch `invariant-auditor` then `verifier` over the accumulated diff. On PASS/PASS proceed; a VIOLATION is a failed gate.

- [ ] **Step 5: Delete the superseded artifacts**

```bash
git rm docs/superpowers/plans/2026-08-16-book-refactor.md docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md docs/superpowers/specs/2026-08-16-book-refactor-design.md
```

- [ ] **Step 6: Update `AGENTS.md` references** (requires explicit user go-ahead — this file is the repo's contract)
  1. "Two plans are in flight" → this plan (`2026-09-01-media-refactor-nginx-entities.md`) + `2026-08-15-codebase-hygiene`
  2. `2026-05-26-monorepo-restructure is largely complete` — unchanged
  3. Any "book-refactor plan Tasks 0–5 is the reference pattern" wording → "the 2026-09-01 media refactor plan's Task 7" (or keep the reference but point at the new plan; the pattern survives, the file does not)
  4. The six-invariant "Violating today" column must be updated — this plan strikes the audio/video/tag rows (layering, CWD-relative paths, 2.0, tests, naming). Leave only what actually remains after Task 13

- [ ] **Step 7: Update README + STATE**

  README "Notes" gains: media is served by nginx (`docker compose up -d --build` brings it up; API at `/api/*`; protected media via X-Accel — never expose `/media/`). *(If README.md edits are outside your write permissions, put the exact sentences in a chat message for the user to paste.)* Then invoke the `state` skill: record the completed plan, log the surviving annex rows (hygiene debt), note the media-unreachable-without-nginx dev behavior, and list the Deferred annex as open items.

- [ ] **Step 8: Refresh the knowledge graph + final commit**

```bash
graphify update .
cd backend && git add -A && cd ..
git add -A
git commit -m "chore: media refactor complete — final gate, removed superseded book/avt plans, docs updated"
```

  Tick every completed task box in **this** plan file before that commit (boxes checked in the same commit as their tasks per Global Constraints — any stragglers go here).

## Deferred Work — preserved for a later pass

Consolidated from the two deleted plans and the spec §7. Verified open 2026-09-01:

- **D1: `uploads/vids` → `uploads/videos` directory rename** — needs a data migration (stored `file_path` strings), Dockerfile/nginx alias, and `config.py` touch. Cosmetic; deliberately out.
- **D2: Orphan `Tag` rows** — media PATCH + book update replace link sets without deleting `Tag` rows; `get_or_create_by_names` never deletes. A future `cleanup_orphan_tags` pass.
- **D3: Media metadata / cover extraction** — books have `EpubMetadataReader` + `CoverGenerator`; audio (ID3) and video (poster) have no equivalent.
- **D4: Auth tightening** — every endpoint gates at "any authenticated user." A student read-only split (upload/PATCH/DELETE → admin+teacher) is a `RoleChecker` list change if a product decision asks for it.
- **D5: Cover replacement on PUT** — no image validator in the leaf set; re-add behind a PNG/JPEG magic-byte validator if wanted.
- **D6: epub→pdf conversion + `GET /books/{uid}/read`** — no converter module in this design; resurrection requires a converter + its security review.
- **D7: Orphan entity rows** — `get_or_create_by_name` never deletes; unlinked `authors`/`levels`/`genres` accumulate like D2.

## Self-Review

- **Spec coverage:** §3 nginx topology → Task 12 (with the one-`/media/`-location consolidation noted in its Why); §4 taxonomy/model semantics → Tasks 4/5/7 (FK single-valued, `book_type`→`genre_id` rename, junk discarded, unknown-name `WHERE false` → Task 7 probe 2); §4 entity semantics (case-insensitive reuse, lowercase create, GET-only) → Task 4; §4 search → Task 7; §5 module architecture → Tasks 4/6/7/8/9/10/11; §5 X-Accel contract (204 + three headers, `resolve_stream` containment, covers public via nginx) → Tasks 7/10/11/12; §6 migration with data backfill + preserved-data verification → Task 7f; §6 testing strategy → Part A pins + red-first probes + the single nginx Range integration check (Task 12 Step 5); §7 deferred → annex; §8 invariants → per-task gates + Task 13 Step 6's invariant-table update.
- **Placeholder scan:** no TBD/TODO. Contracts, case lists, and expected red errors are itemized; the four load-bearing blocks (migration, X-Accel endpoint, nginx.conf, compose) are full code. Learner-delegated bodies are the approved format, not elision.
- **Type consistency:** entity repo produce `AuthorRepo.get_by_name -> Author | None` / `get_or_create_by_name -> Author` in Task 4; Task 7 search consumes `get_by_name`, Task 7/10 writes consume `get_or_create_by_name` ✓. `BookRead` name fields via `validation_alias` = model `author_name`/`level_name`/`genre_name` properties (Task 7 produces both halves same task) ✓. `resolve_stream -> tuple[Path, str]` produced by Tasks 7/10/11 services, consumed by their routers, all building `f"/media/{kind}/{media_path.name}"` ✓. `MediaFileStorage(save_dir)` — Task 9 produces, Tasks 10/11 construct `(settings.AUDIO_DIR)`/`(settings.VIDEO_DIR)` ✓. `ALLOWED_VIDEO_EXTENSIONS` — Task 9 produces, Task 11 consumes ✓. Detail strings (`Audio not found`, `Video not found`, `File type .{ext} not allowed`) verbatim across Tasks 1/9/10/11 ✓. `TagRepo.get_or_create_by_names` — Task 8 produces, Tasks 10/11 consume ✓. `schemas/tag_schema.py` untouched while `TagRead` is consumed everywhere ✓.
- **Known risks:** (1) Task 7 is the largest unit — mitigated by the per-file gates (7b–7e) and the fused-commit discipline; (2) the migration's backfill SQL is hand-written and data-touching — mitigated by the empty-DB round-trip **and** the preserved-data check on `jirani_bk` (7f steps 2–3), the two things do not skip; (3) the auth change on audio/video/tag/book endpoints is behavior-breaking for token-less clients — deliberate, user-approved 2026-09-01; (4) Range behavior leaves pytest permanently — the Task 12 Step 5 curl is the standing mitigation; re-run it after any nginx.conf change; (5) intermediate commits before Task 7 leave dev compose on the old schema — but no endpoint touches the new columns until Task 7 lands the migration in the same commit, so only the Task-7-commit boundary matters (and it is handled); (6) `get_or_create_by_names` must reproduce `ilike` semantics exactly or the Part A case-5 pins fail — that is the test guarding it; (7) Task 1's pin 15/18 and Task 2's pin 11/14 flip shape in Tasks 10/11 — a flip that breaks a *different* pin means the probe touched the wrong contract; re-read the pin list before "fixing" it.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-01-media-refactor-nginx-entities.md`. Two execution options:

1. **Learner mode (current convention)** — you implement each task from the contracts, samples, and hints; the agent reviews diffs and runs `/audit` + `/verify` before each commit, and never writes the implementation.
2. **Subagent-Driven** — dispatch a fresh subagent per task with two-stage review; each task brief must be self-contained (the Interfaces blocks above are the brief material).

Which approach?
