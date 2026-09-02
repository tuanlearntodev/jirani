# Media Refactor + nginx Streaming + Criteria Entities — Design (2026-09-01)

> **Status:** approved 2026-09-01, revised same day — **audio module removed from scope** (user decision 2026-09-01: books + video only; audio remains legacy pending its own future plan). Governs the implementation plan of the same date. Where a plan and this spec disagree, the spec wins.
>
> **Supersedes:** `2026-08-16-book-refactor-design.md` (deleted by this project) and the streaming/architecture halves of the two plans it replaces (`2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md`). The TDD process spec `2026-08-24-tdd-workflow-design.md` is **not** superseded — it governs how the plan is executed.
>
> **React handoff (locked 2026-09-01):** this plan plus React integration start together when it closes — see §7 Deferred + §9 React handoff outcome.

## 1. Goal

Three changes, one project:

1. **Refactor books and video** to the invariant shape (service layer, SQLAlchemy 2.0, tests, naming). **Audio is explicitly out of scope** — user decision 2026-09-01; it stays legacy (untested, Python-streamed, zero-auth) until its own future plan picks it up. Its known violations remain named in `AGENTS.md`'s violating-today column.
2. **Replace hand-rolled Python streaming with nginx** via X-Accel-Redirect, for real performance and correct RFC 7233 behavior (books + video; audio's stream remains the legacy generator until its deferral is picked up).
3. **Promote `author`, `level`, and `genre` to tag-like entities** (single-valued FKs on `books`) with a data-preserving Alembic migration, renaming `book_type` → `genre` to kill the file-format conflation.

## 2. Why nginx over Python streaming

The two in-scope routers serve every byte through a Python generator (`book_router.py` has three streaming endpoints; `video_router.py` one) — and today `audio_router.py:170-177` does the same, deliberately left legacy. Python streaming is the worst pattern in the codebase and the slowest:

- **Performance.** Python `StreamingResponse` crosses the Python/C boundary per chunk, holds an event-loop slot, and competes with request handling. nginx serves via `sendfile(2)` — the kernel moves bytes disk→socket without userspace. On the deployment target (Rock 5B, SD/eMMC), this is the difference between "works" and "falls over when a class opens the same video."
- **Correctness for free.** nginx implements RFC 7233 natively — single-range 206/416, suffix ranges for Safari/pdf.js, `If-Range`. The two replaced plans each carried a ~100-line hand-rolled range parser and an 8-row test table; both are deleted.
- **Layering.** FastAPI does the security decision (auth + path containment), nginx does the byte-serving. Each layer does the one thing it is good at. This is the standard protected-media pattern (Django `X-Sendfile`, Rails `X-Accel-Redirect`).

The honest cost: an nginx config to maintain, and Range behavior leaves the pytest suite (mitigated in §6).

## 3. nginx topology

`docker-compose.yml` gains an `nginx` service; the `backend` service stops publishing `8000` to the host. nginx is the **only** published port.

```
client → nginx:80
  ├── location /api/            → proxy_pass http://backend:8000/   (strip /api prefix)
  ├── location /media/          → internal; alias /srv/uploads/     (one location covers books/vids)
  └── location /static/covers/  → public static, alias /srv/uploads/covers/
```

The single `location /media/` with `alias /srv/uploads/` is a deliberate consolidation of the original three-location sketch: the redirect URIs the backend emits (`/media/books/…`, `/media/vids/…`) already carry the kind, and `alias` math maps each to the right on-disk directory. One internal location instead of three — same security boundary, less config to drift. **Scheduled follow-on:** plan Task 11 renames the `vids` dir and its redirect kind to `videos`; the `/media/` alias needs no change — the URI simply carries the new kind, and the `video.file_path` rows migrate alongside (physical file move first, then the data migration).

- `/media/*` locations are `internal` — reachable only via `X-Accel-Redirect`, never directly. This is the enforcement that media requires auth.
- `/static/covers/` is public (book covers are browsable assets). The `StaticFiles` mount in `main.py` is removed; nginx takes covers over. The `cover_url` computed field on `BookRead` (`/static/covers/{name}`) is unchanged — the URL prefix is identical, only the server behind it changes (FastAPI `StaticFiles` → nginx).
- Volumes: the host `./uploads` tree is mounted into **both** `backend` (read/write, at `/app/uploads`) and `nginx` (read-only, at `/srv/uploads`). One source of truth on disk.
- **React (locked, §9):** when the SPA arrives, it is served same-origin from `nginx` too — a `location /` `try_files $uri $uri/ /index.html` block serving `frontend/dist`, sitting alongside `/api/`, `/media/`, `/static/covers/`. The plan's Task 10 annex records this integration point so the SPA never needs CORS or a second server. Until then, `location /` falls through to `backend:8000` unchanged.

## 4. Criteria taxonomy

`author`, `level`, and `genre` become **single-valued foreign-key entities**, each mirroring `Tag` in shape (`models/tag.py:14-17`). Single-valued FK, **not** many-to-many — user decision 2026-09-01: a book has at most one author/level/genre today (YAGNI), and the migration is a 1:1 column conversion. (With audio out of scope, `author` exists on books only — the `audio.author_id` idea died with the scope cut.)

### New tables

```
authors (id PK, name UNIQUE NOT NULL, lower(name) index)
levels  (id PK, name UNIQUE NOT NULL, lower(name) index)
genres  (id PK, name UNIQUE NOT NULL, lower(name) index)
```

### `books` table delta (Alembic, data preserved)

| Old column | New column | Migration behavior |
|---|---|---|
| `author: str` | `author_id → authors.id` (nullable, `ON DELETE SET NULL`) | backfilled: distinct `lower(trim(author))` → `authors`, FK re-linked |
| `level: str` | `level_id → levels.id` (nullable, `ON DELETE SET NULL`) | backfilled the same way |
| `book_type: str` | **`genre_id → genres.id`** (nullable, `ON DELETE SET NULL`) | backfilled **only** for rows whose `book_type` is not a junk MIME value (`book_type NOT LIKE '%/%'`); junk discarded |

> **Display-case trade-off (locked):** backfilling with `lower(...)` stores author/level/genre names lowercased (`J.K. Rowling` → `j.k. rowling`), and `downgrade()` copies the lowercased form back — the round-trip is lossy. This is accepted: it matches `get_or_create_by_name`'s create-lowercased rule and keeps the entire entity surface case-normalized. The alternative (`DISTINCT ON (lower(name))` preserving first-seen case) was rejected 2026-09-01 to avoid two case rules in one system.
| `language: str` | unchanged | stays a plain indexed string column |
| `extension: str` | unchanged | file format lives here, untouched |

The `book_type` → `genre` rename is semantic, not cosmetic: today the column holds junk MIME values (`application/pdf`) from the old `file_type` conflation bug. The real file format is already carried by `extension`. Junk values are deliberately discarded, not converted.

### `video` table delta

None in the main pass — video gets tags only, no new criteria. **Follow-on (plan Task 13):** `poster_path` (nullable string) added with its own chained revision when video posters land.

### Entity semantics — "same as tags"

Each entity repo gets the tag pattern being added to `TagRepo`:

```
get_or_create_by_name(name: str) -> Author | Level | Genre
```

- Case-insensitive match (`func.lower(Entity.name) == name.strip().lower()`) reuses the existing row with its **stored case**.
- A missing name creates a new row, stored **lowercased**.
- Each entity gets a read-only listing endpoint (`GET /authors/`, `GET /levels/`, `GET /genres/`) shaped like today's `GET /tags/` (`tag_router.py:11-13`), `RoleChecker`-gated.
- **No PATCH/DELETE on entities.** Not a full feature — entities are created implicitly on upload/update and listed; that is the entire surface.

### Search

`BookSearchCriteria` becomes: `q, author, level, genre, language, tags, extension, metadata_`. Author/level/genre filters take a **name** (string), resolve it to an id case-insensitively, and filter on the FK column. An unknown name resolves to `None`, and the repo emits `WHERE false` (the filter matches zero rows) — searching for a nonexistent author returns zero books, not all books. Tag filtering is unchanged (OR semantics, `tags.any()`).

## 5. Module & service architecture

### New entity modules (three, identical shape)

```
models/        author.py, level.py, genre.py
schemas/       author_schema.py, level_schema.py, genre_schema.py   (EntityCreate/EntityRead)
repositories/  author_repo.py, level_repo.py, genre_repo.py         (get_or_create_by_name, list_all)
services/      author_service.py, level_service.py, genre_service.py (list() — thin layering seam)
api/           author_router.py, level_router.py, genre_router.py   (GET / only)
```

All models 2.0 `Mapped[]`, exported from `models/__init__.py` (Alembic sees them). All repos 2.0 `select()`, exported from `repositories/__init__.py`. Routers registered in `api/__init__.py` and `main.py`.

### Book module changes

- `models/book.py`: add `author_id`/`level_id`/`genre_id` FK columns and `author`/`level`/`genre` relationships; **drop** the `book_type` column.
- `schemas/book_schema.py`: `BookCreate`/`BookUpdate`/`BookUpload` take `author: str | None`, `level: str | None`, `genre: str | None` (names, not ids — the service resolves). `BookRead` exposes resolved names (`author: str | None` etc., via relationships). `BookSearchCriteria` gains `author`/`level`/`genre` name filters. The `cover_url` computed field moves to `BookRead` only (old plan Task 0, still correct).
- `repositories/book_repo.py`: 2.0 `select()`; search resolves names → ids and filters FK columns; `selectinload` for tags + the three new relationships.
- `services/book_service.py`: thin orchestration over the leaf modules; on create/update, resolve `author`/`level`/`genre` names via the three entity repos' `get_or_create_by_name` before building `BookCreate`.

### Video module (audio removed)

`Video`/`VideoTag` convert to 2.0 `Mapped[]` inside the fused video rewrite task; `Video` is schema-untouched otherwise (tags only). Tag module refactor (`TagRepo` 2.0 + `get_or_create_by_names` + `TagService` + router auth) is unchanged — the three new entity modules copy its exact shape. **Audio is untouched in this design** — `Audio`/`AudioTag`/`AudioRepo`/`audio_router` remain legacy 1.x with no service layer; the deferral is recorded in §7.

### Streaming endpoint — the X-Accel contract

The two in-scope media routers (books, videos) get an identically-shaped stream endpoint. The router **never opens a file** — it emits a header (Invariant 3):

```python
from urllib.parse import quote

@router.get("/{uid}/stream")
def stream(uid, svc=Depends(get_service), _=Depends(RoleChecker([admin, teacher, student]))):
    media_path, media_type = svc.resolve_stream(uid)   # raises BookNotFound/MediaNotFound
    accel = f"/media/{kind}/{quote(media_path.name)}"   # single safe filename, containment already enforced
    return Response(status_code=204, headers={
        "X-Accel-Redirect": accel,
        "Content-Type": media_type,
        "Accept-Ranges": "bytes",
    })
```

- `resolve_stream` (service) is the **only** place files are located: row missing → 404; `storage.resolve()` enforces traversal containment + existence (the C4 lesson, unchanged). It returns the resolved absolute `Path` and the media type. The redirect URI is built from `quote(media_path.name)` — the basename, percent-encoded. `quote()` is required, not cosmetic: video filenames are `{uuid4}_{original filename}` and book files `{uid}.{ext}`; a student upload like `my clip.mp4` puts a literal space into the header value — Starlette encodes response headers latin-1 (→ `UnicodeEncodeError` 500) or nginx's URI parse chokes on the raw space (→ 400/404). `quote()` percent-encodes; nginx unescapes before the `alias` lookup, so the byte sequence matches the on-disk name exactly. Nested paths cannot appear because the input is a basename.
- FastAPI returns **204 No Content**; nginx substitutes the file body. `Content-Type` is set by FastAPI (it knows the media type); nginx serves bytes + Range.
- Covers are **not** routed through this — they're public static on nginx (`/static/covers/`).

### Error mapping (Invariant 2, router-only)

`BookNotFound`/`MediaNotFound` → 404; `InvalidBookFile`/`InvalidMediaFile` → 400; `IntegrityError` → 400 (includes the entity unique-race). Entity repos raise nothing — `get_or_create_by_name` always succeeds or raises `IntegrityError`.

## 6. Migration & testing strategy

### Alembic migration (main-pass revision, data preserved — Part G chains two more)

The main pass carries **one** revision (below). Part G adds two chained revisions: Task 11's `file_path` rename (chained off this one) and Task 13's `video.poster_path` (chained off Task 11's). All three are hand-written; the empty-DB round-trip and the real-data check in Task 5f apply to this one, and Tasks 11/13 each repeat the round-trip.

```
upgrade():
  1. create authors / levels / genres (+ unique + lower() indexes)
  2. add books.author_id / level_id / genre_id FK columns
  3. backfill authors/levels from distinct trimmed lower(strings); re-link FKs
  4. backfill genres from book_type WHERE book_type NOT LIKE '%/%'  (junk discarded)
  5. drop books.author / books.level / books.book_type
downgrade(): reverse — re-add text columns, copy names back, drop entity tables
```

(`audio.author_id` was cut from this revision when audio left scope; the `down_revision` chains directly off the baseline `70ee18aafdca`.) Tested against a restored copy of real dev data, not just an empty DB.

### Testing strategy

- **Entity modules** — red-first unit tests mirroring the tag pins: case-insensitive reuse, lowercase create, list endpoints, 401 guards.
- **Book search** — red-first repo probes: author/level/genre name→id filter, combined with tag OR, honest total, disjoint pagination. (The old Task 0 `file_type`→`book_type` hotfix is moot — the column is replaced, not renamed.)
- **Characterization pins** — video and tag current-behavior pins survive; only stream pins flip from "assert bytes body" to "assert 204 + redirect headers" when the video rewrite lands. **No audio pins** — the module is deferred.
- **Streaming** — unit tests assert the 204 + `X-Accel-Redirect` + `Content-Type` contract per media type (books, videos); 404 on missing row; 401 unauthenticated; containment (poisoned `file_path` → 404). **No Python Range tests** — deleted. One compose-level integration check curls `Range: bytes=0-99` through nginx and asserts 206 + `Content-Range`.
- **Migration test** — apply to a dev-DB dump; assert row counts and that every non-junk author string round-tripped into an `authors` row.

## 7. Deferred work (preserved, not lost)

Only two items stay deferred (user 2026-09-01). Every former non-audio deferral is **scheduled** — Part G of the plan (Tasks 11–16), executed after the React contract freeze, each red-first with a per-task commit.

- **Audio module refactor** — user-deferred 2026-09-01. `Audio`/`AudioTag`/`AudioRepo`/`audio_router` stay legacy 1.x with inline DB + zero tests + Python-streamed bytes + zero auth; on re-pickup it gets its own plan (its old Task 1 pin-cases + Task 10 rewrite exist in git history at `2026-08-26-audio-video-tag-refactor.md` before this revision). **Until that plan runs, the `/audio/` endpoints remain zero-auth — flag this loudly in any deployment that matters.**
- **React annex follow-ups** — signed-ticket media streaming, the nginx `try_files` block, the `frontend/` AGENTS.md convention. Handled when the React track executes the annex (plan Task 10 Step 1).

Scheduled (Part G, plan Tasks 11–16 — each preserves the frozen §9 contract, additive-only):

| Old deferral | Now |
|---|---|
| `uploads/vids` → `uploads/videos` rename | Task 11 (config + X-Accel kind + data migration; physical move before migration) |
| Orphan `Tag` rows | Task 12 (existence-based `delete_orphans` on tag + the three entity repos, invoked on delete/update only) |
| Orphan entity rows | Task 12 (same) |
| Video metadata / poster extraction | Task 13 (`poster_path` + `poster_url`, ffmpeg-optional, never raises; ID3 stays with audio's deferral) |
| Student read-only auth tightening | Task 14 (video write endpoints → admin/teacher; books already split in Task 5) |
| Cover replacement on PUT | Task 15 (image validator + `save_cover` + optional multipart `cover`) |
| epub→pdf + `GET /books/{uid}/read` | Task 16 (pymupdf converter, cached `{uid}.read.pdf` under `UPLOAD_DIR`, X-Accel) |

## 8. Invariant check

| # | Invariant | This design |
|---|---|---|
| 1 | Layering router→service→repo | ✅ books + video gain a service; entity modules are the seam (audio stays legacy — non-worsening grandfathered violation, deferred per §7) |
| 2 | Error mapping router-only | ✅ §5; entity repos raise nothing but `IntegrityError` |
| 3 | No CWD-relative I/O | ✅ in-scope routers emit headers, never paths; `resolve()` containment stays (audio's CWD-relative line is deferred per §7) |
| 4 | SQLAlchemy 2.0 | ✅ all new models/repos 2.0; video/tag converted (audio legacy) |
| 5 | Postgres tests | ✅ testcontainers harness; migration tested on real data; nginx Range covered by one compose integration check (audio has zero tests — deferred) |
| 6 | Naming | ✅ `Author`, `Level`, `Genre`, `AuthorRepo`… — no underscores; (`Audio_Repo` etc. remain as legacy debt) |

Schema change (Invariant "ask first"): approved by the user 2026-09-01 as part of this design.

## 9. React handoff outcome

When this plan closes, React integration starts in parallel with new backend feature development. To make that safe, the plan ends with the **backend contract frozen**: the response schemas (`BookRead`, `VideoView`, `TagRead`, `AuthorRead`/`LevelRead`/`GenreRead`, `Page[T]`), the error body shape (`{detail: str}`), auth (Bearer JWT with role), and the URL prefixes (`/api/`, `/media/`, `/static/covers/`) are the surface React pins to. Any new backend feature lands *behind* that contract without reshaping it, so the two tracks can proceed cleanly.

The final task of the plan writes `docs/superpowers/specs/react-kickoff-annex.md` with the integration decisions recorded for the SPA:

- **Topology:** same-origin Option A — the same `nginx` service serves both the API and the SPA. `frontend/dist` mounts into `nginx` at a `location /` block with `try_files $uri $uri/ /index.html;` and `/api/`, `/media/`, `/static/covers/` locations continue to take precedence. No CORS surface, no second published port.
- **Token strategy:** login via `POST /api/auth/login`, token stored in `localStorage`, every API call through a fetch wrapper adding `Authorization: Bearer <token>`.
- **Role gating:** role decoded from the JWT payload (`RoleChecker` mirrors on the backend); UI routes gate on it client-side as UX — never as security.
- **Media access:** `<img src="/static/covers/…">` works natively because covers are public. For protected streams (`/api/books/{uid}/stream`, `/api/videos/stream/{id}`), native `<video>/<embed>` tags cannot carry the `Authorization` header — the SPA either (a) fetches with the wrapper into a blob URL (`URL.createObjectURL`), buffering the whole file client-side, or (b) the backend adds a short-lived signed query ticket (`?ticket=`) as a follow-up feature task. The annex records (a) as the interim pattern and flags (b) as a follow-up — decided deliberately when the SPA plan lands, not silently.
- **Error shape:** UI reads `{detail}` uniformly; backend error mapping (Invariant 2) already guarantees it.
- **Where React/config lives:** `frontend/` directory gets its own convention section in `AGENTS.md` (write-mode guidance added alongside the annex; the backend's advisory boundaries stay unchanged).
