# Structure + Auth Implementation Plan (rescoped 2026-08-15)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two efforts, in this order. **Part A — system design of the folder structure**: package hygiene, single dependency manifest, config-driven paths, Docker, and Alembic. **Part B — the auth system**: fix the seven live defects and pin the behavior with a real test suite.

**Explicitly out of scope this pass:** book / audio / video / tag test suites, and the bugs those tests would have found (`Book.file_type` AttributeError, audio+video delete-missing 500). They are preserved verbatim in the Deferred Work annex at the bottom so nothing is lost. The audio/video *routers* are still touched in Task S3, but only to change where files are written — no behavior change.

**Architecture:** The FastAPI layered monorepo (router → service → repository → model) stays intact. Tests run on the ALREADY-COMMITTED testcontainers Postgres harness (`backend/conftest.py` starts one `postgres:16-alpine` per session and sets `DATABASE_URL`/`SECRET_KEY`; `backend/app/tests/conftest.py` provides `db_env`, `reset_db` (autouse), `client`, `db`, `setup_paths` plus module-level helpers `setup_admin`, `login`, `auth_headers`). AuthRepo is already SQLAlchemy 2.0 `select()` (commit `a034adf`). Dependency management consolidates on `backend/pyproject.toml` + `backend/uv.lock`. Schema management moves from `Base.metadata.create_all` to Alembic.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests, docker-compose for dev/prod), Alembic 1.17, uv, pytest/httpx, ruff, mypy.

## Global Constraints

- `requires-python = ">=3.13"`; run every command with `uv run` from `backend/`
- Tests need only a **running Docker daemon** — the harness self-manages its container. `docker compose up -d db` is required *only* for the Alembic baseline in Task S5.
- Pre-existing repo-wide lint debt (B008 etc.) is out of scope: run `ruff check --ignore B008` on changed files, `mypy --strict` on changed files only. Log pre-existing failures in STATE.md; do not fix unrelated files.
- Commit after every task, message style from git log: `test:`, `fix:`, `chore:`, `feat:`
- Never delete a failing test to make the suite pass — fix the underlying logic (AGENTS.md)
- After the final task run `graphify update .` to refresh the knowledge graph
- **Locked auth decisions** (from the auth code review): (a) admin-role creation is rejected for **everyone** with **400**, `/setup` is the only bootstrap; (b) teacher creates teacher → **403**; (c) student self-change accepts any ≥4-char password (not all-digit); (d) DB migration story = full Alembic adoption

---

## Corrections to the previous plan

The prior revision of this document was audited line-by-line against the working tree on 2026-08-15. Five claims were wrong or missing. They are corrected below and folded into the tasks.

| # | Previous claim | Verified reality | Consequence |
|---|---|---|---|
| 1 | `backend/app/tests/__init__.py` "✅ exists" | **Does not exist.** Neither does `backend/app/dependencies/__init__.py` | Task 2 of the old plan told tests to `from app.tests.conftest import ...` — an import from a non-package. Now fixed first, in S1. |
| 2 | (not mentioned) | `backend/app/__init__.py` eagerly imports `models`, `schemas`, `repositories`, `api`, `services` and lists `"app"` in `__all__` — a name never defined in that module | Import cycles + a broken `from app import *`. This *is* folder-structure design. Fixed in S1. |
| 3 | (not mentioned) | `docker/entrypoint.sh` **exists but is dead** — the Dockerfile never `COPY`s it and has no `ENTRYPOINT` | The old plan's Task 7 assumed it was already wired. S4 wires it explicitly. |
| 4 | "Tracked media under `uploads/`" | There are **two** upload trees: root `uploads/` (holds the 4 tracked files) and `backend/uploads/` (empty). `BASE_DIR` = `backend/`, so **root `uploads/` is orphaned** — the app never reads it | Explains *why* the media is stranded. S3 consolidates the trees instead of just untracking. |
| 5 | "Duplicate manifests" | Confirmed, and worse: root `uv.lock` and `backend/uv.lock` **differ** (`diff` exits non-zero) | Real drift, not just duplication. S2 deletes the root copy. |

One more constraint the old plan missed: **`from app import settings` is load-bearing** — used by `app/main.py:7`, `app/api/book_router.py:9`, and `app/services/book_service.py:9`. The `app/__init__.py` cleanup in S1 must keep that re-export working or update all three call sites.

---

## Current State (verified against the tree, 2026-08-15)

### Structure

| Area | State | Where |
|---|---|---|
| Test harness | ✅ testcontainers Postgres, session-scoped | `backend/conftest.py`, `backend/app/tests/conftest.py` |
| AuthRepo 2.0 syntax | ✅ `select()` | commit `a034adf` |
| `app/tests/__init__.py` | 🔴 MISSING — `app.tests.conftest` is not importable | — |
| `app/dependencies/__init__.py` | 🔴 MISSING | — |
| `app/__init__.py` | 🔴 Eager subpackage imports + `"app"` in `__all__` (undefined name) | `backend/app/__init__.py` |
| pytest config | 🔴 None — `pythonpath`/`testpaths` rely on CWD luck | `backend/pyproject.toml` |
| Manifests | 🔴 Root `uv.lock` (drifted) + `backend/requirements.txt` + `backend/uv.lock` | repo root, `backend/` |
| `pyproject.toml` description | 🔴 "Add your description here" | `backend/pyproject.toml:4` |
| Upload trees | 🔴 Two: root `uploads/` (orphaned, 4 tracked media files) and `backend/uploads/` (live) | repo root, `backend/` |
| Relative upload dirs | 🔴 `"uploads/audio"` ×2, `Path("uploads")/"vids"` | `audio_router.py:41,76`, `video_router.py:14` |
| `AUDIO_DIR`/`VIDEO_DIR` settings | 🔴 Absent (only `UPLOAD_DIR`, `COVER_DIR`, `DATA_DIR`) | `backend/app/config.py` |
| Dockerfile | 🔴 `python:3.11-slim` + `pip install -r requirements.txt`, copies whole `backend/`, no entrypoint | `backend/Dockerfile` |
| `docker/entrypoint.sh` | 🔴 Exists, never referenced by the image | `docker/entrypoint.sh` |
| Alembic | 🔴 Declared in deps, zero usage; lifespan does `create_all` | `backend/app/main.py:22` |
| Media in git | 🔴 3 `.mp3` + 1 `.wav` tracked despite `uploads/` in `.gitignore` | `uploads/audio/` |

### Auth

| Defect | State | Where |
|---|---|---|
| `verify_password` wrong password → 500 | 🔴 LIVE — raises `ValueError` on mismatch instead of returning `False` | `auth_service.py:59-63` |
| Teacher-creates-teacher RBAC gap | 🔴 LIVE — `create_user` takes no caller role at all | `auth_service.py:80-93`, `auth_router.py:95` |
| Admin-role creation | 🔴 LIVE — raises `PermissionError` (403); must be `ValueError` (400) | `auth_service.py:90-93` |
| Bulk admin creation | 🔴 LIVE — same, `PermissionError` (403); must be 400 | `auth_service.py:171-172` |
| reset-password teacher→teacher → 500 | 🔴 LIVE — router catches only `ValueError`; `PermissionError` escapes | `auth_router.py:62-63`, `auth_service.py:144-145` |
| `first_login` on teacher reset | 🔴 LIVE — `change_password` hardcodes `first_login = False` | `auth_repo.py:41-46` |
| Student self-change rule | 🔴 LIVE — requires all-digit; must be ≥4 chars, any chars | `auth_service.py:41-43` |
| `/setup` race → 500 | 🔴 LIVE — admin row exists but flag file missing ⇒ uncaught `ValueError` | `setup_router.py:30-33` |
| Bulk prefix with `%` | 🔴 LIVE — `.like()` treats `%` as a wildcard | `auth_repo.py:51` |
| `has_admin()` | 🔴 Dead code — zero call sites repo-wide | `auth_repo.py:33-39` |
| `get_all_users(None)` | 🔴 LIVE latent — `accounts` unbound if role is neither teacher nor admin ⇒ `UnboundLocalError` | `auth_service.py:213-218` |
| Auth tests | 🔴 One smoke test (`test_client_boots`) | `backend/app/tests/test_auth.py` |

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/tests/__init__.py` | **Create** | S1 | Make `app.tests.conftest` importable |
| `backend/app/dependencies/__init__.py` | **Create** | S1 | Package marker |
| `backend/app/__init__.py` | Modify | S1 | Strip eager subpackage imports + undefined `__all__` entry |
| `backend/app/main.py` | Modify | S1, S5 | Explicit model registration; drop `create_all` |
| `backend/app/api/book_router.py`, `services/book_service.py` | Modify | S1 | `from app import settings` → `from app.config import settings` |
| `backend/pyproject.toml` | Modify | S1, S2, S6 | pytest config; description; ruff/mypy config |
| root `uv.lock`, `backend/requirements.txt` | **Delete** | S2 | Collapse to one manifest |
| `backend/app/config.py` | Modify | S3 | Add `AUDIO_DIR` / `VIDEO_DIR` |
| `backend/app/api/audio_router.py`, `video_router.py` | Modify | S3 | Settings-driven paths (no behavior change) |
| root `uploads/audio/*.mp3`, `*.wav` | **Untrack** | S3 | Orphaned tracked media |
| `backend/Dockerfile` | Modify | S4, S5 | uv + py3.13; wire entrypoint + migrations |
| `.dockerignore` | Modify | S4 | Exclude venv/caches/data |
| `docker/entrypoint.sh` | Modify | S4, S5 | Actually get wired in; `alembic upgrade head` |
| `backend/alembic.ini`, `backend/migrations/` | **Create** | S5 | Versioned schema |
| `backend/app/services/auth_service.py` | Modify | A1, A2 | The auth defect fixes |
| `backend/app/repositories/auth_repo.py` | Modify | A2 | `first_login` param, `startswith`, drop `has_admin` |
| `backend/app/api/auth_router.py` | Modify | A1, A2 | Pass caller role; error mapping |
| `backend/app/api/setup_router.py` | Modify | A2 | Race hardening |
| `backend/app/tests/test_auth.py` | Modify | A1–A3 | Full auth suite |
| `README.md`, `STATE.md` | Modify | S6 | Document the new workflow |

---

# PART A — Folder structure / system design

### Task S1: Package hygiene and deterministic imports

**Files:**
- Create: `backend/app/tests/__init__.py`, `backend/app/dependencies/__init__.py`
- Modify: `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/api/book_router.py`, `backend/app/services/book_service.py`, `backend/pyproject.toml`

**Interfaces:**
- Consumes: nothing new
- Produces: `app.tests.*` importable as a package; `app` importable without pulling the entire application graph; `pytest` runs identically from any CWD

**Why (learning):** Three distinct lessons here.

*1. A directory is not a package.* `backend/app/tests/` has no `__init__.py`, yet Part B's tests need `from app.tests.conftest import setup_admin, login, auth_headers`. pytest's `rootdir` insertion makes *test collection* work via implicit namespace packages, but an explicit `import app.tests.conftest` is fragile — it depends on `sys.path` ordering and silently breaks under different invocations (`pytest` vs `pytest app/tests` vs `python -m pytest`). Adding `__init__.py` makes the package a declared thing rather than an accident. This is the difference between a **regular package** (has `__init__.py`, one unambiguous location) and an **implicit namespace package** (PEP 420, can be assembled from multiple `sys.path` entries). Namespace packages exist for plugin systems that *want* to be split across distributions; for a test suite they only add ambiguity.

*2. Eager `__init__.py` imports are an architectural liability.* Today `app/__init__.py` imports `config`, `database`, `models`, `schemas`, `repositories`, `api`, and `services`. That means `import app.config` — the cheapest possible import — transitively constructs the SQLAlchemy engine, imports FastAPI, and builds every router. Consequences: (a) import cycles become likely as the app grows, since any module importing `app.anything` triggers the whole graph; (b) tooling like Alembic pays the full cost to read one setting; (c) failures surface as confusing `ImportError` chains far from the real cause. The principle is **explicit imports at the point of use**. A package's `__init__.py` should export a small, deliberate surface — or nothing at all.

*3. `__all__` is a contract, and this one is broken.* `"app"` is listed in `__all__` but never defined in the module. `from app import *` raises `AttributeError` today. `__all__` controls star-imports and signals public API to linters and docs tools; an entry with no backing name is a latent error that no test catches because nobody star-imports it. Lesson: `__all__` must be kept in lockstep with the module body, which is another argument for keeping it small.

*4. Configuration belongs in the file, not the invocation.* Without `[tool.pytest.ini_options]`, whether the suite runs depends on your shell's CWD. Encoding `pythonpath` and `testpaths` in `pyproject.toml` makes the command reproducible on every machine and in CI — the same reason `uv.lock` exists. Prefer declarative config over remembered incantations.

- [x] **Step 1: Establish the baseline — the harness works today**

```bash
cd backend && uv run pytest app/tests -v
```

Expected: `1 passed` (`test_client_boots`). This is the safety net for every later step; if it does not pass, stop and fix the harness before touching anything.

- [x] **Step 2: Add the missing package markers**

```bash
touch backend/app/tests/__init__.py backend/app/dependencies/__init__.py
```

Both files stay empty. An empty `__init__.py` is the correct content for a package that exports nothing — it declares "this directory is a package" and nothing more.

- [x] **Step 3: Add pytest config to `backend/pyproject.toml`**

Append:

```toml
[tool.pytest.ini_options]
testpaths = ["app/tests"]
pythonpath = ["."]
addopts = "-q --tb=short"
```

`pythonpath = ["."]` puts `backend/` on `sys.path` so `app.*` and `app.tests.*` resolve regardless of CWD. `testpaths` means bare `uv run pytest` collects the right directory.

- [x] **Step 4: Rewrite `backend/app/__init__.py`**

Replace the entire file with:

```python
"""
Jirani Offline Library Backend

A FastAPI-based backend for managing an offline library system.
Designed for deployment on Rock 5B with ARM64 architecture.
"""

__version__ = "1.0.0"
__author__ = "tuanlearntodev"
__description__ = "FastAPI backend for offline library management"

__all__ = ["__version__", "__author__", "__description__"]
```

Every subpackage import and the `settings` / `get_db` / `SessionLocal` / `Base` re-exports are gone. Consumers import from the defining module instead — see the next step.

- [x] **Step 5: Update the three `from app import settings` call sites**

`from app import settings` only worked because of the eager re-export just deleted. Three files depend on it (verified by grep — do not skip any):

- `backend/app/main.py:7`
- `backend/app/api/book_router.py:9`
- `backend/app/services/book_service.py:9`

In each, replace:

```python
from app import settings
```

with:

```python
from app.config import settings
```

In `main.py` the line also carries the comment `# Import models to register them with Base` — delete the comment, it is now false (and was misleading before: models registered as a *side effect* of the eager import, not because of `settings`).

- [x] **Step 6: Make model registration explicit in `backend/app/main.py`**

This is the load-bearing consequence of Step 4. `Base.metadata` is only populated by importing the modules that define the models. Previously that happened invisibly. Add an explicit import near the other `app` imports:

```python
import app.models  # noqa: F401  # registers every model on Base.metadata
```

The `# noqa: F401` tells ruff the "unused" import is deliberate. *Why this matters:* SQLAlchemy's declarative `Base` is populated by class-definition side effects. If a model module is never imported, its table simply does not exist in `Base.metadata` — `create_all` skips it and Alembic autogenerate emits a `drop_table` for it. This same import is repeated in `migrations/env.py` in Task S5 for exactly that reason. **Implicit side-effect registration should always be made explicit at the composition root.**

- [x] **Step 7: Verify nothing broke**

```bash
cd backend && uv run python -c "import app; print(app.__version__)"
cd backend && uv run python -c "from app.main import app; print(len(app.routes), 'routes')"
cd backend && uv run pytest -v
```

Expected: version prints; route count > 10; `1 passed`. If an `ImportError` appears, a call site of `from app import <name>` was missed — grep again for `from app import`.

- [x] **Step 8: Lint + commit**

```bash
cd backend && uv run ruff format app/__init__.py app/main.py app/api/book_router.py app/services/book_service.py && uv run ruff check app/__init__.py app/main.py app/api/book_router.py app/services/book_service.py --ignore B008
git add backend/app/__init__.py backend/app/tests/__init__.py backend/app/dependencies/__init__.py backend/app/main.py backend/app/api/book_router.py backend/app/services/book_service.py backend/pyproject.toml
git commit -m "chore: package hygiene — explicit imports, package markers, pytest config"
```

---

### Task S2: One dependency manifest

**Files:**
- Delete: root `uv.lock`, `backend/requirements.txt`
- Modify: `backend/pyproject.toml` (description)

**Interfaces:**
- Consumes: `backend/pyproject.toml` + `backend/uv.lock` as the single source of truth
- Produces: exactly one resolvable dependency graph in the repo

**Why (learning):** The repo currently declares dependencies in three places: `backend/pyproject.toml` (source of truth), `backend/uv.lock` (its resolution), and `backend/requirements.txt` (a hand-maintained copy that the Dockerfile actually installs). Plus a stray root `uv.lock` that **differs** from the backend one — verified with `diff`, exit code non-zero.

The failure mode is not hypothetical. `requirements.txt` is what production installs, so any dependency added to `pyproject.toml` and not mirrored is present in dev and absent in the image — a `ModuleNotFoundError` that appears only after deploy. The general principle is **single source of truth**: derived artifacts must be *generated*, never hand-edited. `uv.lock` is generated. `requirements.txt` here is not, which is why it drifted.

The stray root lock is a different lesson: **lockfiles are scoped to the project that owns the manifest.** A lock at the repo root implies a project rooted there, and none exists. Tools resolving upward from a subdirectory can pick up the wrong one. Delete it rather than sync it — two identical files still drift eventually; one file cannot.

Note the ordering dependency: this task must land **before** S4, because the new Dockerfile installs from `uv.lock` and would otherwise be modifying a file this task deletes.

- [ ] **Step 1: Confirm the drift before deleting (evidence, not assumption)**

```bash
diff uv.lock backend/uv.lock > /dev/null && echo "IDENTICAL" || echo "DIFFERENT — root lock is stale"
grep -c "" backend/requirements.txt
```

Expected: `DIFFERENT`. Record the finding in the commit body if you like — it justifies the deletion.

- [ ] **Step 2: Confirm `pyproject.toml` is a superset of `requirements.txt`**

Before deleting `requirements.txt`, verify nothing in it is missing from `pyproject.toml`:

```bash
cd backend && uv run python - <<'PY'
import re, tomllib
req = {
    re.split(r"[<>=!\[]", line.strip())[0].lower()
    for line in open("requirements.txt")
    if line.strip() and not line.startswith("#")
}
proj = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
have = {re.split(r"[<>=!\[]", d)[0].lower() for d in proj}
missing = req - have
print("MISSING from pyproject:", missing or "none")
PY
```

Expected: `none`. If anything is listed, add it to `pyproject.toml` with `uv add <pkg>` and re-run **before** proceeding. Do not delete a manifest you have not verified is redundant.

- [ ] **Step 3: Delete the redundant manifests**

```bash
git rm uv.lock backend/requirements.txt
```

- [ ] **Step 4: Fix the placeholder description in `backend/pyproject.toml`**

Replace:

```toml
description = "Add your description here"
```

with:

```toml
description = "Jirani Offline Library — FastAPI backend for offline library management"
```

- [ ] **Step 5: Verify the environment still resolves**

```bash
cd backend && uv sync && uv run pytest -v
```

Expected: sync succeeds against `backend/uv.lock`; tests still `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: collapse to a single dependency manifest (backend/pyproject.toml + uv.lock)"
```

---

### Task S3: Settings-driven upload paths + consolidate the two upload trees

**Files:**
- Modify: `backend/app/config.py` (add `AUDIO_DIR`, `VIDEO_DIR`), `backend/app/api/audio_router.py` (2 sites), `backend/app/api/video_router.py` (1 site), `backend/app/main.py` (lifespan)
- Untrack: root `uploads/audio/*.mp3`, `*.wav`

**Interfaces:**
- Consumes: `settings.BASE_DIR`-anchored paths
- Produces: `settings.AUDIO_DIR` / `settings.VIDEO_DIR`; all four upload dirs created at startup; no CWD-relative filesystem writes; zero tracked binaries

**Why (learning):** Two intertwined problems, one root cause.

*1. Relative paths are resolved against the current working directory, which is not a property of your code.* `audio_router.py:41` and `:76` write to the string `"uploads/audio"`; `video_router.py:14` builds `Path("uploads") / "vids"`. None of these are anchored to anything. Where the bytes land depends entirely on where the process was launched: run `uvicorn` from `backend/` and you get `backend/uploads/audio`; run it from the repo root and you get `<root>/uploads/audio`; in Docker, `WORKDIR /app` gives `/app/uploads/audio`. The path is then persisted into the database as a string, so a row written in one environment resolves to nothing in another — the stream endpoint 404s (or worse, serves a stale file). Compare the book module, which does this correctly: `config.py` anchors `UPLOAD_DIR` to `BASE_DIR = Path(__file__).resolve().parent.parent`. `__file__` is a property of the *code*, so it is invariant under CWD. **Rule: never let filesystem layout depend on how the process was invoked. Anchor to `__file__` or to explicit configuration, never to the CWD.**

*2. The orphaned tree is the visible symptom of problem 1.* There are two upload trees. `BASE_DIR` resolves to `backend/`, so the application reads and writes `backend/uploads/` — which is empty. The root `uploads/` holds four real audio files that were committed at some point, and the app never touches them. They survive in git because `.gitignore` is not retroactive: **ignore rules only apply to untracked files.** Once a path is in the index, git keeps tracking it forever until you explicitly `git rm --cached`. This is the single most common `.gitignore` misunderstanding. The fix is to remove them from the index (keeping them on disk) so the ignore rule finally takes effect.

*Why untracking binaries matters beyond tidiness:* git stores full snapshots of every version of a binary. Media files do not delta-compress, so every re-upload permanently inflates the clone size for every future contributor. Binary assets belong in object storage or a volume mount — note `docker-compose.yml` already mounts `./uploads:/app/uploads`, so these files were never meant to be in the image or the repo.

*Directory creation belongs at the composition root.* Today each router calls `os.makedirs` inline at request time. Moving it to the lifespan means the "does this directory exist" question is answered once at startup, not on every upload — and a permissions failure surfaces at boot instead of on a user's first upload.

- [ ] **Step 1: Add the two missing directory settings to `backend/app/config.py`**

In the `Settings` class, alongside the existing `UPLOAD_DIR` / `COVER_DIR`:

```python
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "uploads" / "books"
    COVER_DIR: Path = BASE_DIR / "uploads" / "covers"
    AUDIO_DIR: Path = BASE_DIR / "uploads" / "audio"
    VIDEO_DIR: Path = BASE_DIR / "uploads" / "vids"
```

`vids` (not `videos`) is deliberate — it matches the existing on-disk directory and the Dockerfile's `mkdir`. Renaming it is a separate migration with data implications; do not fold it in here.

- [ ] **Step 2: Fix `backend/app/api/audio_router.py` — BOTH sites**

Add to the imports:

```python
from app.config import settings
```

Then replace the assignment at **line 41** and again at **line 76** (single-file upload and multi-file upload — grep for `upload_directory = "uploads/audio"` to confirm exactly two matches):

```python
    upload_directory = settings.AUDIO_DIR
```

Leave the surrounding `os.makedirs(upload_directory, exist_ok=True)` and the `file_location` f-string as they are. `Path` interpolates cleanly into an f-string, so `f"{upload_directory}/{uuid...}"` still produces a valid absolute path. This is intentionally the minimum diff — no behavior change beyond the anchor point.

- [ ] **Step 3: Fix `backend/app/api/video_router.py` — line 14**

Add `from app.config import settings` to the imports, then replace:

```python
VIDS_DIR = Path("uploads") / "vids"
```

with:

```python
VIDS_DIR = settings.VIDEO_DIR
```

`from pathlib import Path` on line 10 may now be unused — let ruff decide:

```bash
cd backend && uv run ruff check app/api/video_router.py --ignore B008
```

Remove the import only if ruff reports `F401`.

- [ ] **Step 4: Create all four upload dirs in the `backend/app/main.py` lifespan**

The lifespan currently creates only `UPLOAD_DIR`, `COVER_DIR`, and `DATA_DIR`. Add the two new ones:

```python
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.COVER_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    settings.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
```

(Keep `Base.metadata.create_all` for now — Task S5 removes it.)

- [ ] **Step 5: Untrack the orphaned media**

```bash
git rm --cached uploads/audio/*.mp3 uploads/audio/*.wav
```

`--cached` removes from the index only; the files stay on disk. Verify the index is clean:

```bash
git ls-files | grep -E "\.(mp3|wav|mp4)$" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 6: Decide the fate of the orphaned root tree**

Root `uploads/` is not read by the application. Two defensible options — pick one and record it in STATE.md:

- **(a) Leave it on disk, untracked.** Zero risk. `.gitignore` now genuinely covers it. Recommended.
- **(b) Move the four files into `backend/uploads/audio/`** so they are reachable if matching DB rows exist:
  ```bash
  mv uploads/audio/*.mp3 uploads/audio/*.wav backend/uploads/audio/
  ```
  Only meaningful if the `audio` table has rows whose `file_path` matches. Check first:
  ```bash
  docker compose up -d db && docker compose exec db psql -U postgres -d jirani_library -c "SELECT id, file_path FROM audio;" 2>/dev/null || echo "no dev DB / no rows"
  ```

Whichever you choose, add `.gitkeep` files so the directory structure survives a fresh clone:

```bash
touch backend/uploads/books/.gitkeep backend/uploads/covers/.gitkeep backend/uploads/audio/.gitkeep backend/uploads/vids/.gitkeep
git add -f backend/uploads/*/.gitkeep
```

`-f` is required because `.gitignore` has a bare `uploads/` rule that matches at any depth.

- [ ] **Step 7: Verify**

```bash
cd backend && uv run python -c "from app.config import settings; print(settings.AUDIO_DIR); print(settings.VIDEO_DIR)"
cd backend && uv run pytest -v
```

Expected: both paths print as absolute, rooted at `backend/uploads/`; tests still pass.

- [ ] **Step 8: Lint + commit (two commits — config change and media untracking are separate concerns)**

```bash
cd backend && uv run ruff format app/config.py app/main.py app/api/audio_router.py app/api/video_router.py && uv run ruff check app/config.py app/main.py app/api/audio_router.py app/api/video_router.py --ignore B008
git add backend/app/config.py backend/app/main.py backend/app/api/audio_router.py backend/app/api/video_router.py
git commit -m "fix: anchor upload paths to settings instead of the working directory"
git add -A
git commit -m "chore: untrack orphaned media, add .gitkeep to upload dirs"
```

---

### Task S4: Dockerfile on uv + Python 3.13, and actually wire the entrypoint

**Files:**
- Modify: `backend/Dockerfile`, `.dockerignore`, `docker/entrypoint.sh`

**Interfaces:**
- Consumes: `backend/pyproject.toml` + `backend/uv.lock` (single manifest from S2)
- Produces: an image built with `uv sync --frozen` on `python:3.13-slim`, with `docker/entrypoint.sh` genuinely executed

**Why (learning):** Four separate defects in one file.

*1. Version skew between dev and prod.* `pyproject.toml` declares `requires-python = ">=3.13"` and `backend/.python-version` pins 3.13, but the image is `python:3.11-slim`. You are testing on one interpreter and shipping on another. Any 3.12/3.13-only syntax works locally and `SyntaxError`s in production. **The runtime version is part of the dependency contract and must be pinned in exactly one place, then honored everywhere.**

*2. `pip install -r requirements.txt` is unreproducible.* `requirements.txt` (deleted in S2) held loose constraints, so two builds a week apart could resolve different transitive versions — the classic "works on my machine, and also worked in CI yesterday" failure. `uv sync --frozen` installs the exact resolved graph from `uv.lock` and **fails** if the lock disagrees with `pyproject.toml`. That failure is the feature: it converts silent drift into a loud build error.

*3. `COPY backend/ ./` destroys layer caching.* Docker caches per instruction and invalidates every subsequent layer when an input changes. Copying the entire backend before installing means editing one line of Python invalidates the dependency install — a multi-minute rebuild for a one-character change. The fix is **order layers by rate of change, slowest first**: manifests (rarely change) → dependency install → application code (changes constantly). `--no-install-project` installs only the dependencies, deliberately excluding your own code from that cached layer.

*4. `docker/entrypoint.sh` is dead code.* It exists, it is correct, and the image never copies or references it — so its `mkdir` calls never run and, more importantly, S5's `alembic upgrade head` would never execute. **Lesson: an unreferenced config file is worse than a missing one, because it looks like coverage you do not have.** Verify wiring, do not assume it.

*Bonus — `build-essential` is dead weight.* It was needed to compile C extensions from source, but every dependency here (`psycopg2-binary`, `pymupdf`, `bcrypt`) ships manylinux wheels. Dropping it removes a compiler toolchain from the production image: smaller, faster, smaller attack surface. **Never ship build tooling in a runtime image.**

- [ ] **Step 1: Rewrite `backend/Dockerfile`**

```dockerfile
# Build backend
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

# uv from the official distroless image — no pip bootstrap needed
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

# Dependency layer: only invalidated when the manifests change
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application layer: changes on every commit, cheap to rebuild
COPY backend/app ./app

RUN mkdir -p /app/uploads/books /app/uploads/covers /app/uploads/audio /app/uploads/vids /app/data

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Notes on the details:
- The commented-out frontend build block from the old file is dropped. Dead code in a Dockerfile is still dead code; git history preserves it.
- `--no-dev` excludes pytest/ruff/mypy/testcontainers from the production image.
- `--no-sync` on the `CMD` stops uv from re-resolving at container start — the environment is already correct and the container may have no network.
- `ENTRYPOINT` + `CMD` is the standard split: the entrypoint always runs and receives the CMD as its arguments, which `exec "$@"` then execs. That is why the entrypoint must end in `exec "$@"` — `exec` replaces the shell process so uvicorn becomes PID 1 and receives `SIGTERM` directly. Without `exec`, the shell stays PID 1, swallows signals, and `docker stop` degrades into a 10-second timeout and `SIGKILL`.

- [ ] **Step 2: Update `docker/entrypoint.sh` to cover all four upload dirs**

```sh
#!/usr/bin/env sh
set -eu

mkdir -p /app/uploads/books /app/uploads/covers /app/uploads/audio /app/uploads/vids /app/data

exec "$@"
```

(`alembic upgrade head` is added in Task S5 — one concern per task.)

`set -eu` is not decoration: `-e` aborts on any failing command so a broken migration cannot silently start a server against an outdated schema, and `-u` turns a typo'd variable into an error instead of an empty string.

- [ ] **Step 3: Extend `.dockerignore`**

Append:

```
backend/.venv/
backend/.mypy_cache/
backend/.ruff_cache/
backend/data/
.ruff_cache/
.git/
```

Everything listed is either a host-specific artifact or a secret. `backend/data/` holds `.secret` (the generated `SECRET_KEY`) — **baking that into an image layer would leak it to anyone who can pull the image.** `.venv/` is host-platform-specific and would be both large and broken inside the container. `.git/` can be hundreds of MB and is never needed at runtime.

*Concept:* `.dockerignore` filters the **build context** — the tarball the daemon receives before the first instruction runs. Excluding files here means they are never uploaded, never cached, and never leak into a layer via a broad `COPY`. It is a security boundary, not just a speed optimization.

- [ ] **Step 4: Build and verify**

```bash
docker compose build jirani-backend
docker compose run --rm --entrypoint sh jirani-backend -c "python --version && uv run --no-sync python -c 'import fastapi, sqlalchemy; print(\"deps ok\")'"
```

Expected: `Python 3.13.x` and `deps ok`. If `uv sync --frozen` fails with a lock mismatch, run `cd backend && uv lock` and commit the updated lock — that failure means `pyproject.toml` and `uv.lock` genuinely disagree, which is exactly what `--frozen` exists to catch.

- [ ] **Step 5: Confirm the entrypoint is actually running**

```bash
docker compose run --rm jirani-backend sh -c 'ls -d /app/uploads/*'
```

Expected: all four directories listed, created by the entrypoint rather than the Dockerfile's `mkdir`. This is the check the old plan never made.

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile .dockerignore docker/entrypoint.sh
git commit -m "chore: build image with uv on python 3.13, wire entrypoint, drop build-essential"
```

---

### Task S5: Full Alembic adoption

**Files:**
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/<hash>_initial_schema.py`
- Modify: `backend/app/main.py` (remove `create_all`), `backend/Dockerfile` (copy migration assets), `docker/entrypoint.sh` (`alembic upgrade head`)

**Interfaces:**
- Consumes: `app.database.Base` metadata (all 10 models via `app/models/__init__.py`), `settings.DATABASE_URL`
- Produces: versioned schema; `alembic upgrade head` is the single source of table creation for dev/prod; the test conftest keeps `create_all`

**Why (learning):** `alembic` has been a declared dependency with zero usage since the project started. The schema lives in one line — `Base.metadata.create_all(bind=engine)` in the lifespan.

*Why `create_all` cannot be the production schema story.* It only ever issues `CREATE TABLE IF NOT EXISTS`. It creates tables that are missing; it will **never** add a column, change a type, add an index, or drop anything. So the moment a model changes, dev and prod silently diverge: the ORM emits SQL for a column the database does not have, and you get a runtime `UndefinedColumn` error on whichever endpoint touches it first. The only recovery is "drop the database and rebuild" — which this repo's own history shows. That is acceptable for a prototype and unacceptable the moment there is data you cannot regenerate.

*What a migration tool actually buys you.* Alembic keeps an ordered chain of revisions and one `alembic_version` row in the target database recording where it currently sits. `upgrade head` computes and applies only the delta. Three properties follow: schema changes are **reviewable** (a diff in a file, not an implicit consequence of editing a model), **repeatable** (the same sequence on every environment), and **ordered** relative to the code that needs them.

*Autogenerate is a first draft, not an oracle.* It diffs `Base.metadata` against a live database and guesses. It reliably detects added/dropped tables and columns; it is unreliable about type changes, renames (a rename looks exactly like a drop plus an add — and a naive apply **destroys the data**), server defaults, and some index and constraint forms. **Always read the generated migration before applying it.** This is the step people skip, and it is where data loss happens.

*The baseline must be generated against an empty database.* Autogenerate emits the diff between your models and the target DB. Point it at your populated dev database — which already has every table from `create_all` — and the diff is empty, producing a migration that does nothing. Then a fresh environment runs `upgrade head`, gets no tables, and fails. Hence: generate against empty, then `stamp` the existing dev DB.

*`stamp` is the adoption primitive.* `alembic stamp head` writes the version row **without executing any DDL**. It means "this database already looks like head, take my word for it." That is precisely the safe way to bring an existing database under migration control: the tables are already correct, you only need to record where in the timeline they sit. Running `upgrade head` against dev instead would try to `CREATE TABLE` things that exist and abort.

*Why tests deliberately do NOT use migrations.* `backend/app/tests/conftest.py` keeps per-test `drop_all` / `create_all`. It is fast (~100ms), perfectly isolated, and immune to migration drift. If tests ran migrations, a bad migration would fail every test in the suite and you could not tell a behavior regression from a schema problem. **Migrations protect data; tests protect behavior.** Keeping them separate keeps failures diagnosable. The tradeoff is real and worth stating: migrations are then not exercised by the test suite, so Step 5's explicit upgrade-against-empty check is the thing standing in for that coverage. Do not skip it.

- [ ] **Step 1: Scaffold**

```bash
cd backend && uv run alembic init migrations
```

Creates `alembic.ini` and `migrations/` with `env.py`, `script.py.mako`, and an empty `versions/`.

- [ ] **Step 2: Rewrite `backend/migrations/env.py`**

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

import app.models  # noqa: F401  # registers every model on Base.metadata
from app.config import settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Two details that matter, both consequences of Task S1:

- `import app.models` must execute **before** `target_metadata` is read. After S1 removed the eager imports from `app/__init__.py`, importing `app.database` alone gives you an *empty* `Base.metadata`, and autogenerate would emit `drop_table` for every model. This is the same explicit-registration point as `main.py`, for the same reason.
- `set_main_option` overrides the URL hardcoded in `alembic.ini` with the application's settings, so migrations and the app can never target different databases. **Configuration should have one source; the `.ini` is a fallback, not a second truth.**

- [ ] **Step 3: Adjust `backend/alembic.ini`**

Change only the `[alembic]` section:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
# sqlalchemy.url is set at runtime by migrations/env.py from app.config.settings
```

**Keep the `[loggers]` / `[handlers]` / `[formatters]` sections the generator wrote.** `fileConfig(config.config_file_name)` in `env.py` parses them; deleting them makes every migration run crash with a `configparser.NoSectionError`.

- [ ] **Step 4: Generate the baseline against an EMPTY database**

```bash
docker compose up -d db
# jirani_test is not created by the testcontainers harness — create it by hand.
docker compose exec db psql -U postgres -c "CREATE DATABASE jirani_test;" 2>/dev/null || true
docker compose exec db psql -U postgres -d jirani_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_test uv run alembic revision --autogenerate -m "initial schema"
```

Note this is a *different* Postgres instance from the one the tests use (compose vs. testcontainers). That is deliberate and temporary — the baseline needs a stable, inspectable, empty database. Do not try to generate it against the throwaway test container.

- [ ] **Step 5: Review the generated migration — do not skip this**

```bash
ls backend/migrations/versions/
grep -E "create_table|create_index|op.drop" backend/migrations/versions/*_initial_schema.py
```

Expected: `create_table` for all **10** tables — `accounts`, `books`, `tags`, `book_tags`, `audio`, `audio_tags`, `video`, `video_tags`, plus any remaining join tables — the `roleenum` type, and the GIN index on the book JSONB column.

Two red flags:
- **Any `op.drop_*` in a baseline migration** means the target DB was not empty. Re-run Step 4's `DROP SCHEMA`.
- **A missing table** means `env.py` did not import its model. Confirm it is exported from `app/models/__init__.py`.

Then verify the migration actually runs on an empty DB:

```bash
docker compose exec db psql -U postgres -d jirani_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_test uv run alembic upgrade head
docker compose exec db psql -U postgres -d jirani_test -c "\dt"
```

Expected: all tables present, plus `alembic_version`.

- [ ] **Step 6: Adopt the existing dev database with `stamp`**

```bash
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_library uv run alembic stamp head
docker compose exec db psql -U postgres -d jirani_library -c "SELECT version_num FROM alembic_version;"
```

Expected: the revision hash prints. **No DDL runs and no data is touched** — this is the safety-critical step. If you accidentally run `upgrade` instead of `stamp` here, it will fail on `CREATE TABLE ... already exists`; that failure is harmless, but re-read this step before retrying.

- [ ] **Step 7: Remove `create_all` from `backend/app/main.py`**

The lifespan becomes:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.COVER_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    settings.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    engine.dispose()
```

Delete `Base.metadata.create_all(bind=engine)` and drop `Base` from the `from app.database import ...` line (keep `engine` — it is still used by `engine.dispose()`). **Keep `import app.models`** from S1: the ORM still needs its mappers configured at runtime even though it no longer creates tables.

*Concept:* the application should not mutate its own schema at startup. Schema changes are a deploy-time operation with different privileges, different failure handling, and a different audit trail than serving requests. Conflating them means every replica races to migrate on boot.

- [ ] **Step 8: Wire migrations into the container**

`docker/entrypoint.sh`:

```sh
#!/usr/bin/env sh
set -eu

mkdir -p /app/uploads/books /app/uploads/covers /app/uploads/audio /app/uploads/vids /app/data

uv run --no-sync alembic upgrade head

exec "$@"
```

`backend/Dockerfile` — the S4 version only copies `backend/app`, so the migration assets are absent and `alembic upgrade head` would die with `No such file or directory: 'alembic.ini'`. Add after the `COPY backend/app ./app` line:

```dockerfile
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
```

With `set -e`, a failed migration aborts the container before uvicorn starts. That is the desired behavior: **fail loudly on a bad schema rather than serving traffic against one.**

- [ ] **Step 9: End-to-end verification from a clean volume**

```bash
docker compose down -v
docker compose up -d --build
sleep 10
docker compose exec db psql -U postgres -d jirani_library -c "SELECT version_num FROM alembic_version;"
curl -s localhost:8000/ | grep -q "Welcome" && echo "API OK"
```

Expected: the revision hash prints and `API OK`. **`down -v` destroys the dev volume** — intentional here, since the whole point is proving a fresh environment builds itself from migrations. Do not run this against anything you care about.

- [ ] **Step 10: Full suite + commit**

```bash
cd backend && uv run pytest -v
git add backend/alembic.ini backend/migrations backend/app/main.py docker/entrypoint.sh backend/Dockerfile
git commit -m "feat: adopt Alembic — baseline migration, migrate on startup, drop create_all"
```

Tests must still pass: conftest uses `create_all` directly and is unaffected by the lifespan change.

---

### Task S6: Document the structure decisions

**Files:**
- Modify: `README.md`, `backend/pyproject.toml` (ruff/mypy config), `STATE.md`

**Why (learning):** A structural decision that is not written down gets reverted by the next person — or by you in three months. The specific things needing documentation are the ones that are now *non-obvious*: schema changes require a migration (previously automatic), and tests need Docker but not a manual database (surprising if you have not seen testcontainers).

Pinning ruff and mypy config in `pyproject.toml` is the same principle as Step S1's pytest config: **the tool's behavior should be a property of the repository, not of the invoking shell.** Otherwise your editor, your terminal, and CI each apply different rules and you get formatting churn in every diff.

- [ ] **Step 1: Rewrite the README "Notes" section**

```markdown
## Notes

- **Schema** is managed by Alembic and applied at container startup
  (`alembic upgrade head` in `docker/entrypoint.sh`). Locally:
  `cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.
- **Schema changes:** edit the model, then
  `uv run alembic revision --autogenerate -m "describe change"`,
  **review the generated file** (autogenerate cannot see renames — it emits a
  drop plus an add, which destroys data), then `uv run alembic upgrade head`.
- **Tests** use a testcontainers Postgres. You need a running Docker daemon,
  but no manual database: `cd backend && uv run pytest -v`.
- **Dependencies** live only in `backend/pyproject.toml`; `backend/uv.lock` is
  generated. Add with `uv add <pkg>` — never hand-edit the lock, and there is
  no `requirements.txt`.
- **Uploads** are written to `settings.AUDIO_DIR` / `UPLOAD_DIR` / `COVER_DIR` /
  `VIDEO_DIR`, all anchored to `backend/`. Never use a relative path for file I/O.
```

- [ ] **Step 2: Add tool config to `backend/pyproject.toml`**

```toml
[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.13"
```

(`I` = import sorting, `UP` = pyupgrade for 3.13 idioms, `B` = bugbear. B008 stays in `select` but is suppressed per-command while the pre-existing debt is unaddressed — FastAPI's `Depends()` default-argument idiom trips it by design.)

- [ ] **Step 3: Record the deferred items in STATE.md**

Note under known risks:
- Book/audio/video/tag modules still have **zero test coverage** — see the Deferred Work annex
- `Book.file_type` AttributeError and audio/video delete-missing 500s are **still live**
- Old DB rows written with CWD-relative paths may 404 on stream until re-uploaded
- Root `uploads/` is orphaned (or was merged — record which option Task S3 Step 6 took)

- [ ] **Step 4: Structure-phase gate**

```bash
cd backend && uv run ruff format . && uv run ruff check . --fix --ignore B008
cd backend && uv run mypy app/config.py app/main.py app/__init__.py --strict 2>&1 | tail -20
cd backend && uv run pytest -v
docker compose build jirani-backend
```

Expected: ruff clean; mypy reports only pre-existing errors (log them, do not fix unrelated files); tests pass; image builds.

- [ ] **Step 5: Commit**

```bash
graphify update .
git add -A
git commit -m "chore: document structure decisions, pin ruff/mypy config"
```

**Part A is complete.** The structure is now: one manifest, deterministic imports, config-driven paths, a reproducible image, and a versioned schema. Part B changes behavior; do not start it until the gate above is green.

---

# PART B — Auth system

### Task A1: Lock the auth behavior contract (`verify_password` + RBAC)

**Files:**
- Modify: `backend/app/services/auth_service.py` (`verify_password`, `create_user`, `bulk_create_users`)
- Modify: `backend/app/api/auth_router.py` (pass `current_user.role`)
- Test: `backend/app/tests/test_auth.py` (append)

**Interfaces:**
- Consumes: harness fixtures `client`, `db`, `setup_paths` + helpers `setup_admin`, `login`, `auth_headers` (importable as a package thanks to S1)
- Produces: `create_user(self, metadata: AccountCreateRequest, user_role: RoleEnum) -> tuple[Account, str]`; `verify_password` returns `bool`

**Why (learning):** Three lessons, one per defect.

*1. A predicate must not raise on the negative case.* `verify_password` is typed `-> bool` but returns `True` or raises `ValueError`. It can never return `False`. Every caller written against the signature is wrong: `authenticate_user` does `if not self.verify_password(...): return None` — the `return None` branch is **unreachable**, so a wrong password propagates an exception out of the service, past the router (which only catches `HTTPException`), into FastAPI's handler, and out as **500**. A login failure — the single most common event in an auth system — is reported as a server error. Worse, `/auth/change-password` calls it at line 74 *outside* any `try`, so a wrong current password is also a 500.

The general principle: **reserve exceptions for exceptional conditions.** "The password does not match" is an expected, routine outcome and belongs in the return value. A malformed *stored hash* is genuinely exceptional and should still raise — which is exactly what `pwd_context.verify` does on its own. So the fix is to stop interfering.

*2. An authorization check needs the actor, and this function never receives one.* `create_user(metadata)` takes only the account to create. The caller's identity is not a parameter, so the function **cannot** enforce a rule about who is allowed to do what. The router does gate on `RoleChecker([teacher, admin])`, but that is coarse: it answers "may you call this endpoint" and cannot answer "may you create *this* role." A teacher therefore creates other teachers and escalates laterally.

This is the difference between **authentication** (who are you), **coarse authorization** (may you reach this route), and **fine-grained authorization** (may you perform this operation on this object). The last needs both actor and target in scope. Note `bulk_create_users` already threads `user_role` correctly — the single-create path was simply missed, which is what happens when the same rule is implemented in two places.

*3. Exception type is API design.* `create_user` raises `PermissionError` for admin-role creation, and the router maps `PermissionError` → 403. But 403 means "you lack permission" and implies a different caller might succeed. Nobody can create an admin through this endpoint — `/setup` is the only bootstrap — so the request itself is malformed, which is **400**. Distinguishing "you may not" from "this is never valid" is not pedantry: a client can meaningfully retry a 403 with elevated credentials, and can never usefully retry this. The convention for this codebase: `ValueError` → 400, `PermissionError` → 403.

- [ ] **Step 1: Confirm the harness before touching anything**

```bash
cd backend && uv run pytest app/tests -v
```

Expected: passing. Part A's S1 made `app.tests` a real package, so the helper imports below resolve.

- [ ] **Step 2: Write the failing `verify_password` tests**

Append to `backend/app/tests/test_auth.py`:

```python
import pytest

from app.models import RoleEnum
from app.schemas import AccountCreateRequest
from app.services import AuthService


def test_verify_password_wrong_password_returns_false() -> None:
    hashed = AuthService.get_password_hash("right-password")
    assert AuthService.verify_password("wrong-password", hashed) is False


def test_verify_password_correct_returns_true() -> None:
    hashed = AuthService.get_password_hash("right-password")
    assert AuthService.verify_password("right-password", hashed) is True
```

These are pure static-method tests — no DB, no fixtures.

- [ ] **Step 3: Run and watch it fail**

```bash
cd backend && uv run pytest app/tests/test_auth.py -k "verify_password" -v
```

Expected: `test_verify_password_wrong_password_returns_false` FAILS with `ValueError: Invalid password format.` **That failure is the bug report** — it is the 500 reproduced at the unit level. Do not proceed until you have seen it.

- [ ] **Step 4: Fix `verify_password` (`auth_service.py:59-63`)**

Replace:

```python
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if pwd_context.verify(plain_password, hashed_password):
            return True
        raise ValueError("Invalid password format.")
```

with:

```python
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Return True on match, False on mismatch.

        Only raises if the *stored* hash is malformed, which is a real
        programming error rather than a failed login.
        """
        return pwd_context.verify(plain_password, hashed_password)
```

- [ ] **Step 5: Green**

```bash
cd backend && uv run pytest app/tests/test_auth.py -k "verify_password" -v
```

Expected: 2 passed. `authenticate_user`'s dead `return None` branch is now reachable, so `/auth/token` returns 401 instead of 500 — verified end-to-end in Task A3.

- [ ] **Step 6: Write the failing RBAC tests**

Add the helper and tests:

```python
def service_for(db) -> AuthService:
    from app.repositories import AuthRepo

    return AuthService(AuthRepo(db))


def test_create_admin_via_service_raises_value_error(db) -> None:
    with pytest.raises(ValueError):
        service_for(db).create_user(
            AccountCreateRequest(
                username="boss", role=RoleEnum.admin, first_name="A", last_name="B"
            ),
            user_role=RoleEnum.admin,
        )


def test_create_teacher_by_teacher_raises_permission_error(db) -> None:
    with pytest.raises(PermissionError):
        service_for(db).create_user(
            AccountCreateRequest(
                username="tea2", role=RoleEnum.teacher, first_name="A", last_name="B"
            ),
            user_role=RoleEnum.teacher,
        )


def test_create_teacher_by_admin_ok(db) -> None:
    account, _ = service_for(db).create_user(
        AccountCreateRequest(
            username="tea3", role=RoleEnum.teacher, first_name="A", last_name="B"
        ),
        user_role=RoleEnum.admin,
    )
    assert account.role == RoleEnum.teacher
```

Note `PermissionError` and `ValueError` are Python builtins — no import needed.

- [ ] **Step 7: Run — three distinct failures**

```bash
cd backend && uv run pytest app/tests/test_auth.py -k "create_admin or create_teacher" -v
```

Expected: all three fail with `TypeError: create_user() got an unexpected keyword argument 'user_role'` — the parameter does not exist yet. That single signature error masks the three underlying behaviors; after Step 8 they must all pass for the *right* reasons.

- [ ] **Step 8: Fix `create_user` (`auth_service.py:80-105`)**

```python
    def create_user(
        self, metadata: AccountCreateRequest, user_role: RoleEnum
    ) -> tuple[Account, str]:
        existing_user = self.get_user_by_username(metadata.username)
        if existing_user:
            raise ValueError(f"Username '{metadata.username}' is already taken.")
        if metadata.role == RoleEnum.admin:
            raise ValueError("Admin accounts can only be created via /setup.")
        if metadata.role == RoleEnum.teacher and user_role != RoleEnum.admin:
            raise PermissionError("Only admins can create teacher accounts.")

        if metadata.role == RoleEnum.student:
            password = self.generate_student_password()
            first_login = False
        elif metadata.role == RoleEnum.teacher:
            password = self.generate_teacher_password()
            first_login = True
        else:
            raise ValueError(
                "Only student and teacher accounts can be created via this endpoint."
            )

        hashed_password = self.get_password_hash(password)
        new_account = Account(
            username=metadata.username,
            hashed_password=hashed_password,
            role=metadata.role,
            first_name=metadata.first_name,
            last_name=metadata.last_name,
            first_login=first_login,
        )
        self.auth_repo.create_account(new_account)
        return new_account, password
```

Guards come before any work — **validate first, mutate second**, so a rejected request never leaves a partial write.

- [ ] **Step 9: Align `bulk_create_users` (`auth_service.py:171-172`)**

It already receives `user_role`, but raises `PermissionError` (→403) for the admin case. Make it consistent with `create_user`:

```python
        if bulk_data.role == RoleEnum.admin:
            raise ValueError("Admin accounts can only be created via /setup.")
        if bulk_data.role == RoleEnum.teacher and user_role != RoleEnum.admin:
            raise PermissionError("Only admins can create teacher accounts.")
```

**The same rule must produce the same status code on every endpoint that enforces it.** Divergent behavior between `/users` and `/users/bulk` is a bug even when each is individually defensible.

- [ ] **Step 10: Pass the caller's role from the router (`auth_router.py:95`)**

```python
        new_user, credential = auth_service.create_user(user_data, current_user.role)
```

No mapping changes needed — lines 97-100 already map `ValueError`→400 and `PermissionError`→403.

- [ ] **Step 11: Run + commit**

```bash
cd backend && uv run pytest app/tests/test_auth.py -v
```

Expected: all green, each for the right reason.

```bash
cd backend && uv run ruff format app/services/auth_service.py app/api/auth_router.py app/tests/ && uv run ruff check app/services/auth_service.py app/api/auth_router.py app/tests/ --ignore B008
git add backend/app/services/auth_service.py backend/app/api/auth_router.py backend/app/tests/test_auth.py
git commit -m "fix: auth defects — verify_password returns bool, RBAC on create_user, admin role 400"
```

---

### Task A2: Password rules, reset semantics, `/setup` race, literal prefixes

**Files:**
- Modify: `backend/app/services/auth_service.py` (`validate_credentials`, `reset_password`, `get_all_users`)
- Modify: `backend/app/repositories/auth_repo.py` (`change_password` param, `startswith`, `create_account` rollback, delete `has_admin`)
- Modify: `backend/app/api/auth_router.py` (`PermissionError`→403 on reset, `IntegrityError`→400)
- Modify: `backend/app/api/setup_router.py` (race hardening)
- Test: `backend/app/tests/test_auth.py` (append)

**Interfaces:**
- Consumes: Task A1 outputs
- Produces: student self-change = any chars, len ≥ 4; teacher resetting a teacher → 403; admin reset of a teacher keeps `first_login=True`; duplicate usernames → 400 even under a race; `/setup` never 500s; `%` in a bulk prefix is literal

**Why (learning):** Six defects; each teaches something different.

*1. Validation rules belong to policy, not to habit.* The student branch requires `password.isdigit()` — a 4-digit PIN. But the message says "4-digit number" while the check also enforces `len >= 4`, and the locked product decision is "≥4 characters, any characters." Rejecting `"cats"` is a usability bug that pushes students toward the ~10⁴ keyspace of digits. Also note `auth_schema.py` already enforces `min_length=4` at the Pydantic layer, so this check is partly redundant. **Where a rule lives matters:** schema-level validation is about *shape* (a string of plausible length) and belongs at the boundary; service-level validation is about *policy* (what this role is allowed) and belongs in the domain.

*2. An unhandled exception type is a 500.* `/reset-password` catches only `ValueError` (line 62). `reset_password` raises `PermissionError` when a teacher targets another teacher (line 145). Nothing catches it, so a **correctly enforced authorization rule is reported as a server error** — the security logic works and the response says the server is broken. Whenever a service can raise more than one exception type, the router must map all of them. The FastAPI-idiomatic alternative is an app-level exception handler registered once, so a new raise site cannot be forgotten; per-route mapping is fine here because there are two types and few routes, but the tradeoff is worth knowing.

*3. A flag with two meanings serves neither.* `change_password` hardcodes `account.first_login = False`, but two very different operations call it: a **self-change** (the user chose a password, so the flag should clear) and an **admin reset** (the user has a temporary password they have never seen, so the flag must stay set). Forcing `False` in both means a teacher whose password was reset is never prompted to change it. Fix: make the caller state its intent via a keyword-only parameter with the safe default. **Keyword-only (`*`) matters** — `change_password(user, pw, False)` at a call site is unreadable, and a positional boolean is easy to pass in the wrong slot. Forcing `first_login=True` makes every call site self-documenting.

*4. Check-then-act across a boundary is a race.* `/setup` checks `REVEALED_FLAG.exists()`, then creates the admin, then touches the flag. Between the create and the touch, the process can die — leaving an admin row with no flag. The next request sees no flag, tries to create the admin again, and `setup_admin_account` raises an uncaught `ValueError` → **500**. This is TOCTOU (time-of-check to time-of-use): the state you checked can change before you act. The robust pattern is to let the authoritative operation fail and handle that failure, rather than trying to predict it. Here the database's uniqueness on `username` is the real authority.

*5. The database has its own opinion about uniqueness, and it wins.* `create_user` checks `get_user_by_username` first, but two concurrent requests can both pass that check before either commits. One then violates the unique index and raises `IntegrityError` — uncaught, so **500**. The application-level check is still worth keeping (it gives a clean message in the common case), but it is an optimization, not a guarantee. **The database constraint is the correctness boundary; the app check is UX.** Handle both. The `rollback()` in the except block is mandatory: a failed transaction leaves the session unusable and every later query in that request would fail with a cascading, confusing error.

*6. Passing user input into a pattern-matching operator is injection-shaped.* `get_next_prefix_number` builds `Account.username.like(f"{prefix}%")`. In `LIKE`, `%` and `_` are wildcards, so a prefix of `a%1` matches far more than intended and the computed next number is wrong. This is the same class of bug as SQL injection — untrusted input reaching an interpreter that assigns special meaning to some characters — even though parameterization prevents actual SQL injection here. SQLAlchemy's `startswith()` auto-escapes the wildcards. **Prefer the operation that expresses your intent over the general-purpose one you then have to sanitize.**

*Also in scope:* delete `has_admin()` from `auth_repo.py:33-39` — verified zero call sites repo-wide. Dead code is not free: it must be read, understood, and maintained, and an untested method invites future use as if it were proven. Delete it; git remembers.

- [ ] **Step 1: Failing tests for the student password rule**

```python
def test_student_self_change_accepts_4_char_word() -> None:
    AuthService.validate_credentials(RoleEnum.student, "cats", context="self_change")


def test_student_self_change_rejects_3_chars() -> None:
    with pytest.raises(ValueError):
        AuthService.validate_credentials(RoleEnum.student, "cat", context="self_change")
```

```bash
cd backend && uv run pytest app/tests/test_auth.py -k "self_change" -v
```

Expected: the first FAILS (`"cats"` is not all digits); the second passes already.

- [ ] **Step 2: Fix `validate_credentials` (`auth_service.py:41-43`)**

```python
        elif context == "self_change" and role == RoleEnum.student:
            if len(password) < 4:
                raise ValueError("Password must be at least 4 characters for students.")
```

- [ ] **Step 3: Failing tests for reset mapping + `first_login`**

Add the conftest helper import at the top of the file (module-level functions, not fixtures — importable now that `app/tests/__init__.py` exists):

```python
from app.tests.conftest import auth_headers, login, setup_admin
```

Then shared helpers. Generated credentials are random, so **always read them from the create response — never guess**:

```python
def _create_teacher(client, token: str, username: str) -> str:
    response = client.post(
        "/auth/users",
        json={"username": username, "role": "teacher", "first_name": "T", "last_name": "U"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["credential"]


def _account_id(client, token: str, username: str) -> int:
    users = client.get("/auth/users", headers=auth_headers(token)).json()
    return next(u["id"] for u in users if u["username"] == username)
```

And the tests:

```python
def test_reset_teacher_password_as_teacher_is_403(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    _create_teacher(client, admin_token, "reset-victim")
    victim_id = _account_id(client, admin_token, "reset-victim")
    teacher_password = _create_teacher(client, admin_token, "reset-actor")
    teacher_token = login(client, "reset-actor", teacher_password)["access_token"]
    response = client.post(
        "/auth/reset-password",
        json={"account_id": victim_id},
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 403


def test_admin_reset_of_teacher_keeps_first_login_true(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    _create_teacher(client, admin_token, "teacherC")
    teacher_id = _account_id(client, admin_token, "teacherC")
    response = client.post(
        "/auth/reset-password",
        json={"account_id": teacher_id},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200
    new_password = response.json()["new_password"]
    me = client.get(
        "/auth/me",
        headers=auth_headers(login(client, "teacherC", new_password)["access_token"]),
    )
    assert me.json()["first_login"] is True
```

- [ ] **Step 4: Run — confirm both failures**

```bash
cd backend && uv run pytest app/tests/test_auth.py -k "reset_teacher or keeps_first_login" -v
```

Expected: the first FAILS with **500** (uncaught `PermissionError`); the second FAILS with `first_login == False`.

- [ ] **Step 5: Fix the router, repo, and service**

`backend/app/api/auth_router.py` — extend `/reset-password`'s handler (after line 62):

```python
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
```

`backend/app/repositories/auth_repo.py` — replace `change_password` (lines 41-46):

```python
    def change_password(
        self, account: Account, new_hashed_password: str, *, first_login: bool = False
    ) -> Account:
        account.hashed_password = new_hashed_password
        account.first_login = first_login
        self.db_session.commit()
        self.db_session.refresh(account)
        return account
```

`backend/app/services/auth_service.py` — in `reset_password` (line 150):

```python
        user.hashed_password = hashed_password
        self.auth_repo.change_password(
            user, user.hashed_password, first_login=user.role == RoleEnum.teacher
        )
        return user, password
```

The self-change path in `AuthService.change_password` keeps the default `first_login=False` — the user chose their own password, so the flag should clear.

- [ ] **Step 6: Failing tests for the `/setup` race and the `%` prefix**

```python
def test_setup_returns_403_when_admin_exists_but_flag_missing(client, setup_paths) -> None:
    client.get("/setup")
    (setup_paths / ".credentials_revealed").unlink()
    (setup_paths / ".credentials").unlink()
    response = client.get("/setup")
    assert response.status_code == 403


def test_bulk_prefix_with_percent_is_literal(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/users/bulk",
        json={"count": 2, "role": "student", "prefix": "a%1"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 201
    assert [a["username"] for a in response.json()["accounts"]] == ["a%1001", "a%1002"]
```

The race test deletes **both** files — that is what simulates a crash between the DB commit and the flag write. Deleting only the flag would take the `CREDENTIALS_FILE.exists()` branch and never reach the failing path.

- [ ] **Step 7: Harden `/setup` (`setup_router.py:30-33`)**

Wrap the creation so the authoritative operation's failure is handled instead of predicted:

```python
    if not CREDENTIALS_FILE.exists():
        password = secrets.token_urlsafe(8)
        credentials = {"username": "admin", "password": password}
        try:
            auth_service.setup_admin_account(credentials["password"])
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="admin credentials have already been revealed.",
            )
```

403 is right: the admin exists, so the bootstrap is genuinely over — the caller just lost the one chance to see the password. Recovery is an out-of-band password reset, not a retry.

- [ ] **Step 8: Fix the prefix and delete dead code (`auth_repo.py`)**

Line 51 — replace:

```python
                select(Account).where(Account.username.like(f"{prefix}%"))
```

with:

```python
                select(Account).where(Account.username.startswith(prefix))
```

Then delete `has_admin` (lines 33-39) entirely. If a future feature needs it, add it back **with tests**.

- [ ] **Step 9: Handle `IntegrityError` on the create paths**

`backend/app/repositories/auth_repo.py` — add `from sqlalchemy.exc import IntegrityError` at the top and make `create_account` fail cleanly:

```python
    def create_account(self, account: Account) -> Account:
        self.db_session.add(account)
        try:
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
        self.db_session.refresh(account)
        return account
```

The repo rolls back (restoring a usable session) and re-raises — **translating a database error into an HTTP status is the router's job, not the repository's.** Keeping `IntegrityError` here would leak persistence details into the domain; catching it silently would hide a real conflict.

`backend/app/api/auth_router.py` — import `from sqlalchemy.exc import IntegrityError` and add to **both** `create_user` and `bulk_create_users`:

```python
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Username conflict - please retry.")
```

- [ ] **Step 10: Fix the latent `get_all_users` crash (`auth_service.py:213-218`)**

`accounts` is only assigned in the teacher and admin branches. Any other role reaches the return statement with the name unbound → `UnboundLocalError` → 500. The router's `RoleChecker` makes it unreachable *today*, but that is a guarantee held by a different file:

```python
    def get_all_users(self, user_role: RoleEnum | None = None) -> list[AccountRead]:
        if user_role == RoleEnum.teacher:
            accounts = self.auth_repo.get_all_users(role=RoleEnum.student)
        elif user_role == RoleEnum.admin:
            accounts = self.auth_repo.get_all_users()
        else:
            raise PermissionError("Only teachers and admins can list users.")
        return [AccountRead.model_validate(account) for account in accounts]
```

**A function should be correct on its own terms, not because of who currently calls it.** An explicit raise turns a future refactor's silent 500 into a clear 403.

- [ ] **Step 11: Full run + commit**

```bash
cd backend && uv run pytest app/tests/test_auth.py -v
```

Expected: all green.

```bash
cd backend && uv run ruff format app/tests app/services/auth_service.py app/repositories/auth_repo.py app/api/auth_router.py app/api/setup_router.py && uv run ruff check app/tests app/services/auth_service.py app/repositories/auth_repo.py app/api/auth_router.py app/api/setup_router.py --ignore B008
git add -A
git commit -m "fix: reset-password 403 + first_login semantics, student min-4 rule, setup race, literal bulk prefix"
```

---

### Task A3: Complete the auth repo + API test suite

**Files:**
- Modify: `backend/app/tests/test_auth.py` (append repo + HTTP integration tests)

**Interfaces:**
- Consumes: `client` / `db` / `setup_paths` fixtures, helpers `setup_admin` / `login` / `auth_headers`, A1–A2 fixes
- Produces: coverage of `/setup`, `/auth/token`, `/auth/me`, `/auth/users`, `/auth/users/bulk`, `/auth/change-password`, `/auth/reset-password`, and every `AuthRepo` method

**Why (learning):** A1 and A2 wrote tests to *drive* fixes — each one started red and turned green. These tests do the complementary job: **characterization tests** that pin behavior which is already correct, so a future change that breaks it fails loudly. They should be green the moment you write them; if one is red, you found a bug the review missed — treat it as a finding, not a broken test.

Two things worth internalizing from the shape of this suite:

*Repo tests and API tests answer different questions.* The repo tests hit the database directly and verify one unit of persistence — fast, precise, and they fail with an obvious cause. The API tests drive the full stack through `TestClient` and verify wiring: dependency injection, `RoleChecker`, serialization, status codes. A bug in `get_next_prefix_number` shows up in both, but only the repo test tells you *where*. Neither replaces the other: the repo tests would all pass even if the router forgot to pass `current_user.role`.

*Test isolation is a design property.* The `reset_db` fixture is `autouse=True` and drops/recreates every table before each test, so tests can assume an empty database and can run in any order. Without it, `test_repo_next_prefix_continues_from_max` would see accounts created by earlier tests and produce a different number depending on the run order — the kind of flake that costs a day. **A test that depends on another test having run first is not a test, it is a fixture with extra steps.**

- [ ] **Step 1: Append the `AuthRepo` tests**

```python
def test_repo_get_by_username_found(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    AuthRepo(db).create_account(
        Account(username="findme", hashed_password="x", role=RoleEnum.student,
                first_name="A", last_name="B")
    )
    user = AuthRepo(db).get_by_username("findme")
    assert user is not None and user.username == "findme"


def test_repo_get_by_username_missing(db) -> None:
    from app.repositories import AuthRepo

    assert AuthRepo(db).get_by_username("ghost") is None


def test_repo_get_by_id_found_and_missing(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    created = AuthRepo(db).create_account(
        Account(username="byid", hashed_password="x", role=RoleEnum.student,
                first_name="A", last_name="B")
    )
    assert AuthRepo(db).get_by_id(created.id) is not None
    assert AuthRepo(db).get_by_id(999_999) is None


def test_repo_get_all_users_filters_by_role(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    repo = AuthRepo(db)
    repo.create_account(Account(username="s1", hashed_password="x", role=RoleEnum.student, first_name="A", last_name="B"))
    repo.create_account(Account(username="t1", hashed_password="x", role=RoleEnum.teacher, first_name="A", last_name="B"))
    assert {u.username for u in repo.get_all_users()} == {"s1", "t1"}
    assert {u.username for u in repo.get_all_users(role=RoleEnum.student)} == {"s1"}


def test_repo_next_prefix_empty(db) -> None:
    from app.repositories import AuthRepo

    assert AuthRepo(db).get_next_prefix_number("stu") == 1


def test_repo_next_prefix_continues_from_max(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    AuthRepo(db).create_account(Account(username="stu001", hashed_password="x", role=RoleEnum.student, first_name="A", last_name="B"))
    AuthRepo(db).create_account(Account(username="stu005", hashed_password="x", role=RoleEnum.student, first_name="A", last_name="B"))
    assert AuthRepo(db).get_next_prefix_number("stu") == 6


def test_repo_next_prefix_ignores_non_digit_suffix(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    AuthRepo(db).create_account(Account(username="stuabc", hashed_password="x", role=RoleEnum.student, first_name="A", last_name="B"))
    assert AuthRepo(db).get_next_prefix_number("stu") == 1


def test_repo_change_password_first_login_default_false(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    repo = AuthRepo(db)
    account = repo.create_account(
        Account(username="cpw", hashed_password="old", role=RoleEnum.teacher,
                first_name="A", last_name="B")
    )
    assert repo.change_password(account, "new").first_login is False


def test_repo_change_password_can_keep_first_login(db) -> None:
    from app.models import Account
    from app.repositories import AuthRepo

    repo = AuthRepo(db)
    account = repo.create_account(
        Account(username="cpw2", hashed_password="old", role=RoleEnum.teacher,
                first_name="A", last_name="B")
    )
    assert repo.change_password(account, "new", first_login=True).first_login is True
```

The last two pin the A2 keyword-only parameter in both directions — the default and the override.

- [ ] **Step 2: Append the HTTP integration tests**

`auth_headers` / `login` / `setup_admin` and `_create_teacher` / `_account_id` were already added in A2 Step 3 — **do not redefine them.**

```python
# --- /setup ---------------------------------------------------------------

def test_setup_first_visit_generates_admin(client, setup_paths) -> None:
    response = client.get("/setup")
    assert response.status_code == 200
    assert "admin" in response.json()["message"]
    assert (setup_paths / ".credentials").exists()


def test_setup_second_visit_returns_403(client, setup_paths) -> None:
    client.get("/setup")
    assert client.get("/setup").status_code == 403


# --- /auth/token ----------------------------------------------------------

def test_login_admin_success(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    body = login(client, "admin", admin_password)
    assert body["role"] == "admin"
    assert body["access_token"]


def test_login_teacher_first_login_true(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    password = _create_teacher(client, admin_token, "login-tea")
    assert login(client, "login-tea", password)["first_login"] is True


def test_login_student_first_login_false(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    bulk = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "stl"},
        headers=auth_headers(admin_token),
    )
    credential = bulk.json()["accounts"][0]["password"]
    assert login(client, "stl001", credential)["first_login"] is False


def test_login_wrong_password_is_401(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    _create_teacher(client, admin_token, "wrong-pw")
    response = client.post("/auth/token", json={"username": "wrong-pw", "password": "nope"})
    assert response.status_code == 401
```

`test_login_wrong_password_is_401` is the end-to-end proof of the A1 `verify_password` fix — before it, this returned 500.

```python
# --- /auth/me -------------------------------------------------------------

def test_me_returns_current_user(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_password)["access_token"]
    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_me_without_token_rejected(client) -> None:
    assert client.get("/auth/me").status_code in (401, 403)


# --- /auth/users ----------------------------------------------------------

def test_create_student_by_admin(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/users",
        json={"username": "stu1", "role": "student", "first_name": "S", "last_name": "U"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 201
    assert len(response.json()["credential"]) == 6


def test_create_admin_by_admin_is_400(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/users",
        json={"username": "boss", "role": "admin", "first_name": "A", "last_name": "B"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_create_teacher_by_teacher_is_403(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    teacher_password = _create_teacher(client, admin_token, "tea-owner")
    teacher_token = login(client, "tea-owner", teacher_password)["access_token"]
    response = client.post(
        "/auth/users",
        json={"username": "tea2", "role": "teacher", "first_name": "A", "last_name": "B"},
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 403


def test_create_duplicate_username_is_400(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    _create_teacher(client, admin_token, "dup-user")
    response = client.post(
        "/auth/users",
        json={"username": "dup-user", "role": "student", "first_name": "D", "last_name": "U"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 400


# --- /auth/users/bulk -----------------------------------------------------

def test_bulk_create_students_by_admin(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/users/bulk",
        json={"count": 3, "role": "student", "prefix": "bu"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 201
    assert [a["username"] for a in response.json()["accounts"]] == ["bu001", "bu002", "bu003"]


def test_bulk_create_teacher_by_teacher_is_403(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    teacher_password = _create_teacher(client, admin_token, "b-tea")
    teacher_token = login(client, "b-tea", teacher_password)["access_token"]
    response = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "teacher", "prefix": "tb"},
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 403


def test_bulk_create_admin_is_400(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "admin", "prefix": "ab"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 400
```

`test_bulk_create_admin_is_400` pins the A1 Step 9 consistency fix — it returned 403 before.

```python
# --- /auth/change-password -------------------------------------------------

def test_student_changes_own_password_then_relogin(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    bulk = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "cp"},
        headers=auth_headers(admin_token),
    ).json()
    old_password = bulk["accounts"][0]["password"]
    token = login(client, "cp001", old_password)["access_token"]
    response = client.post(
        "/auth/change-password",
        json={"old_password": old_password, "new_password": "newpwd4"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert login(client, "cp001", "newpwd4")["access_token"]


def test_change_password_wrong_old_password_is_400(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    bulk = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "wo"},
        headers=auth_headers(admin_token),
    ).json()
    old_password = bulk["accounts"][0]["password"]
    token = login(client, "wo001", old_password)["access_token"]
    response = client.post(
        "/auth/change-password",
        json={"old_password": "totally-wrong", "new_password": "newpwd4"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_change_password_sets_first_login_false(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    bulk = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "fl"},
        headers=auth_headers(admin_token),
    ).json()
    old_password = bulk["accounts"][0]["password"]
    token = login(client, "fl001", old_password)["access_token"]
    client.post(
        "/auth/change-password",
        json={"old_password": old_password, "new_password": "newpwd4"},
        headers=auth_headers(token),
    )
    me = client.get(
        "/auth/me",
        headers=auth_headers(login(client, "fl001", "newpwd4")["access_token"]),
    )
    assert me.json()["first_login"] is False


# --- /auth/reset-password -------------------------------------------------

def test_teacher_resets_student(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "rs"},
        headers=auth_headers(admin_token),
    )
    student_id = _account_id(client, admin_token, "rs001")
    teacher_password = _create_teacher(client, admin_token, "reset-tea")
    teacher_token = login(client, "reset-tea", teacher_password)["access_token"]
    response = client.post(
        "/auth/reset-password",
        json={"account_id": student_id},
        headers=auth_headers(teacher_token),
    )
    assert response.status_code == 200
    assert login(client, "rs001", response.json()["new_password"])


def test_reset_missing_account_is_404(client, setup_paths) -> None:
    admin_password = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_password)["access_token"]
    response = client.post(
        "/auth/reset-password",
        json={"account_id": 999999},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 404


# NOTE: test_reset_teacher_password_as_teacher_is_403 and
# test_admin_reset_of_teacher_keeps_first_login_true are defined in A2 Step 3.
```

`test_change_password_wrong_old_password_is_400` covers the *second* `verify_password` call site — `auth_router.py:74`, outside any `try` — which returned 500 before A1.

- [ ] **Step 3: Run the whole file**

```bash
cd backend && uv run pytest app/tests/test_auth.py -v
```

Expected: all green. Any red test here is a genuine finding — investigate, do not adjust the assertion to match the behavior.

- [ ] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/ && uv run ruff check app/tests/ --ignore B008
git add backend/app/tests/test_auth.py
git commit -m "test: complete auth API and repo coverage"
```

- [ ] **Step 5: Final gate**

```bash
cd backend && uv run ruff format . && uv run ruff check . --fix --ignore B008
cd backend && uv run mypy app/services/auth_service.py app/repositories/auth_repo.py app/api/auth_router.py --strict 2>&1 | tail -20
cd backend && uv run pytest -v
graphify update .
git add -A
git commit -m "chore: refresh knowledge graph after structure and auth work"
```

Expected: ruff clean; mypy reports only pre-existing errors (log in STATE.md); full suite green.

---

## Learning Annex — cross-cutting concepts

Task-specific reasoning lives in each task's **Why (learning)** section. These are the themes that recur across several tasks.

1. **Explicit over implicit, especially for side effects.** The same lesson appears three times: model registration (`import app.models` in both `main.py` and `migrations/env.py`), package declaration (`__init__.py`), and tool configuration (`pyproject.toml`). In each case something *worked by accident* — an eager import, pytest's path insertion, the current working directory. Accidental mechanisms fail silently when the context changes, and the resulting error appears far from the cause. Name the dependency at the point where it matters.

2. **Errors are part of your API design.** `verify_password` raising instead of returning `False`, `PermissionError` used where `ValueError` belongs, `IntegrityError` escaping as a 500 — all the same mistake at different layers. Decide deliberately: *expected* outcomes are return values; *exceptional* ones are exceptions; and each exception type maps to exactly one status code (here: `ValueError`→400, `PermissionError`→403, not-found→404). Then enforce the mapping consistently — `/users` and `/users/bulk` disagreeing about admin creation was a bug even though each was individually defensible.

3. **Know where the correctness boundary is.** The app's `get_by_username` check is UX; the database's unique index is correctness. The `RoleChecker` on a route is coarse authorization; the check inside `create_user` is fine-grained. In both pairs, the outer layer is an optimization or convenience and the inner one is the guarantee. Bugs come from mistaking one for the other — which is exactly what `get_all_users(None)` does when it relies on a decorator in a different file to stay correct.

4. **Anything derived must be generated, never maintained by hand.** `requirements.txt` drifted from `pyproject.toml` because a human had to remember to sync it. `uv.lock` does not drift because a tool writes it and `--frozen` fails the build if it disagrees. Apply the same test to any file you are about to edit: is this the source of truth, or a copy of one?

5. **Time-of-check to time-of-use.** `/setup`'s flag check and the duplicate-username check are the same bug shape: verify a condition, then act on it, with a window in between where the world can change. The fix is not a better check — it is letting the authoritative operation (the unique constraint, the admin-exists error) fail and handling that failure.

6. **Test isolation is a design property, not a convenience.** `reset_db` being `autouse` means no test can depend on another's leftovers, so tests can run in any order and a failure names one cause. The Postgres choice matters for the same reason: SQLite would silently accept `JSONB`/GIN SQL that Postgres rejects, making green tests meaningless for the deployed system. **Test against what you deploy.**

7. **Deleting code is a contribution.** `has_admin()` had zero call sites. Dead code still has to be read, still shows up in searches, and — being untested — invites a future caller to trust it. Git is the archive; the working tree is for code that runs.

8. **Tests come in two kinds and you need both.** A1/A2 wrote tests that fail first, proving the bug exists and then proving the fix works. A3 wrote tests against already-correct behavior so future changes cannot break it silently. Confusing the two leads to writing "tests" that only assert what the code already does — worthless as bug-finders, valuable only as regression nets.

9. **Migrations protect data; tests protect behavior.** Deliberately kept separate: the test conftest uses `create_all`, and dev/prod use Alembic. Mixing them makes a bad migration fail the entire suite, at which point you cannot distinguish a schema problem from a behavior regression. The cost is that migrations get no coverage from the suite — accepted, and offset by S5's explicit upgrade-against-empty verification.

10. **The runtime environment is part of the dependency contract.** Python 3.13 in `pyproject.toml` and 3.11 in the Dockerfile is the same category of error as an unpinned library. So is a CWD-relative upload path: it makes the *filesystem layout* an implicit dependency on how the process was launched. Anchor to code (`__file__`) or to explicit config — never to ambient state.

---

## Deferred Work — preserved for a later pass

Cut from this plan to keep the scope on structure + auth. Everything below was verified live on 2026-08-15 and is **still broken**. Nothing here is lost; it is a ready-to-execute backlog.

### D1: Book module tests + `file_type` bug
- **Bug:** `backend/app/repositories/book_repo.py:122-123` filters on `Book.file_type`, but the column is `book_type` → `AttributeError` (500) on any `/books/search/?file_type=...` request.
- **Bug:** `backend/app/services/book_service.py:226` passes `file_type=` to `BookCreate`, which is silently dropped (`extra="ignore"`) → the MIME type is never persisted.
- **Tests needed:** `test_book_repo.py` (~15 cases: JSONB `metadata_`, tag normalization/reuse via `ilike`, orphan tag cleanup on delete, the search matrix) and `test_book_api.py` (~17 cases: upload validation, PDF magic-byte check, epub, tags, details, search, stream, update, delete).
- **Note:** these must run against Postgres — the JSONB + GIN index is not expressible in SQLite.
- **Caveat found during review:** the planned `_pdf_bytes()` fixture is a stub trailer. If PyMuPDF thumbnail generation is not inside a caught block, several upload tests will fail for reasons unrelated to what they test. Verify the router's error handling before writing the fixtures.

### D2: Audio / video / tag tests + delete-500 bug
- **Bug:** `audio_repo.py:17-22` `delete_audio` and `video_repo.py:18-23` `delete_video` dereference `None.deleted_at` when the id does not exist → 500. Fix: raise `ValueError(f"... {id} does not exist")` and map to 404 in `audio_router.py:122-126` and `video_router.py:111-114`.
- **Tests needed:** repo tests for soft-delete semantics (`deleted_at`) and API tests for upload / upload_multiple / list-excludes-deleted / patch / stream / delete-404.

### D3: SQLAlchemy 2.0 conversion for the remaining repos
`Account` / `Book` / `Tag` are 2.0 `Mapped[]` style; `Audio` / `Video` and their join tables are legacy 1.x `Column`. `BookRepo` and `TagRepo` still use `query()` while `AuthRepo` is 2.0 `select()`. **Do D1 and D2 first** — their tests are what makes this conversion verifiable, exactly as the auth tests here made `a034adf` safe.

### D4: Directory rename `uploads/vids` → `uploads/videos`
Cosmetic, but it touches on-disk layout, the Dockerfile `mkdir`, and existing DB `file_path` values. Needs a data migration; not worth bundling with anything else.

---

## Self-Review

- **Scope check:** the user asked for folder-structure system design first, then auth. Part A (S1–S6) is structure; Part B (A1–A3) is auth; the book/audio/video/tag work is in Deferred. The one deliberate crossover is S3 touching `audio_router.py` and `video_router.py` — path anchoring only, no behavior change, and their bugs stay in D2.
- **Ordering dependencies:** S1 (packaging) → everything, because `app.tests` must be a package before A1's helper imports and `import app.models` must be explicit before S5's autogenerate. S2 (manifests) → S4, since the Dockerfile installs from the lock S2 keeps. S4 (entrypoint wiring) → S5, since migrations run from the entrypoint S4 makes live. A1 → A2 → A3, since A2 builds on `create_user`'s new signature and A3 assumes both.
- **Verified against the tree:** every file path, line number, and defect in this plan was confirmed on 2026-08-15. Five errors in the previous revision are documented in the Corrections table.
- **Placeholder scan:** no TBD/TODO. Every step has literal code or an exact command plus expected output.
- **Type consistency:** `create_user(metadata, user_role)` threaded through the router; `change_password(account, hash, *, first_login=False)` matches the `reset_password` call; fixtures match the committed conftest exactly (`db`, `client`, `setup_paths`, and module-level `setup_admin`/`login`/`auth_headers`); `settings.AUDIO_DIR`/`VIDEO_DIR` added in S3 and consumed by the routers and the lifespan.
- **Known risks:** (1) S5 Step 9's `docker compose down -v` destroys the dev volume — intentional, but do not run it against data you need; (2) baseline autogenerate may miss the GIN index — Step 5 requires manual review; (3) DB rows written with old CWD-relative paths will 404 on stream until re-uploaded; (4) generated passwords are random, so tests must read credentials from create/bulk responses and never guess them; (5) S1's `app/__init__.py` rewrite is the highest-blast-radius change in Part A — Step 7's import checks exist specifically to catch a missed call site.

---

## Execution Handoff

Two options:

1. **Subagent-Driven (recommended)** — one fresh subagent per task, review between tasks. The task boundaries here are deliberately clean: each has its own files, its own verification command, and its own commit.
2. **Inline Execution** — work through the tasks in this session with checkpoints via superpowers:executing-plans.

Suggested checkpoints regardless of mode: after **S1** (highest blast radius in Part A), after **S6** (Part A gate — do not start Part B until it is green), and after **A2** (all auth fixes landed, before the characterization suite).





