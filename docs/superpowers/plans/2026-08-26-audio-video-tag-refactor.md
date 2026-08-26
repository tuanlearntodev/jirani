# Audio / Video / Tag Refactor Implementation Plan (2026-08-26, learner edition)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Learner mode (2026-08-26, user-approved):** this plan follows the convention the book-refactor and hygiene plans adopted on 2026-08-24 — contracts, samples, hints, red-error expectations, gates — but the full implementations stay yours to write. There is **no governing design spec** for this project (unlike books), so this document's `Interfaces` blocks and the samples carry the load: if a signature appears here, later tasks depend on it — match it exactly. TDD is binding (AGENTS.md): a step that says "write the failing test" must show red before you touch the implementation. Characterization pins (Part A) are the one deliberate exception — they assert *current* behavior and are witnessed green first, per the TDD-workflow spec's decision 2.

**Goal:** Bring the audio, video, and tag modules to invariant compliance — service layer (Inv 1), SQLAlchemy 2.0 (Inv 4), full test suites (Inv 5), naming (Inv 6) — on PostgreSQL, fixing the delete-missing 500s, the missed CWD-relative upload path, partial-commit uploads, authless endpoints, non-Range streaming, and the nonexistent video validation, under characterization pins.

**Explicitly out of scope this pass:** the `uploads/vids` → `uploads/videos` directory rename (needs a data migration — preserved in the Deferred Work annex), orphan-tag cleanup, media metadata/cover extraction, and any book/audio/video/tag *schema* change (this plan writes no migration). Book-module files are owned by the book plan and are not touched here.

**Architecture:** One shared leaf-module set replaces the inline router logic: `media_errors.py` (domain exceptions), `media_validator.py` (extension gate, audio whitelist preserved verbatim from `audio_router.py:17`, new video whitelist), `media_file_storage.py` (bytes ↔ disk, `resolve()` containment — the book C4 lesson, centralised so the stream endpoints cannot open a file without passing the check). Each media module then gets a thin service over a 2.0 `select()` repo, with the router reduced to HTTP translation: `RoleChecker([admin, teacher, student])` on every endpoint (user decision 2026-08-26), RFC 7233 Range streaming mirroring the book spec's table (same decision), `MediaNotFound`→404 / `InvalidMediaFile`→400 / `IntegrityError`→400 mapping. Tag logic moves out of the audio/video routers into `TagRepo.get_or_create_by_names()` (one shared aggregate boundary), and the tag module gets its own service. Tests run on the committed testcontainers harness (`db`, `client`, `setup_paths`, `setup_admin`/`login`/`auth_headers`); the legacy `AttributeError`-=500 delete bug is pinned via `TestClient`'s `raise_server_exceptions=True` as `pytest.raises(AttributeError)`, then flipped to a 404 probe red-first.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests), uvicorn, uv, pytest/httpx, ruff, mypy.

**Governing specs:** `docs/superpowers/specs/2026-08-24-tdd-workflow-design.md` (approved 2026-08-24 — decisions 1–4: TDD binding, characterization-first, tag included; its "Explicitly deferred" section §73–77 is this project's brief). Pattern reference (not binding): `docs/superpowers/specs/2026-08-16-book-refactor-design.md` — the audio/video/tag plan mirrors its module shape, error-mapping rule, RoleChecker placement, RFC 7233 table, and resolve()-containment lesson. Deferred-annex positions inherited from `2026-08-16-book-refactor.md` D1/D3 and `2026-08-15-codebase-hygiene.md` D2/D3 are mapped to tasks in the annex header below.

## Global Constraints

Every task implicitly includes all of the following. Exact values copied from the specs.

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; no `docker compose up -d db` needed for tests. The harness (`backend/app/tests/conftest.py`) exposes `db`, `client`, `setup_paths`, and importable helpers `setup_admin`/`login`/`auth_headers` (module-level, safe since hygiene S1 — book plan Corrections #2). `app.tests` is a package — never re-create its `__init__.py`
- One harness trap survives (book plan Architecture): **call `db.expire_all()` before reading via `db` after a write through `client`** — the long-lived session's identity map otherwise returns stale objects
- `ruff check` with `--ignore B008` on changed files; `mypy --strict` on changed files only, per the Debt Coverage Annex below — touched files end at **0 ruff + 0 mypy**, and pre-existing errors in a touched file are that task's debt to clear. Log other plans' failures in STATE.md; do not fix unrelated files
- Characterization-first (TDD spec decision 2): Part A pins are **witnessed green on legacy code first**; every behavior *fix* gets a red-first probe that fails on legacy before implementation. Never delete a failing test to make the suite pass
- Commit after every task, including the plan file tick in the same commit (AGENTS.md); message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- **Locked decisions (user-approved 2026-08-26):** `RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])` on **every** audio/video/tag endpoint (any authenticated account; no 403 path exists); RFC 7233 Range on `/audio/stream` and `/videos/stream` per the book spec's table; a `ALLOWED_VIDEO_EXTENSIONS` whitelist for video (audio's whitelist preserved verbatim); learner-edition format
- **No schema changes in this plan.** Models convert `Column()` → `mapped_column()` with identical columns; relationship names/table names unchanged (rewriting the classes alone gives Alembic zero delta — hygiene S5 owns migrations and the harness still uses `create_all` for tests)
- After the final task, run `graphify update .` (AST-only)
- Work tree note: uncommitted auth changes (`auth_router.py`, `setup_router.py`, `auth_repo.py`, `auth_service.py`, `test_auth.py`) are in flight on this branch — leave them alone; the plan runs on the current working tree

## Positions inherited from the two plans' Deferred annexes (verified 2026-08-26)

| Source (annex) | Position | Lands in |
|---|---|---|
| Book plan D1 / hygiene D2 | `audio_repo.py:20-25` `delete_audio` + `video_repo.py:22-27` `delete_video` dereference `None.deleted_at` on missing id → 500; fix to 404 | Task 7 / Task 8 red-first probes |
| Book plan D1 | tag logic inline in routers (Inv 1) — "a tag service + repo belong with these suites" | Task 6 (service + `get_or_create_by_names`) |
| Book plan D3 | `TagRepo` still legacy `query()` → 2.0 | Task 6 |
| Hygiene D2 | tests: repo soft-delete semantics + API upload / upload_multiple / list-excludes-deleted / patch / stream / delete-404 | Part A (pins) + Part C (probes) |
| Hygiene D3 | `Audio`/`Video`/`AudioTag`/`VideoTag` models legacy 1.x `Column` | Task 7 / Task 8 |
| Inv 3 (missed by S3) | `audio_router.py:91` still writes the literal `"uploads/audio"` (CWD-relative) — the single-upload site was fixed, this one was not | Task 7 red-first probe |
| Inv 6 (no plan covered it) | `Audio_Repo`, `Video_Repo`, `Audio_Create`, `Audio_View`, `Video_Create`, `Video_View`, `Video_Delete` | Tasks 6–8 renames |
| STATE ledger | audio 19+1 / video 15+1 / repos+models 9 / tag module 7 rows | Debt Coverage Annex |

## Current State (verified against the tree, 2026-08-26)

| Area | State | Where |
|---|---|---|
| Audio endpoints | 🔴 6 endpoints, **zero auth**, inline DB + tag logic | `backend/app/api/audio_router.py` (177 lines) |
| Video endpoints | 🔴 6 endpoints, **zero auth**, inline DB + tag logic | `backend/app/api/video_router.py` (157 lines) |
| Tag endpoint | 🔴 `GET /tags/` only, zero auth, repo passthrough | `backend/app/api/tag_router.py:11-13` |
| Delete missing id | 🔴 LIVE 500 — `None.deleted_at` deref | `audio_repo.py:20-25`, `video_repo.py:22-27` |
| CWD-relative path | 🔴 LIVE — `upload_directory = "uploads/audio"` (S3 fixed the single-upload site only) | `audio_router.py:91` |
| upload_multiple partial commit | 🔴 files saved + rows committed for earlier files before a later file's validation fails | `audio_router.py:91-106`, `video_router.py:79-95` |
| Streaming | 🔴 ignores `Range` (always 200 full body), no `Accept-Ranges`, opens DB `file_path` with **no containment** (traversal), missing file on disk → 500, stream serves soft-deleted rows | `audio_router.py:152-177`, `video_router.py:139-157` |
| Video validation | 🔴 **none** — any filename uploads, no whitelist (audio has one) | `video_router.py:41-72` |
| Models | 🔴 legacy 1.x `Column()` x4 (`Audio`, `Video`, `AudioTag`, `VideoTag`); `Tag` already 2.0 | `models/audio.py`, `video.py`, `audio_tag.py`, `video_tag.py`, `tag.py` |
| Repos | 🔴 legacy `query()` x3; `AudioRepo.update_audio`, `TagRepo.get_tag_by_id`, `TagRepo.create_tag`, `Video_Delete` are dead code | `audio_repo.py:27-35`, `tag_repo.py:11-24`, `video_schema.py:21-23` |
| Naming (Inv 6) | 🔴 `Audio_Repo`, `Video_Repo`, `Audio_Create`, `Audio_View`, `Video_Create`, `Video_View`, `Video_Delete` | all audio/video modules + schemas |
| Tests (Inv 5) | 🔴 zero — suite contains only `test_auth.py` | `backend/app/tests/` |
| Whitelist constants | ✅ `ALLOWED_AUDIO = {"mp3","mp4","wav","ogg","m4a","aac","flac"}` | `audio_router.py:17` |
| Anchored dirs | ✅ `AUDIO_DIR`/`VIDEO_DIR` exist, BASE_DIR-anchored; lifespan mkdirs them | `config.py:41-42`, `main.py:26-27` |
| Blast radius | ✅ audio/video/tag modules are imported **only** by their own routers, `main.py`, `api/__init__.py`, `models/__init__.py`, `repositories/__init__.py`; `tag_schema` (via `book_router`) is **not** modified in this plan | verified by grep 2026-08-26 |

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/tests/test_audio_repo.py` | Create | 1 | Audio repo characterization pins (incl. the `AttributeError` bug pin) |
| `backend/app/tests/test_audio_api.py` | Create | 1, 7 | Audio API pins; Task 7 flips bug pins + adds auth/stream probes |
| `backend/app/tests/test_video_repo.py` | Create | 2, 8 | Video repo pins; Task 8 flips |
| `backend/app/tests/test_video_api.py` | Create | 2, 8 | Video API pins; Task 8 flips + probes |
| `backend/app/tests/test_tag_repo.py` | Create | 3, 6 | Tag repo pins; 2.0 + `get_or_create_by_names` tests |
| `backend/app/tests/test_tag_api.py` | Create | 3, 6 | Tag API pins; auth probe |
| `backend/app/services/media_errors.py` | Create | 4 | `MediaError` base; `MediaNotFound`, `InvalidMediaFile` |
| `backend/app/services/media_validator.py` | Create | 4 | `validate_media(filename, *, allowed) -> str`; `ALLOWED_AUDIO_EXTENSIONS`, `ALLOWED_VIDEO_EXTENSIONS` |
| `backend/app/tests/test_media_validator.py` | Create | 4 | Validator unit tests |
| `backend/app/services/media_file_storage.py` | Create | 5 | `MediaFileStorage(save_dir)` — `save` / `resolve` (containment + existence) / `delete` |
| `backend/app/tests/test_media_storage.py` | Create | 5 | Storage round-trip + traversal containment |
| `backend/app/repositories/tag_repo.py` | Rewrite | 6 | 2.0 `select()`; keep `get_all_tags`, add `get_or_create_by_names`; delete dead methods |
| `backend/app/services/tag_service.py` | Create | 6 | `TagService.list_tags() -> list[TagRead]` |
| `backend/app/api/tag_router.py` | Rewrite | 6 | RoleChecker + service call |
| `backend/app/tests/test_media_stream.py` | Create | 7, 8 | RFC 7233 table; audio in 7, video parametrization in 8 |
| `backend/app/repositories/audio_repo.py` | Rewrite | 7 | `AudioRepo` — 2.0 `select()`, `create`/`get_by_id`/`list_active`/`soft_delete`; delete dead `update_audio` |
| `backend/app/services/audio_service.py` | Create | 7 | `AudioService(db)` — orchestration, domain exceptions, tag linking via `TagRepo` |
| `backend/app/api/audio_router.py` | Rewrite | 7 | RoleChecker + Range + error mapping + DI |
| `backend/app/schemas/audio_schema.py` | Modify | 7 | Rename `Audio_Create`→`AudioCreate`, `Audio_View`→`AudioView` |
| `backend/app/models/audio.py`, `audio_tag.py` | Modify | 7 | 2.0 `mapped_column()`, identical columns |
| `backend/app/repositories/video_repo.py` | Rewrite | 8 | `VideoRepo` — mirror of `AudioRepo` |
| `backend/app/services/video_service.py` | Create | 8 | `VideoService(db)` — mirror of `AudioService` |
| `backend/app/api/video_router.py` | Rewrite | 8 | RoleChecker + Range + error mapping + whitelist |
| `backend/app/schemas/video_schema.py` | Modify | 8 | Rename classes; delete dead `Video_Delete` |
| `backend/app/models/video.py`, `video_tag.py` | Modify | 8 | 2.0 `mapped_column()`, identical columns |
| `backend/app/tests/test_audio_repo.py`, `test_video_repo.py`, `test_audio_api.py`, `test_video_api.py` | Modify | 7/8 | Flip bug pins (500→404), add auth headers to all requests, add 401 guards |
| `backend/app/main.py`, `app/api/__init__.py`, `app/repositories/__init__.py` | Modify | 6/7/8 | Unchanged behavior; `__init__` exports for renamed classes stay/join (`AudioRepo`, `VideoRepo` in `__all__`) |
| `backend/app/schemas/tag_schema.py` | — | — | **Untouched** — `TagCreate`/`TagRead` are consumed by `book_router`/`book_schema` |

## Debt Coverage Annex (measured 2026-08-26)

Snapshot of the target files only, fresh-measured for this plan: **0 ruff errors** (B008-ignored) and **49 `mypy --strict` errors** across the audio/video/tag modules (STATE.md's 2026-08-23 ledger recorded audio 19+1, video 15+1, repos/models 9, tag module 7 — the two numbers differ only by subsequent auth-work churn; the fresh 49 is the operative baseline). Every row's debt is struck by a rewrite task; the callout rows (`config.py`, auth files, book files) belong to the hygiene and book plans — red on those files is expected until those plans run.

| File | ruff | mypy | Owning task |
|---|---|---|---|
| `app/api/audio_router.py` | 0 | 19 | 7 (full rewrite) |
| `app/api/video_router.py` | 0 | 15 | 8 (full rewrite) |
| `app/api/tag_router.py` | 0 | 1 | 6 (rewrite) |
| `app/repositories/audio_repo.py` | 0 | 5 | 7 (rewrite) |
| `app/repositories/video_repo.py` | 0 | 2 | 8 (rewrite) |
| `app/repositories/tag_repo.py` | 0 | 2 | 6 (rewrite) |
| `app/models/audio.py`, `audio_tag.py` | 0 | 2 | 7 (2.0 conversion) |
| `app/models/video.py`, `video_tag.py` | 0 | 2 | 8 (2.0 conversion) |
| `app/models/tag.py` | 0 | 1 | 6 (touch — clear or log) |
| `app/schemas/audio_schema.py`, `video_schema.py`, `tag_schema.py` | 0 | 0 | 7/8 renames keep them at 0 |

# PART A — Characterization pins

Part A pins current behavior — including its bugs — per the TDD-workflow spec's decision 2. Every pin here is **witnessed green against the legacy code**: that is what makes it a pin rather than a wish. Pins assert the *contract* (status, fields, user-visible semantics), not incidental internals — with one deliberate exception: bugs are pinned as-broken with `pytest.raises(...)` and later flipped red-first. The legacy code has no auth, so Part A requests carry **no headers**; Tasks 7–8 add the `auth_headers` fixture to every request and add the 401 guards. The single-upload path reads `settings.AUDIO_DIR` per call, so `monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)` works there; the literal-path bug site (`audio_router.py:91`) ignores the patch — pins touching `upload_multiple` assert DB rows, never the filesystem, until Task 7 fixes the path.

### Task 1: Audio characterization pins

**Files:**
- Create: `backend/app/tests/test_audio_repo.py`
- Create: `backend/app/tests/test_audio_api.py`

**Interfaces:**
- Consumes: legacy `Audio_Repo` (`create_audio`, `delete_audio`), `Audio` model, `Audio_Create`/`Audio_View` schemas, `app.models` exports, harness fixtures `db`, `client`, `monkeypatch`, `tmp_path`
- Produces: the pinned-behavior statement later tasks must preserve — soft delete excludes from list but keeps the row; stream serves soft-deleted rows; DELETE returns 200 with `id`/`title`/`description`/`audio_url`/`tags` (the incidental `file_path`/`created_at`/`deleted_at` leak is **not** pinned — Task 7's `AudioView` response deliberately drops it); DELETE missing id raises `AttributeError` (the bug pin); `upload_multiple` accepts no tags and persists earlier files before a later failure (the bug pin)

**Why (learning):** pins must be written first because everything downstream is measured against them: the fused rewrites in Task 7 run the identical test files and must stay green except where a fix deliberately flips a pin. A pin that passes for the wrong reason (e.g. an empty-tags bug masked by a missing row) teaches nothing — seed through the API where possible, assert both the response *and* the DB state.

**Seeding idioms (samples):**

```python
def _seed_audio(db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3") -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track
```

Auth is absent on legacy — requests below carry no headers. When a test writes through `client`, call `db.expire_all()` before reading via `db` (harness trap, see Global Constraints).

- [ ] **Step 1: Write `test_audio_repo.py` — the repo pins**

Case list (write the bodies yourself):
1. `create_audio` persists: row gets an id; `title`/`description`/`file_path` round-trip; `deleted_at` is `None`
2. `delete_audio` soft-deletes: `deleted_at` set (compare `datetime.now(UTC)` within a small delta), row still present in DB
3. `delete_audio` on a missing id **raises** — the bug pin: `with pytest.raises(AttributeError): Audio_Repo(db).delete_audio(999999)`

Run: `cd backend && uv run pytest app/tests/test_audio_repo.py -v`. Expected: `3 passed` — pins pass immediately on legacy, this is correct characterization, not a red failure. (Docker daemon required — the harness starts `postgres:16-alpine`.)

- [ ] **Step 2: Write `test_audio_api.py` — the API pins**

Case list (write the bodies yourself):

1. `GET /audio/` on an empty table → `200`, `[]`
2. `GET /audio/` excludes a soft-deleted track (seed two, delete one via repo) — assert the remaining id; do **not** assert order (no `ORDER BY` exists; treat the response as a set)
3. `POST /audio/upload` happy path: `files={"file": ("song.mp3", b"\xff\xfbID3 mock audio bytes", "audio/mpeg")}`, `data={"tags": "math, algebra"}` → `200`: `title == "song"` (filename stem — the `.mp3` is stripped), `audio_url == f"/audio/stream/{id}"`, `tags == [{"id": t1, "name": "math"}, {"id": t2, "name": "algebra"}]` in that order; the file bytes exist under `monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)` with the `{uuid4}_{filename}` naming; the DB row's `file_path` is under `tmp_path`
4. `POST /audio/upload` with `data={"tags": " math ,, MATH "}` → single tag, stored name **lowercase** `"math"` (new tags are created lowercased; duplicates collapse; the leading/trailing spaces are stripped)
5. `POST /audio/upload` with existing mixed-case tag: pre-create `Tag(name="Math")` via `db`, upload `tags="MATH"` → the **existing** `"Math"` is reused (match is case-insensitive `ilike`), not a second row — assert both the response name and `db.query(Tag).count() == 1`
6. `POST /audio/upload` with `.txt` filename → `400` with detail `File type .txt not allowed`, and `tmp_path` contains **no** file (single upload validates before any byte reaches disk)
7. `POST /audio/upload` with an extensionless filename → `400` (extension extraction is `rsplit(".", 1)[-1]`, returns the whole name, whitelist rejects)
8. `POST /audio/upload_multiple` (two files, second `.txt`, **no tags param exists**) → `400`; then assert via `client`: `GET /audio/` returns exactly **one** track — this is the partial-commit bug pin (the valid file was saved and committed before the invalid one failed; the valid file's bytes landed under the CWD-relative `"uploads/audio"` literal — do **not** assert on the filesystem here, the pin is the DB side effect)
9. `POST /audio/upload_multiple` (two valid files) → `200` list of two views, `title` is each filename stem
10. `PATCH /audio/{id}` with `title`, `description`, `tags="bass"` → `200` updated view (title/description changed, tag set **replaced**: previous tags gone from the response, `"bass"` present); the *old tag row survives in DB* (PATCH clears links, never deletes `Tag` rows — pin via `db.query(Tag)`)
11. `PATCH /audio/{id}` with `tags=""` → tag set **cleared** (empty string is not `None` — it clears); with `tags` omitted → tags untouched
12. `PATCH /audio/999999` → `404` with detail `Audio not found`; no DB change
13. `DELETE /audio/{id}` (existing) → `200`; response contains `id`, `title`, `description`, `audio_url`, `tags` keys; afterwards `GET /audio/` excludes it; the row still exists with `deleted_at` set
14. `DELETE /audio/999999` → the bug pin: `with pytest.raises(AttributeError): client.delete("/audio/999999")` — the harness's `raise_server_exceptions=True` surfaces the `None.deleted_at` deref as a raised exception instead of a 500. This is the flip target for Task 7's probe
15. `GET /audio/stream/{id}` (seed row whose `file_path` points at a real `tmp_path` file with mock bytes) → `200`, `Content-Type: audio/mpeg` (`.mp3`), body byte-for-byte equal to the file
16. `GET /audio/stream/999999` → `404` detail `Audio not found`
17. Stream of a **soft-deleted** track → `200` (the quirk pin: streaming ignores `deleted_at`)
18. Stream whose row's file is missing on disk → the bug pin: `with pytest.raises(FileNotFoundError)` (uncaught `open()`)

- [ ] **Step 3: Run and witness green**

Run: `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py -v`. Expected: all pass (approximately 21 tests). If a pin fails, it is asserting something the code does not do — fix the **pin** to match verified behavior and record the deviation at the bottom of this task; do not fix legacy code here.

- [ ] **Step 4: Lint and commit**

```bash
cd backend && uv run ruff format app/tests/test_audio_repo.py app/tests/test_audio_api.py && uv run ruff check app/tests/test_audio_repo.py app/tests/test_audio_api.py --ignore B008
```

Commit (from `backend/`, or repo root with the `backend/` prefix):

```bash
git add backend/app/tests/test_audio_repo.py backend/app/tests/test_audio_api.py
git commit -m "test: pin audio module behavior — list, upload, patch, delete, stream"
```

---

### Task 2: Video characterization pins

**Files:**
- Create: `backend/app/tests/test_video_repo.py`
- Create: `backend/app/tests/test_video_api.py`

**Interfaces:**
- Consumes: legacy `Video_Repo` (`create_video`, `delete_video`), `Video` model, `Video_Create`/`Video_View` schemas, harness fixtures
- Produces: the video pinned-behavior statement, mirroring Task 1 with four deliberate differences: upload takes `title` **(required Form)** and optional `description`/`tags` from the form; **no extension validation exists** — `video_router.py:41-72` accepts any filename (pinned as-is; Task 8 adds the whitelist red-first, which flips this pin); content type comes from `mimetypes.guess_type(file_path)` with `application/octet-stream` fallback; unknown `file_path` extensions on stream resolve via `guess_type` (`.mp4` → `video/mp4`)

**Why (learning):** the video module is a near-copy of audio with three behavioral deltas (form title, no validation, mimetypes). Pinning both sides of each delta now is what makes Task 8's fused rewrite verifiable — a rewrite that silently added audio's validation or dropped the form title would fail these pins but pass a hand-written test suite.

- [ ] **Step 1: Write `test_video_repo.py`** — mirror Task 1 Step 1: create persists, delete soft-deletes, delete-missing **raises `AttributeError`** (video_repo.py:24 bug pin).

- [ ] **Step 2: Write `test_video_api.py`** — case list (mirror Task 1 Step 2 with the deltas applied):

1. `GET /videos/` empty → `200 []`; excludes soft-deleted (set assertion, no order)
2. `POST /videos/upload` happy: `files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42 mock bytes", "video/mp4")}`, form `title="Intro"`, `description="first"`, `tags="lesson"` → `200`: `title == "Intro"` (form wins — no stem fallback on single upload), `description == "first"`, `video_url == f"/videos/stream/{id}"`, tags `[{"id", "name": "lesson"}]`; file under `settings.VIDEO_DIR` (monkeypatched to `tmp_path` — video's path is settings-driven, unlike audio's line-91 literal)
3. `POST /videos/upload` **missing `title`** → `422` (required Form)
4. `POST /videos/upload` with `.txt` filename → **`200`** — the quirk pin: video accepts any file. Note in a comment: Task 8 flips this to `400`
5. `POST /videos/upload` with `tags=" MATH , math "` → single tag reused/collapsed, stored name keeps the **first-seen case** when a pre-existing `Tag("Math")` row exists; lowercased otherwise (identical `ilike` semantics to audio — `ilike` matches the case-insensitive comparison, so no trick in `MATH` being uppercase)
6. `POST /videos/upload_multiple` valid pair → `200` list of two; `title` is the filename stem, `description is None`
7. `POST /videos/upload_multiple` with a later invalid... **nothing is invalid** today — instead pin the partial-commit shape that Task 8's whitelist will expose: two files where the second has an illegal extension still yields `200` and **both** rows today (no validation = no failure). The Task 8 probe will flip this
8. `PATCH /videos/{id}` title/description/tags replace; tags empty-string clears; tags omitted leaves; old `Tag` rows survive; missing id → `404` detail `Video not found`
9. `DELETE /videos/{id}` → `200` with the pinned keys (`id`, `title`, `description`, `video_url`, `tags`); excluded from list afterwards; row kept with `deleted_at`
10. `DELETE /videos/999999` → bug pin: `with pytest.raises(AttributeError)`
11. `GET /videos/stream/{id}` → `200`, `Content-Type: video/mp4`, body equals the seeded file bytes
12. `GET /videos/stream/999999` → `404` detail `Video not found`
13. Stream soft-deleted track → `200` (quirk pin)
14. Stream with row file missing on disk → bug pin: `with pytest.raises(FileNotFoundError)`

- [ ] **Step 3: Run and witness green** — `cd backend && uv run pytest app/tests/test_video_repo.py app/tests/test_video_api.py -v`. Expected: all pass.

- [ ] **Step 4: Lint and commit**

```bash
cd backend && uv run ruff format app/tests/test_video_repo.py app/tests/test_video_api.py && uv run ruff check app/tests/test_video_repo.py app/tests/test_video_api.py --ignore B008
```

```bash
git add backend/app/tests/test_video_repo.py backend/app/tests/test_video_api.py
git commit -m "test: pin video module behavior — list, upload, patch, delete, stream"
```

---

### Task 3: Tag characterization pins

**Files:**
- Create: `backend/app/tests/test_tag_repo.py`
- Create: `backend/app/tests/test_tag_api.py`

**Interfaces:**
- Consumes: legacy `TagRepo` (`get_all_tags`, `get_tag_by_id`, `create_tag`), `Tag` model, `TagRead`, `TagCreate` (from `app.schemas.tag_schema` — its validator strips and normalises), harness `db`/`client`
- Produces: the pinned statement that Task 6 preserves — `GET /tags/` is an unordered list of `{id, name}`; `get_tag_by_id` returns `None`... **on a missing id** (legacy `.first()`); `create_tag` applies the `TagCreate` validator (whitespace collapse, charset, length). Both `get_tag_by_id` and `create_tag` are dead in the app today (verified by grep — the only caller of `TagRepo` is `tag_router`, which calls `get_all_tags`) — their pins become their deletion's justification, exactly the "deleting dead code is a contribution" rule

**Why (learning):** the tag module is the smallest aggregate and its rewrite is the dependency later tasks stand on (`get_or_create_by_names` is consumed by both media services). Pinning `Tag` row semantics now — validator normalization, survival of typo'd case — protects Task 6's rule: validation belongs to `TagCreate`, storage keeps what it is given.

- [ ] **Step 1: Write `test_tag_repo.py`**

Case list (write the bodies yourself):
1. `get_all_tags` returns seeded rows (seed three via `db.add(Tag(name=...))`); assert names as a set, not an order
2. `get_tag_by_id(seeded_id)` returns the row with `name`; `get_tag_by_id(999999)` returns `None`
3. `create_tag(TagCreate(name="  Math  "))` → stored name `"Math"` — the validator's `" ".join(v.split())` collapse; a re-run with `"Math"` → **unique-constraint `IntegrityError`** (name is unique — app-level `ilike` matching means users may reach for duplicate-looking names, but the DB is the guarantee; this is the "constraint vs check" boundary)

- [ ] **Step 2: Write `test_tag_api.py`**

1. `GET /tags/` empty → `200 []`
2. `GET /tags/` with three seeded tags → `200`, set of names and `id`/`name` shape
3. (Legacy has no auth — no 401 pin here; Task 6 adds it.)

- [ ] **Step 3: Run and witness green** — `cd backend && uv run pytest app/tests/test_tag_repo.py app/tests/test_tag_api.py -v`. Expected: all pass.

- [ ] **Step 4: Lint and commit**

```bash
cd backend && uv run ruff format app/tests/test_tag_repo.py app/tests/test_tag_api.py && uv run ruff check app/tests/test_tag_repo.py app/tests/test_tag_api.py --ignore B008
```

```bash
git add backend/app/tests/test_tag_repo.py backend/app/tests/test_tag_api.py
git commit -m "test: pin tag module behavior — list, lookup, create normalization"
```

# PART B — Leaf modules

Part B ships the three shared modules the fused rewrites consume, in the book plan's leaf-first order: nothing imports them yet, so the tree stays green after every commit. Each module is red-first even though the tree as a whole stays green — the red is `ModuleNotFoundError` on its own test file, verified before the module exists, then green after.

### Task 4: `media_errors.py` + `media_validator.py`

> **Lint/type gate:** new files ship clean (0/0).

**Files:**
- Create: `backend/app/services/media_errors.py`
- Create: `backend/app/services/media_validator.py`
- Test: `backend/app/tests/test_media_validator.py`

**Interfaces:**
- Produces:
  - `class MediaError(Exception)` — `__init__(self, detail: str | None = None)`; attribute `self.detail: str` falling back to class attribute `default_detail: str`; no HTTP types anywhere (Invariant 2)
  - `class MediaNotFound(MediaError)` — `default_detail = "Media not found"` (carries row-missing, file-missing, and traversal cases; the router maps every `MediaNotFound` to 404)
  - `class InvalidMediaFile(MediaError)` — `default_detail = "Invalid media file"` (router maps to 400)
  - `ALLOWED_AUDIO_EXTENSIONS: frozenset[str]` — **verbatim copy** of `audio_router.py:17`: `{"mp3", "mp4", "wav", "ogg", "m4a", "aac", "flac"}`
  - `ALLOWED_VIDEO_EXTENSIONS: frozenset[str]` — new: `{"mp4", "mov", "avi", "mkv", "webm", "m4v", "ogv", "wmv"}`. Note: `135f3ac` ("Video file types") is in git history on the `feature/videofiletypes` branch if you want the historical source of the on-disk `.mp4` examples
  - `def validate_media(filename: str, *, allowed: frozenset[str]) -> str` — returns the lowercase extension; raises `InvalidMediaFile(f"File type .{ext} not allowed")` on a disallowed extension. The detail string is **verbatim** the legacy message from `audio_router.py:23` so the Task 1 pin 6's expectation survives the module move
- Consumes: nothing but stdlib

Design note (deliberate): the whitelists live in the validator module, not `config.py`. Extension whitelists are domain knowledge, not deployment settings, and `config.py` carries hygiene-A4-owned mypy debt — touching it would import that debt into this plan. This is the one intentional deviation from the book's `ContentValidator` (which read `settings.ALLOWED_EXTENSIONS`); recorded here so nobody "fixes" it later.

**Why (learning):** two pure-Python leaves, no HTTP, no `open()`, no DB — unit-testable in isolation. `MediaError` carries `.detail` because every legacy 404 message (`Audio not found`, `Video not found`) becomes a `detail` string at the point of raise, and the router only needs `except MediaError as e: ...`.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_media_validator.py`. Cases:
1. `validate_media("Song.MP3", allowed=ALLOWED_AUDIO_EXTENSIONS)` → `"mp3"` (case-folded)
2. `validate_media("clip.mp4")` with the audio whitelist → raises `InvalidMediaFile`; assert `exc.value.detail == "File type .mp4 not allowed"` (verbatim legacy message)
3. `validate_media("clip.mp4")` with the video whitelist → `"mp4"`; `"clip.txt"` → raises
4. `validate_media("noext", allowed=...)` → raises (no dot: `rsplit(".", 1)[-1]` returns the whole name)
5. `validate_media("song.mp3.", ...)` → raises (trailing-dot name yields empty extension)
6. `MediaNotFound("Audio not found")` → `.detail == "Audio not found"`; `MediaNotFound()` → `.detail == "Media not found"`; same default-detail behavior for `InvalidMediaFile`

Sample — the failure idiom:

```python
from app.services.media_errors import InvalidMediaFile, MediaNotFound
from app.services.media_validator import (ALLOWED_AUDIO_EXTENSIONS,
                                          ALLOWED_VIDEO_EXTENSIONS, validate_media)


def test_audio_whitelist_rejects_video_extension() -> None:
    with pytest.raises(InvalidMediaFile) as exc:
        validate_media("clip.mp4", allowed=ALLOWED_AUDIO_EXTENSIONS)
    assert exc.value.detail == "File type .mp4 not allowed"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_media_validator.py -v`. Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.media_validator'` — red for the right reason. (Docker daemon still required; the session-scoped harness container starts even for pure-Python tests.)

- [ ] **Step 3: Create `media_errors.py`** — the three classes per the Interfaces contract. Hint: the base class pattern mirrors the book's `book_errors.py`; a per-class `default_detail` and a `detail` override are the whole design.

- [ ] **Step 4: Create `media_validator.py`** — whitelist constants + `validate_media`. Hint: everything the legacy `audio_router.validate_audio` did, minus the `HTTPException`, plus an `allowed` parameter for the second whitelist.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_media_validator.py -v`. Expected: all pass.

- [ ] **Step 6: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/media_errors.py app/services/media_validator.py app/tests/test_media_validator.py && uv run ruff check app/services/media_errors.py app/services/media_validator.py app/tests/test_media_validator.py --ignore B008 && uv run mypy app/services/media_errors.py app/services/media_validator.py --strict
```

Expected: ruff clean after format; mypy 0 errors on the two service files.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/media_errors.py backend/app/services/media_validator.py backend/app/tests/test_media_validator.py
git commit -m "feat: add media domain errors and extension validator"
```

---

### Task 5: `MediaFileStorage` (incl. `resolve()` containment)

> **Lint/type gate:** ships clean (0/0); the storage module is the pattern Task 7's service copies.

**Files:**
- Create: `backend/app/services/media_file_storage.py`
- Test: `backend/app/tests/test_media_storage.py`

**Interfaces:**
- Produces:
  - `class MediaFileStorage` — `__init__(self, save_dir: Path)`
  - `save(self, file_bytes: bytes, filename: str) -> str` — `save_dir.mkdir(parents=True, exist_ok=True)`; writes to `save_dir / f"{uuid4()}_{filename}"` (the legacy naming, preserved); returns the **absolute** path as `str` (this is what the DB row's `file_path` stores from Task 7 on; legacy rows may hold either the old relative `"uploads/audio/..."` form or an absolute path — `resolve` must handle both)
  - `resolve(self, path: str) -> Path` — resolves any stored `file_path` to a `Path` and **raises `MediaNotFound`** on failure: (a) traversal — the resolved path escapes `save_dir` (`Path.is_relative_to()`); (b) the file does not exist. One gate for "can this row be served", mirroring the book's `BookFileStorage.resolve()`: the stream endpoint cannot open a file without passing through it
  - `delete(self, path: str) -> None` — `resolve` then `unlink(missing_ok=True)`
- Consumes: `MediaError`/`MediaNotFound` (Task 4), `uuid`, `Path`; the services instantiate it as `MediaFileStorage(settings.AUDIO_DIR)` and `MediaFileStorage(settings.VIDEO_DIR)`

**Why (learning):** the book refactor's C4 finding applies verbatim here: a DB-supplied `file_path` joined to a directory escapes it via `..`, and today `audio_router.py:170`/`video_router.py:150` `open(file_path)` without any check — a poisoned row can serve `/etc/hosts`. The uuid prefix on the write path incidentally defeats write-side traversal, but the *read* path's untrusted input is the DB row, and containment must be one testable gate, not a policy per call site.

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_media_storage.py`. Cases (use `tmp_path` as `save_dir`):
1. `save(b"bytes", "song.mp3")` → returns a `str`; the file exists at `tmp_path`; the name matches `r"^[0-9a-f-]{36}_song\.mp3$"` (uuid prefix + original name)
2. Nested-filename write: `save(b"b", "sub/dir.mp3")` → created under `tmp_path/sub/` (nested names are legal), returned path parses back via `resolve`
3. `resolve(save(...))` round-trips to a path whose `read_bytes()` equals the saved bytes
4. `resolve(str(tmp_path / "song.mp3"))` on an absolute legacy-style path → works when inside `save_dir`
5. Legacy relative form: `resolve("uploads/audio/uuid_x.mp3")` — create the file at `save_dir / "uuid_x.mp3"`, resolve with `relative_to("uploads/audio")`... unify: `resolve` joins **relative** paths to `save_dir` (this covers old rows whose stored path was the relative `"uploads/audio/..."`).
6. Traversal: file at `tmp_path.parent / "secret.txt"`; `resolve(str(tmp_path.parent / "secret.txt"))` → raises `MediaNotFound`
7. Traversal via `..`: `resolve(str(save_dir / ".." / "secret.txt"))` → raises `MediaNotFound`
8. Missing file inside dir: `resolve(str(save_dir / "ghost.mp3"))` → raises `MediaNotFound`
9. `delete(save(...))` → file gone; `delete` on an already-missing path → no raise (`missing_ok=True`)

Sample — the traversal idiom:

```python
def test_resolve_rejects_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_bytes(b"secret")
    storage = MediaFileStorage(tmp_path)
    with pytest.raises(MediaNotFound):
        storage.resolve(str(outside))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_media_storage.py -v`. Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.media_file_storage'`.

- [ ] **Step 3: Create `media_file_storage.py`** per the Interfaces. Hints: `Path.is_relative_to` is the containment check; resolve a relative path against `save_dir` before checking containment; existence check via `Path.is_file()`. Rejections raise `MediaNotFound("Invalid media path")` / `MediaNotFound("Media file not found")` — the detail distinguishes traversal from missing file, and the router maps both to 404 anyway.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && uv run pytest app/tests/test_media_storage.py -v`. Expected: all pass.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/services/media_file_storage.py app/tests/test_media_storage.py && uv run ruff check app/services/media_file_storage.py app/tests/test_media_storage.py --ignore B008 && uv run mypy app/services/media_file_storage.py --strict
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/media_file_storage.py backend/app/tests/test_media_storage.py
git commit -m "feat: add MediaFileStorage with resolve() containment"
```

# PART C — Fused rewrites

Part C moves each module to the invariant shape in one commit apiece — repo + service + router + schemas + models together, because mid-rewrite split commits would leave `AttributeError`-broken checkouts (the book plan's Task 5 lesson: one commit keeps every point in history importable and runnable, which matters because `git pull && cat STATE.md` is the cross-machine resume path). Task order is bottom-up: tag first (its `get_or_create_by_names` is consumed by both media services), then audio, then video. Each fused task follows the same rhythm: **update the Part A pins to the invariant world (auth headers, deliberate pin flips), write the bug-fix probes red-first against legacy, implement, witness green.**

### Task 6: Tag fused rewrite — 2.0 repo + service + router auth

> **Lint/type gate:** all touched files end at 0 ruff + 0 `mypy --strict`; `tag_repo.py`'s 2 mypy rows and `tag_router.py`'s 1 row are this task's debt to clear (Annex).

**Files:**
- Rewrite: `backend/app/repositories/tag_repo.py`
- Create: `backend/app/services/tag_service.py`
- Rewrite: `backend/app/api/tag_router.py`
- Modify: `backend/app/repositories/__init__.py` (keep the `TagRepo` export in `__all__`)
- Test: `backend/app/tests/test_tag_repo.py`, `backend/app/tests/test_tag_api.py`

**Interfaces:**
- Produces:
  - `TagRepo.get_all_tags() -> list[Tag]` — 2.0 `select(Tag)`, no `query()`, no `joinedload` (no eager relationship needs here)
  - `TagRepo.get_or_create_by_names(names: list[str]) -> list[Tag]` — **preserves the legacy semantics exactly** (Tasks 1–3 pins are the contract): case-insensitive match against stored names; an existing tag is reused with its **stored case**; a missing name creates a new tag **lowercased**; duplicates within `names` collapse; output order is first-occurrence order. One hint for the correct non-`ilike` form: `select(Tag).where(func.lower(Tag.name).in_({n.strip().lower() for n in names}))` — matching by lowercased value reproduces `ilike`'s case-insensitive match in one query, and the input loop (`seen`-set) reproduces the append/check/append order. The **old per-name `Tag.name.ilike(...)` loop moves out of the routers and dies here; do not keep two implementations**
  - `TagRepo.get_tag_by_id` and `create_tag` are **deleted** — dead (verified: no caller in the tree). Their Task 3 pins (1..2) are updated: `get_tag_by_id` test cases are removed, `create_tag` normalization is covered by... nothing (the validator tests live with `TagCreate` itself in `tag_schema` — which this plan does not touch; Task 3's case 3 therefore becomes a **deleted pin**, recorded in the commit message)
  - `TagService(db: Session)` with `list_tags() -> list[TagRead]` — wraps `get_all_tags`; domain trivial (no errors to map), this is the layering seam Invariant 1 demands
  - `tag_router` — `GET /tags/` keeps prefix + response model; gains `Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student]))` and calls `TagService(db).list_tags()`. The router holds **no** queries
- Consumes: `app.models.Tag`, `TagRead` (`tag_schema` untouched), `RoleChecker`/`RoleEnum` from `app.dependencies.auth`, `app.models.role_enum`

**Why (learning):** this is the Invariant-1 seam for tag logic: from Task 7 on, both media routers call tag lookups through the service layer's single 2.0 repo method instead of their inline per-tag `query().ilike()` loops. Getting the case semantics right *now* — and pinned — is what keeps Tasks 1–2's case-4/5 pins green after Task 7 rewrites the call sites.

- [ ] **Step 1: Update the Part A pins to the invariant world**

In `backend/app/tests/test_tag_api.py`, add the auth probe and wrap existing requests:
1. All existing `client.get("/tags/")` calls gain `headers=auth_headers(token)` where `token = login(client, "admin", password)` per the helper idiom from `test_auth.py` (module-level import: `from app.tests.conftest import setup_admin, login, auth_headers` — safe since S1; check `test_auth.py` for the exact fixture dance: `setup_admin(client, setup_paths)` returns the password, then `login`)
2. Add: `client.get("/tags/")` **without** a token → `401`

In `backend/app/tests/test_tag_repo.py`:
3. Delete the `get_tag_by_id(999999) -> None` and the uniqueness cases (dead-method pins; see Interfaces)

Run: `cd backend && uv run pytest app/tests/test_tag_api.py app/tests/test_tag_repo.py -v`. Expected: the `401` probe **fails** (legacy returns 200 — red for the right reason); the deleted cases simply no longer exist; anything else failing means the pin update drifted.

- [ ] **Step 2: Rewrite `tag_repo.py`** per the Interfaces — 2.0 `select()`, `get_or_create_by_names`, dead methods deleted.

- [ ] **Step 3: Create `tag_service.py`** per the Interfaces — `TagService.list_tags()`.

- [ ] **Step 4: Rewrite `tag_router.py`** per the Interfaces — RoleChecker, service call, zero queries.

- [ ] **Step 5: Run the suite to verify green**

Run: `cd backend && uv run pytest app/tests/test_tag_repo.py app/tests/test_tag_api.py -v`. Expected: all pass — including the `401` probe, which is now green because the endpoint requires auth.

- [ ] **Step 6: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/test_tag_repo.py app/tests/test_tag_api.py && uv run ruff check app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py app/tests/test_tag_repo.py app/tests/test_tag_api.py --ignore B008 && uv run mypy app/repositories/tag_repo.py app/services/tag_service.py app/api/tag_router.py --strict
```

Expected: 0 ruff, 0 mypy on these files (Annex rows struck).

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/tag_repo.py backend/app/services/tag_service.py backend/app/api/tag_router.py backend/app/tests/test_tag_repo.py backend/app/tests/test_tag_api.py
git commit -m "refactor: tag module — 2.0 repo, service layer, auth; drop dead get_tag_by_id/create_tag"
```

---

### Task 7: Audio fused rewrite — schema/model names, service, router, fixes

> **Lint/type gate:** `audio_router.py` (19), `audio_repo.py` (5), `audio_schema.py` (0), `models/audio.py`+`audio_tag.py` (2) all end at 0/0. This is the biggest single task — the structure is book Task 5's: three clearly separated steps (repo+model → service → router), one commit at the end.

**Files:**
- Rewrite: `backend/app/repositories/audio_repo.py`
- Create: `backend/app/services/audio_service.py`
- Rewrite: `backend/app/api/audio_router.py`
- Modify: `backend/app/schemas/audio_schema.py`
- Modify: `backend/app/models/audio.py`, `backend/app/models/audio_tag.py`
- Modify: `backend/app/repositories/__init__.py` (add `AudioRepo` to the exports)
- Test: `backend/app/tests/test_media_stream.py` (Create — audio cases), `test_audio_api.py`, `test_audio_repo.py` (Modify)

**Interfaces:**

*Models* (`models/audio.py`, `audio_tag.py`) — 2.0 `Mapped[]`/`mapped_column()`, **columns and table names identical** (no migration): `id` (Integer PK indexed), `title` (String, non-null), `description` (String, null), `file_path` (String, non-null), `created_at` (DateTime `default=lambda: datetime.now(UTC)`), `deleted_at` (DateTime null default None); `tags` relationship via `"audio_tags"` string unchanged, `back_populates`. `AudioTag`: `id` PK, `audio_id`/`tag_id` FKs with `ondelete="CASCADE"`, `UniqueConstraint("audio_id", "tag_id")`. `models/__init__.py` needs **no edit** — `Audio`/`AudioTag` already exported.

*Schemas* (`audio_schema.py`) — rename only:
- `AudioCreate` — `title: str`, `description: str | None = None`, `file_path: str` (was `Audio_Create`)
- `AudioView` — `id`, `title`, `description`, `audio_url: str`, `tags: list[TagRead] = []`, `model_config = ConfigDict(from_attributes=True)` (was `Audio_View`)

*Repo* (`audio_repo.py`) — `class AudioRepo`, 2.0 `select()`:
- `create(self, audio_create: AudioCreate) -> Audio` — `add`/`commit`/`refresh` (commit-stays-in-repo, legacy semantics)
- `get_by_id(self, audio_id: int) -> Audio | None` — with `options(selectinload(Audio.tags))`
- `list_active(self) -> list[Audio]` — `deleted_at.is_(None)`, `selectinload(Audio.tags)`, **no `ORDER BY`** (pin: unordered; Part A asserts sets)
- `soft_delete(self, audio_id: int) -> Audio | None` — sets `deleted_at = datetime.now(UTC)`, commit, refresh; `None` when missing (missing is a return value, not an exception — book repo convention)
- `update_audio` **deleted** (dead — the router's inline update was the only caller and it mutates the loaded row itself)

*Service* (`audio_service.py`) — `class AudioService`, `__init__(self, db: Session)`:
- `list_tracks() -> list[AudioView]`
- `upload(self, file_bytes: bytes, filename: str, tag_names: list[str]) -> AudioView` — `validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)` → `MediaFileStorage(settings.AUDIO_DIR).save(...)` → `AudioRepo.create` with title = filename stem minus extension → `TagRepo.get_or_create_by_names(tag_names)` → link → `AudioView`. Description `None` (legacy). **No HTTP types; raises only `MediaNotFound`/`InvalidMediaFile`**
- `upload_multiple(self, files: list[tuple[bytes, str]]) -> list[AudioView]` — **validate every file before the first byte is written or the first row committed** (the validate-then-mutate fix; one commit for the whole batch)
- `update(self, audio_id: int, *, title: str | None, description: str | None, tag_names: list[str] | None) -> AudioView` — `None` means untouched (legacy tri-state: `None` = leave, `[]` = clear, list = replace); tag replacement semantics pinned in Part A case 10-11
- `soft_delete(self, audio_id: int) -> AudioView` — missing id → `raise MediaNotFound("Audio not found")` (verbatim legacy detail; router maps 404)
- `resolve_stream(self, audio_id: int) -> tuple[Path, str]` — row missing → `MediaNotFound("Audio not found")`; file resolution via `storage.resolve` (traversal + existence → `MediaNotFound`); media type from the legacy extension map (default `audio/mpeg`)
- Internals may hold `settings` and construct the storage once in `__init__`; the service raises **domain exceptions only** (Invariant 2)

*Router* (`audio_router.py`) — prefix `/audio`, tags `["audio"]`:
- DI: `get_audio_service(db: Session = Depends(get_db)) -> AudioService`
- **Every endpoint**: `user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student]))`
- `GET /` → `list_tracks`
- `POST /upload` (multipart `file`, `tags: str = Form("")`) → parse comma-separated `tag_names` (strip, drop empties — same split as legacy `audio_router.py:61-63`) → `upload`; 400 via `InvalidMediaFile`, 404 via `MediaNotFound`, `IntegrityError` → 400
- `POST /upload_multiple` (`files: list[UploadFile]`) → read into `list[tuple[bytes, str]]` → `upload_multiple` — no tags field (legacy contract)
- `PATCH /{audio_id}` (form params `title`/`description`/`tags` — legacy shape) → `update`; parse `tags` only when not `None`
- `DELETE /{audio_id}` → `soft_delete` → `AudioView`
- `GET /stream/{audio_id}` → **RFC 7233** per the table in Task 7 Step 3; 404 on `MediaNotFound`
- The router holds **no queries, no `open()`, no tag logic**

**Why (learning):** every one of the six fixes here was pinned as a bug in Part A: the delete-500 (`audio_repo.py:22`), the CWD-relative literal (`audio_router.py:91`), the partial-commit loop, the uncontained `open()`, the missing Range handling, and the absence of auth. Fusing repo+service+router+schema+model into one commit is what keeps history importable — split commits would break `GET /audio/` partway through. The pins from Task 1 are the safety net: run the same file, watch only the deliberate flips go red, and fight the rest to green.

- [ ] **Step 1: Update Part A pins + write the red-first probes**

**Modify** `backend/app/tests/test_audio_api.py`:
1. Add `auth_headers(token)` to every request (helper idiom as Task 6 Step 1)
2. Add a parametrized 401 guard: every path — `GET /`, `POST /upload`, `POST /upload_multiple`, `PATCH /{id}`, `DELETE /{id}`, `GET /stream/{id}` — without a token → `401`
3. Flip bug pins to their fixed expectations (these must be **red on legacy** — run before implementing):
   - case 14 (DELETE missing): `client.delete("/audio/999999", headers=...)` waits for `404` (legacy: raises `AttributeError`)
   - case 8 (partial-commit): after the failing two-file `upload_multiple`, `GET /audio/` returns **zero** rows, and with `monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)` **zero** files exist (legacy: one row + bytes under the literal path)
   - case 18 (missing file): stream 404 (legacy: raises `FileNotFoundError`)
   - case 17 (quirk): stays — stream of a soft-deleted track remains 200
   - case 5 (tag reuse): stays green by `get_or_create_by_names` semantics

**Modify** `backend/app/tests/test_audio_repo.py`:
4. case 3 flips: `AudioRepo(db).soft_delete(999999)` → `None` (legacy `Audio_Repo.delete_audio` raises); the `AttributeError` pin is deleted
5. `delete_audio` calls become `soft_delete`; class import becomes `AudioRepo`

**Create** `backend/app/tests/test_media_stream.py` — the RFC 7233 table for `/audio/stream/{id}` (seed a row whose `file_path` points at a real `tmp_path` file; 1000 bytes of deterministic content):

| Request header | Expected status | Expected body / headers |
|---|---|---|
| (none) | 200 | full body, `Accept-Ranges: bytes` |
| `Range: bytes=0-99` | 206 | bytes 0..99, `Content-Range: bytes 0-99/1000` |
| `Range: bytes=500-` | 206 | bytes 500..999, `Content-Range: bytes 500-999/1000` |
| `Range: bytes=-500` | 206 | last 500 bytes, `Content-Range: bytes 500-999/1000` |
| `Range: bytes=20-10` (start>end) | 416 | `Content-Range: bytes */1000` |
| `Range: bytes=1000-` (start≥size) | 416 | `Content-Range: bytes */1000` |
| `Range: bytes=0-99,200-299` (multi) | 200 | full body |
| `Range: garbage` (malformed) | 200 | full body |

**Interface note for the implementer — this is the whole Range contract:** ranges are inclusive; suffix ranges (`-500`) are legal and must not 500 like the book's original plan did; an out-of-range **start** is unsatisfiable → 416, not clamped; `Accept-Ranges: bytes` on every response. The book spec's table (`2026-08-16-book-refactor-design.md` §126–138) is the authoritative copy of this table. All stream requests carry `auth_headers` (streams are role-gated like everything else).

- [ ] **Step 2: Run the modified pin files to verify they fail red**

Run: `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py app/tests/test_media_stream.py -v`

Expected red, each for the right reason:
- 401 guards → legacy returns 200, probe fails on `assert 401`
- DELETE-missing → `AttributeError` raised (not a 404)
- partial-commit → 1 row survives (assert 0 fails)
- stream-missing-file → `FileNotFoundError`
- every Range case → 200 with full body and no `Accept-Ranges` (assert 206 / header fails)

Everything **else** must stay green — green pins on legacy are the point of Part A. Any pin that fails here was written wrong in Task 1; fix the pin, record it.

- [ ] **Step 3: Implement — models + schemas + repo + service + router**

Follow the Interfaces block exactly, in this order (gate after each):
1. `models/audio.py`, `models/audio_tag.py` → 2.0; run `uv run pytest app/tests/test_audio_repo.py -v` — the auth-free repo pins stay green, `soft_delete`-flip cases now pass
2. `schemas/audio_schema.py` renames
3. `repositories/audio_repo.py` → `AudioRepo` per Interfaces
4. `services/audio_service.py` per Interfaces
5. `api/audio_router.py` per Interfaces — the Range bit is the only novel code; hint: parse the `Range` header with a regex (`bytes=(\d*)-(\d*)`), handle the three shapes (start-end, suffix `-N`, open-end `N-`), reject multi/garble → 200 full, slice bytes, and return `StreamingResponse(iter([chunk]), media_type=..., status_code=..., headers={"Content-Range": ..., "Accept-Ranges": "bytes"})`
6. `repositories/__init__.py` — add `AudioRepo` export

- [ ] **Step 4: Run the suite to verify green**

Run: `cd backend && uv run pytest app/tests/test_audio_repo.py app/tests/test_audio_api.py app/tests/test_media_stream.py -v`

Expected: all pass — the probes that were red in Step 2 are now green, and every untouched pin stayed green.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py app/tests/test_audio_api.py app/tests/test_audio_repo.py app/tests/test_media_stream.py && uv run ruff check app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py app/tests/test_audio_api.py app/tests/test_audio_repo.py app/tests/test_media_stream.py --ignore B008 && uv run mypy app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/repositories/__init__.py --strict
```

Expected: 0/0 on all (Annex audio rows struck; `models/tag.py`'s 1 row is Task 6's and was cleared there).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/audio.py backend/app/models/audio_tag.py backend/app/repositories/audio_repo.py backend/app/services/audio_service.py backend/app/api/audio_router.py backend/app/schemas/audio_schema.py backend/app/repositories/__init__.py backend/app/tests/test_audio_api.py backend/app/tests/test_audio_repo.py backend/app/tests/test_media_stream.py
git commit -m "refactor: audio module — 2.0, service layer, auth, Range, delete-404, anchored paths"
```

---

### Task 8: Video fused rewrite — mirror of audio + the whitelist fix

> **Lint/type gate:** `video_router.py` (15), `video_repo.py` (2), `models/video.py`+`video_tag.py` (2) end at 0/0.

**Files:**
- Rewrite: `backend/app/repositories/video_repo.py`
- Create: `backend/app/services/video_service.py`
- Rewrite: `backend/app/api/video_router.py`
- Modify: `backend/app/schemas/video_schema.py` (renames + delete `Video_Delete`)
- Modify: `backend/app/models/video.py`, `backend/app/models/video_tag.py`
- Modify: `backend/app/repositories/__init__.py` (add `VideoRepo`)
- Test: `backend/app/tests/test_media_stream.py` (Modify — video parametrization), `test_video_api.py`, `test_video_repo.py` (Modify)

**Interfaces** — the complete mirror of Task 7 with the video deltas:

- Models: `Video`/`VideoTag` → 2.0, identical columns, `"video_tags"`/`"videos"` relationship names
- Schemas: `VideoCreate`, `VideoView` (renames); **`Video_Delete` deleted** (dead — verified no callers)
- `VideoRepo` — `create`/`get_by_id`/`list_active`/`soft_delete`, same shapes as `AudioRepo`; `file_path` is str; `description` nullable; **no `VideoRepo.update`** (same dead-method removal; the service mutates the loaded row)
- `VideoService(db: Session)`:
  - `list_videos() -> list[VideoView]`
  - `upload(self, file_bytes: bytes, filename: str, *, title: str, description: str | None, tag_names: list[str]) -> VideoView` — **`title` is a required parameter** (legacy Form `...`), `validate_media(filename, allowed=ALLOWED_VIDEO_EXTENSIONS)` — the **new whitelist** (fips Task 2's quirk pin) — storage `MediaFileStorage(settings.VIDEO_DIR)`, tag link via `TagRepo.get_or_create_by_names`
  - `upload_multiple(self, files: list[tuple[bytes, str]]) -> list[VideoView]` — validate-all-first (same fix as audio; legacy has no validation at all, so this is doubly new)
  - `update(...)` / `soft_delete(...)` / `resolve_stream(...) -> tuple[Path, str]` — mirrors: `MediaNotFound("Video not found")` (verbatim), storage media type via `mimetypes.guess_type(path)` with `application/octet-stream` fallback (legacy `video_router.py:145-147` — pin preserved)
- Router: prefix `/videos`, `RoleChecker([admin, teacher, student])` everywhere, form `title: str = Form(...)` / `description: str | None = Form(None)` / `tags: str = Form("")`, RFC 7233 Range (share the implementation shape from Task 7 — or one helper: the book plan's "cross-module helper → a service" rule; if you extract it, it lives in `audio_service.py`'s sibling or a small shared module named per AGENTS convention — do **not** create a `utils` grab-bag)
- Consumes: `ALLOWED_VIDEO_EXTENSIONS` (Task 4), `TagRepo.get_or_create_by_names` (Task 6)

**Why (learning):** the video module is the audio module plus three deltas — required form title, the new whitelist (a behavior *fix*, unlike audio's keep), and `mimetypes` content typing. The Part A pins drawn to those deltas (Task 2 cases 2-4, 7, 11) are what a mindless copy-paste of Task 7 would break — the suite, not the plan, is the referee.

- [ ] **Step 1: Update Part A pins + write the red-first probes**

**Modify** `backend/app/tests/test_video_api.py`:
1. Auth headers on every request + the parametrized 401 guard (all seven paths)
2. Flip/change:
   - case 4 (`.txt` accepted) → expect `400`, detail `File type .txt not allowed` — **red on legacy** (200 today)
   - case 7 (partial-commit shape) → with the whitelist in place, a second-file failure must leave **zero** rows and zero bytes under `monkeypatch.setattr(settings, "VIDEO_DIR", tmp_path)` — red on legacy (both rows + 200)
   - DELETE-missing → `404` (legacy `AttributeError`)
   - stream-missing-file → `404` (legacy `FileNotFoundError`)
   - upload_multiple gains **no** tags parameter (unchanged contract)
3. **Modify** `backend/app/tests/test_video_repo.py`: `VideoRepo` + `soft_delete`-returns-`None` flips, `AttributeError` pin deleted
4. **Modify** `backend/app/tests/test_media_stream.py`: parametrize the RFC 7233 table over both prefixes — `("/audio/stream/", "/videos/stream/")` — seeding each row's file under the corresponding monkeypatched dir. The video cases are **red on legacy** (200 full body, no `Accept-Ranges`)

- [ ] **Step 2: Run to verify red**

Run: `cd backend && uv run pytest app/tests/test_video_repo.py app/tests/test_video_api.py app/tests/test_media_stream.py -v`

Expected red: 401 guards (`200` today), `.txt` upload (`200` today), partial-commit (`200` + 2 rows today), DELETE-missing (`AttributeError`), missing-file (`FileNotFoundError`), all video Range rows (200 full today). Audio Range rows and every untouched pin stay green.

- [ ] **Step 3: Implement** — the Task 7 sequence in miniature: models (`video.py`, `video_tag.py`), schemas (renames + delete `Video_Delete`), repo (`VideoRepo`), service (`VideoService` incl. whitelist validation), router (auth + Range + mapping), `__init__` export. Fill the deltas exactly per the Interfaces.

- [ ] **Step 4: Run to verify green**

Run: `cd backend && uv run pytest app/tests/test_video_repo.py app/tests/test_video_api.py app/tests/test_media_stream.py -v`. Expected: all pass.

- [ ] **Step 5: Format, lint, type-check**

```bash
cd backend && uv run ruff format app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/test_video_api.py app/tests/test_video_repo.py app/tests/test_media_stream.py && uv run ruff check app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py app/tests/test_video_api.py app/tests/test_video_repo.py app/tests/test_media_stream.py --ignore B008 && uv run mypy app/models/video.py app/models/video_tag.py app/repositories/video_repo.py app/services/video_service.py app/api/video_router.py app/schemas/video_schema.py app/repositories/__init__.py --strict
```

Expected: 0/0 on all (video rows struck; the Annex is fully cleared by Task 8 except other plans' callouts).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/video.py backend/app/models/video_tag.py backend/app/repositories/video_repo.py backend/app/services/video_service.py backend/app/api/video_router.py backend/app/schemas/video_schema.py backend/app/repositories/__init__.py backend/app/tests/test_video_api.py backend/app/tests/test_video_repo.py backend/app/tests/test_media_stream.py
git commit -m "refactor: video module — 2.0, service layer, auth, whitelist, Range, delete-404"
```

---

### Task 9: Final gate — definitions of done, repo-wide

> **Lint/type gate:** this task's sweep verifies, it does not rewrite. Any file it touches for a genuine fix joins its owner's commit convention.

**Files:** (verification only, unless a fix is genuinely needed)

**Why (learning):** the book plan's Task 6 gate analogues, applied here: a refactor plan is done when (1) every touched file is 0/0, (2) the full suite is green, (3) the bug inventory is closed, (4) the graph is fresh, and (5) the plan itself says done — in the same commit as the last code change.

- [ ] **Step 1: Full-suite smoke, format pass**

```bash
cd backend && uv run ruff format . && uv run pytest -v
```

Expected: full suite passes — `test_auth.py` plus the nine new files. If `ruff format .` reformats a file outside this plan's map (pre-existing deviation), include it in the final commit and note it; do not chase unrelated debt.

- [ ] **Step 2: Bug-inventory sweep**

```bash
cd backend && grep -n 'uploads/audio' app/ --include='*.py' | grep -v tests || echo "no literal upload paths remain"
cd backend && uv run ruff check app --ignore B008
```

Expected: no literal `"uploads/audio"` outside tests; ruff output limited to ledger rows owned by the hygiene plan (auth/config/database files) and the book plan (`book_service.py`, `book_router.py`, `book_repo.py`, `book_schema.py`, book models) — the Annex callouts. If a remaining error is in a file this plan touched, it is a failed gate: fix it.

- [ ] **Step 3: `mypy --strict` on the plan's files**

```bash
cd backend && uv run mypy app/models/audio.py app/models/audio_tag.py app/models/video.py app/models/video_tag.py app/models/tag.py app/repositories/audio_repo.py app/repositories/video_repo.py app/repositories/tag_repo.py app/services/audio_service.py app/services/video_service.py app/services/tag_service.py app/services/media_errors.py app/services/media_validator.py app/services/media_file_storage.py app/api/audio_router.py app/api/video_router.py app/api/tag_router.py app/schemas/audio_schema.py app/schemas/video_schema.py app/repositories/__init__.py --strict
```

Expected: 0 errors — the Annex is fully struck for this plan. Do **not** run `mypy . --strict` as a gate; other plans' rows are out of scope (Annex callouts). If a changed file surfaces a pre-existing error in an untouched dependency, log it in STATE.md; do not fix it here.

- [ ] **Step 4: Regenerate the knowledge graph**

```bash
graphify update .
```

Expected: clean run (AST-only). Dirty graphify-out files are fine; this keeps the god nodes current with the new service modules — `graphify query "audio service"` should return `audio_service`/`video_service`/`tag_service`.

- [ ] **Step 5: Tick this plan's boxes and record in STATE.md**

Flip every checked-complete task above and this one; note the Annex's struck rows and the surviving callouts (hygiene/book plans). The `state` skill owns STATE.md — invoke it via the completion phrases per AGENTS.md ("verify and commit").

- [ ] **Step 6: Final commit**

```bash
git add docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md STATE.md
git commit -m "chore: audio/video/tag refactor complete — all tasks ticked, graph refreshed"
```

## Learning Annex

1. **Characterization pins are witnessed green first — the inverse of red-green.** A pin is a measurement of reality, not a wish. It fails → the pin was wrong (or the code changed underneath it); it passes → behavior is now *owned*. Bugs get pinned as-broken (`pytest.raises(AttributeError)`) so the fix is a deliberate flip with a red-first probe, not an accident the suite never noticed. The 2026-08-24 TDD decision's two-track order — pins green, fixes red-first — is the whole method; the book plan's tasks were all red-first because nothing legacy existed to pin there.

2. **`TestClient(raise_server_exceptions=True)` surfaces 500s as exceptions — a feature for pinning, a trap for asserting.** The conftest's client raises `AttributeError`/`FileNotFoundError` instead of returning 500. Task 1's bug pins lean on that; the flip probes must not — the fix turns the raise into a real 404 response.

3. **The uuid prefix incidentally defeats write-side traversal, and that is not a substitute for read-side containment.** `{uuid4}_{filename}` cannot escape the media dir regardless of `filename` content (the `uuid_` prefix makes every first segment harmless) — but the DB row is the untrusted input on the read path, and a poisoned row 500s-and-worse today because `open(file_path)` has no gate. `resolve()` centralises the check (book lesson 2 re-learned for media).

4. **`ilike` semantics are a two-sided coin: case-insensitive *match*, first-seen *storage*.** An existing `"Math"` row is found by `tags="MATH"` and re-used as `"Math"`; a *new* name is stored lowercased. `get_or_create_by_names` reproduces both halves with `func.lower(Tag.name).in_(...)` — the queries are gone from the routers, the behavior is not.

5. **validate-then-mutate applies per *batch*, not per item.** The `upload_multiple` loops committed file 1 before discovering file 2 was invalid — the durable-signature of the bug was a committed row whose client got a 400. The fix validates every member of the batch before the first byte hits disk; one commit, one transaction, all-or-nothing.

6. **A response shape is a security surface.** `DELETE /audio/{id}` returned the raw model — absolute server paths for `file_path` in the body. The pins assert the *intended* view contract (`AudioView`), not the incidental leak; passing through the view layer is the fix. (This is why the Part A pins were written to the user-visible contract, not `jsonable_encoder` output.)

7. **A bug can make the test suite un-writable — treat that as evidence.** The CWD-relative literal at `audio_router.py:91` means `upload_multiple` pins cannot assert on the filesystem at all (bytes land in whichever CWD pytest happens to use). The fix is what makes the meaningful test possible; until then, pin the DB side and note why.

8. **One commit per fused module keeps every checkout importable.** `git pull && cat STATE.md` is the resume path; a commit where `audio_router` imports `AudioRepo` while the old `Audio_Repo` is still called is a broken checkpoint that buys nothing. The three-file suite of repo+service+router lands together — Task 5's book lesson, reused twice.

## Deferred Work — preserved for a later pass

Nothing here is lost; verified open on 2026-08-26.

### D1: Directory rename `uploads/vids` → `uploads/videos`
Cosmetic but touches on-disk layout, the Dockerfile `mkdir`, `config.py`'s `VIDEO_DIR`, and existing DB `file_path` values. Needs a data migration (hygiene annex D4, unchanged). State amendment needed in main.py lifespan if the dir literal appears anywhere beyond `settings.VIDEO_DIR`.

### D2: Orphan `Tag` rows
Media PATCH replaces tag sets without touching `Tag` rows; `get_or_create_by_names` never deletes. Rows accumulate. Books has the same behavior. A future cleanup pass could delete tags with no associated rows (join-count = 0) behind a red-first test.

### D3: Media metadata / cover extraction
Books got `EpubMetadataReader` + `CoverGenerator`. Audio/video have no equivalent (no title/artist extraction from ID3, no poster thumbnails for video). Resurrection mirrors book Tasks 3–4 if wanted; the storage/validator seams built here are the place it plugs in.

### D4: Auth tightening (student read-only split)
This plan gates every endpoint at "any authenticated user" per the approved decision. If a product requirement later wants students read-only (upload/PATCH/DELETE restricted to admin+teacher), the seam already exists — `RoleChecker([...])` per-endpoint lists — and only the router Depends lines change. Deferred deliberately; requires a product decision, not a refactor.

## Self-Review

- **Spec coverage (TDD workflow spec, approved 2026-08-24):** decision 1 (TDD binding) — plan written red-green with characterization exception per decision 2, which is itself the spec's mechanism §21–27 → Part A + red-first probes ✓; decision 3 is already landed in AGENTS.md (no work here) ✓; decision 4 (tag included) → Task 6 ✓. Deferred list §73–77: service layers (Inv 1) → Tasks 6–8 ✓; naming → Tasks 6–8 ✓; SQLAlchemy 2.0 (Inv 4) → Tasks 6–8 models+repos ✓; delete-missing 500s → Tasks 7–8 probes ✓; full test suites (Inv 5) → Part A + Part C ✓. Inv 3 residue (audio_router.py:91) → Task 7 ✓.
- **Inherited-position coverage:** book D1 delete-500 ✓ (T7/T8), book D1 tag-service ✓ (T6), book D3 TagRepo 2.0 ✓ (T6), hygiene D2 ✓, hygiene D3 models ✓ (T7/T8); hygiene D4 deliberately re-deferred (D1 of the annex) ✓.
- **Placeholder scan:** no TBD/TODO; every step has an exact command, expected output, or a named contract. Characterization cases are itemized lists the implementer writes bodies for — deliberate per the approved learner format, not elision.
- **Type consistency:** `AudioRepo`/`VideoRepo` method set identical (create/get_by_id/list_active/soft_delete) across Tasks 7–8 ✓; `MediaFileStorage` constructor `(save_dir)` — Task 5 produces, Tasks 7–8 construct with `settings.AUDIO_DIR`/`settings.VIDEO_DIR` ✓; `validate_media(filename, *, allowed)` — Task 4 produces, Tasks 7–8 consume with the two whitelists ✓; `MediaNotFound`/`InvalidMediaFile` used by storage+validator+services, mapped only in routers ✓; `TagRepo.get_or_create_by_names(list[str]) -> list[Tag]` — Task 6 produces, Tasks 7–8 consume ✓; `resolve_stream -> tuple[Path, str]` consumed by both routers ✓; pinned detail strings (`Audio not found`, `Video not found`, `File type .{ext} not allowed`) verbatim across tasks ✓; `schemas/tag_schema.py` untouched while `TagRead` is consumed everywhere ✓.
- **Known risks:** (1) Task 7 is the largest unit — six files, six fixes; mitigated by the gate-after-each-file ordering in Step 3 and the one-commit rule; (2) the auth change is behavior-breaking for any client that calls media endpoints without a token — deliberate, user-approved 2026-08-26, recorded in Global Constraints; (3) the video whitelist flips Task 2's quirk pin — the flip is the red-first probe, not a silent change; (4) `get_or_create_by_names` must reproduce `ilike` semantics exactly or Tasks 1–2 case-5 pins fail — that is the test that guards it; (5) Range streaming is subtle — the book spec's table is authoritative and the probe table in Task 7 covers all eight rows; (6) legacy DB rows holding old relative paths resolve via the save_dir-join branch in `resolve` — rows from the pre-S3 era may point at dead locations and 404 on stream, which is correct behavior (logged in STATE.md as known data state, not a bug); (7) models conversion produces no Alembic delta (columns identical) — if an autogenerate run disagrees, STOP and compare column-by-column before touching schema.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-26-audio-video-tag-refactor.md`. Two execution options:

1. **Learner mode (current convention)** — you implement each task from the contracts, samples, and hints; the agent reviews diffs and runs `/audit` + `/verify` before each commit, and never writes the implementation.
2. **Subagent-Driven** — a fresh subagent per task with two-stage review; each task brief must be self-contained since the subagent sees nothing of this conversation (the Interfaces blocks above are the brief material).

Which approach?
