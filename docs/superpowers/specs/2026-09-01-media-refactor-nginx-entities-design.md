# Media Refactor + nginx Streaming + Criteria Entities — Design (2026-09-01)

> **Status:** approved 2026-09-01. Governs the implementation plan of the same date. Where a plan and this spec disagree, the spec wins.
>
> **Supersedes:** `2026-08-16-book-refactor-design.md` (deleted by this project) and the streaming/architecture halves of the two plans it replaces (`2026-08-16-book-refactor.md`, `2026-08-26-audio-video-tag-refactor.md`). The TDD process spec `2026-08-24-tdd-workflow-design.md` is **not** superseded — it governs how the plan is executed.

## 1. Goal

Three changes, one project:

1. **Refactor books, audio, and video** to the invariant shape (service layer, SQLAlchemy 2.0, tests, naming) — the union of the two plans being replaced.
2. **Replace hand-rolled Python streaming with nginx** via X-Accel-Redirect, for real performance and correct RFC 7233 behavior.
3. **Promote `author`, `level`, and `genre` to tag-like entities** (single-valued FK) with a data-preserving Alembic migration, renaming `book_type` → `genre` to kill the file-format conflation.

## 2. Why nginx over Python streaming

The current implementation serves every byte through a Python generator (`audio_router.py:170-177` reads 1MB chunks; `book_router.py` has three streaming endpoints; `video_router.py` one). This is the worst code in the codebase and the slowest:

- **Performance.** Python `StreamingResponse` crosses the Python/C boundary per chunk, holds an event-loop slot, and competes with request handling. nginx serves via `sendfile(2)` — the kernel moves bytes disk→socket without userspace. On the deployment target (Rock 5B, SD/eMMC), this is the difference between "works" and "falls over when a class opens the same video."
- **Correctness for free.** nginx implements RFC 7233 natively — single-range 206/416, suffix ranges for Safari/pdf.js, `If-Range`. The two replaced plans each carried a ~100-line hand-rolled range parser and an 8-row test table; both are deleted.
- **Layering.** FastAPI does the security decision (auth + path containment), nginx does the byte-serving. Each layer does the one thing it is good at. This is the standard protected-media pattern (Django `X-Sendfile`, Rails `X-Accel-Redirect`).

The honest cost: an nginx config to maintain, and Range behavior leaves the pytest suite (mitigated in §6).

## 3. nginx topology

`docker-compose.yml` gains an `nginx` service; the `backend` service stops publishing `8000` to the host. nginx is the **only** published port.

```
client → nginx:80
  ├── location /api/            → proxy_pass http://backend:8000/   (strip /api prefix)
  ├── location /media/books/    → internal; alias /srv/uploads/books/
  ├── location /media/audio/    → internal; alias /srv/uploads/audio/
  ├── location /media/vids/     → internal; alias /srv/uploads/vids/
  └── location /static/covers/  → public static, alias /srv/uploads/covers/
```

- `/media/*` locations are `internal` — reachable only via `X-Accel-Redirect`, never directly. This is the enforcement that media requires auth.
- `/static/covers/` is public (book covers are browsable assets). The `StaticFiles` mount in `main.py` is removed; nginx takes covers over. The `cover_url` computed field on `BookRead` (`/static/covers/{name}`) is unchanged — the URL prefix is identical, only the server behind it changes (FastAPI `StaticFiles` → nginx).
- Volumes: the host `./uploads` tree is mounted into **both** `backend` (read/write, at `/app/uploads`) and `nginx` (read-only, at `/srv/uploads`). One source of truth on disk.

## 4. Criteria taxonomy

`author`, `level`, and `genre` become **single-valued foreign-key entities**, each mirroring `Tag` in shape (`models/tag.py:14-17`). Single-valued FK, **not** many-to-many — user decision 2026-09-01: a book has at most one author/level/genre today (YAGNI), and the migration is a 1:1 column conversion.

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
| `language: str` | unchanged | stays a plain indexed string column |
| `extension: str` | unchanged | file format lives here, untouched |

The `book_type` → `genre` rename is semantic, not cosmetic: today the column holds junk MIME values (`application/pdf`) from the old `file_type` conflation bug. The real file format is already carried by `extension`. Junk values are deliberately discarded, not converted.

### `audio` table delta

Adds `author_id → authors.id` (nullable, `ON DELETE SET NULL`). No backfill — audio has no author today.

### `video` table delta

None. Video gets tags only, no new criteria.

### Entity semantics — "same as tags"

Each entity repo gets the tag pattern being added to `TagRepo` (old media plan Task 6):

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
- `repositories/book_repo.py`: 2.0 `select()` (old plan Task 5a); search resolves names → ids and filters FK columns; `selectinload` for tags + the three new relationships.
- `services/book_service.py`: thin orchestration over the leaf modules (old plan Task 5b); on create/update, resolve `author`/`level`/`genre` names via the three entity repos' `get_or_create_by_name` before building `BookCreate`.

### Audio / video modules

Carried forward **unchanged** from the old media plan (Tasks 6–8), with one exception — §6 replaces the streaming endpoint. `Audio`/`Video` models convert to 2.0; `audio.py` gains `author_id`; `AudioService.upload`/`update` resolve author via `AuthorRepo.get_or_create_by_name`; `Video` is untouched. Tag module refactor (Task 6: `TagRepo` 2.0 + `get_or_create_by_names` + `TagService` + router auth) is unchanged — the three new entity modules copy its exact shape.

### Streaming endpoint — the X-Accel contract

All three media routers get an identically-shaped stream endpoint. The router **never opens a file** — it emits a header (Invariant 3):

```python
@router.get("/{uid}/stream")
def stream(uid, svc=Depends(get_service), _=Depends(RoleChecker([admin, teacher, student]))):
    media_path, media_type = svc.resolve_stream(uid)   # raises BookNotFound/MediaNotFound
    accel = f"/media/{kind}/{media_path.name}"          # single safe filename, containment already enforced
    return Response(status_code=204, headers={
        "X-Accel-Redirect": accel,
        "Content-Type": media_type,
        "Accept-Ranges": "bytes",
    })
```

- `resolve_stream` (service) is the **only** place files are located: row missing → 404; `storage.resolve()` enforces traversal containment + existence (the C4 lesson, unchanged). It returns the resolved absolute `Path` and the media type. The redirect URI is built from `media_path.name` — the basename only — which is safe by construction because storage wrote it (`{uid}.{ext}` for books, `{uuid4}_{filename}` for audio/video) and `resolve()` already proved it lives under the media dir. Nested paths cannot appear in the URI.
- FastAPI returns **204 No Content**; nginx substitutes the file body. `Content-Type` is set by FastAPI (it knows the media type); nginx serves bytes + Range.
- Covers are **not** routed through this — they're public static on nginx (`/static/covers/`).

### Error mapping (Invariant 2, router-only)

`BookNotFound`/`MediaNotFound` → 404; `InvalidBookFile`/`InvalidMediaFile` → 400; `IntegrityError` → 400 (includes the entity unique-race). Entity repos raise nothing — `get_or_create_by_name` always succeeds or raises `IntegrityError`.

## 6. Migration & testing strategy

### Alembic migration (one revision, data preserved)

```
upgrade():
  1. create authors / levels / genres (+ unique + lower() indexes)
  2. add books.author_id / level_id / genre_id FK columns
  3. backfill authors/levels from distinct trimmed lower(strings); re-link FKs
  4. backfill genres from book_type WHERE book_type NOT LIKE '%/%'  (junk discarded)
  5. drop books.author / books.level / books.book_type
  6. add audio.author_id
downgrade(): reverse — re-add text columns, copy names back, drop entity tables
```

Tested against a restored copy of real dev data, not just an empty DB.

### Testing strategy

- **Entity modules** — red-first unit tests mirroring the tag pins: case-insensitive reuse, lowercase create, list endpoints, 401 guards.
- **Book search** — red-first repo probes: author/level/genre name→id filter, combined with tag OR, honest total, disjoint pagination. (The old Task 0 `file_type`→`book_type` hotfix is moot — the column is replaced, not renamed.)
- **Characterization pins** — the old media plan's Part A pins (audio/video/tag current behavior) survive; only stream pins flip from "assert bytes body" to "assert 204 + redirect headers."
- **Streaming** — unit tests assert the 204 + `X-Accel-Redirect` + `Content-Type` contract per media type; 404 on missing row; 401 unauthenticated; containment (poisoned `file_path` → 404). **No Python Range tests** — deleted. One compose-level integration check curls `Range: bytes=0-99` through nginx and asserts 206 + `Content-Range`.
- **Migration test** — apply to a dev-DB dump; assert row counts and that every non-junk author string round-tripped into an `authors` row.

## 7. Deferred work (preserved, not lost)

- `uploads/vids` → `uploads/videos` rename (needs a data migration).
- epub→pdf conversion + `GET /books/{uid}/read` (no converter module in this design).
- Cover replacement on PUT (no image validator in the leaf set).
- Audio/video metadata extraction (ID3, poster thumbnails).
- Student-read-only auth tightening (product decision).
- Orphan tag/entity cleanup.

## 8. Invariant check

| # | Invariant | This design |
|---|---|---|
| 1 | Layering router→service→repo | ✅ all three media modules gain a service; entity modules are the seam |
| 2 | Error mapping router-only | ✅ §5; entity repos raise nothing but `IntegrityError` |
| 3 | No CWD-relative I/O | ✅ routers emit headers, never paths; `resolve()` containment stays |
| 4 | SQLAlchemy 2.0 | ✅ all new models/repos 2.0; audio/video/tag converted |
| 5 | Postgres tests | ✅ testcontainers harness; migration tested on real data; nginx Range covered by one compose integration check |
| 6 | Naming | ✅ `Author`, `Level`, `Genre`, `AuthorRepo`… — no underscores |

Schema change (Invariant "ask first"): approved by the user 2026-09-01 as part of this design.
