# Monorepo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flat project into a monorepo with `backend/` and `frontend/` directories.

**Architecture:** Move all backend code into `backend/`, create empty `frontend/`, update Docker path, clean up orphaned root files.

**Tech Stack:** Python, FastAPI, Docker

**Status (2026-08-24):** Task 1 and Task 3 are complete — verified against the tree and git history (`db48836`, `e81a7ed`). Task 2's root-files cleanup also landed (`939fdad`), but the `frontend/` directory it created was empty, so git never tracked it and it no longer exists on checkout. The actual frontend landing is still pending the stack decision this semester (see the 2026-08-25 team-config design session) — it will create `frontend/` with real content or a `.gitkeep`.

---

### Task 1: Create `backend/` directory and move backend files

**Files:**
- Create: `backend/`
- Move: `app/` → `backend/app/`
- Move: `pyproject.toml` → `backend/pyproject.toml`
- Move: `Dockerfile` → `backend/Dockerfile`
- Note (accounted): `requirements.txt` moved here originally, then deliberately deleted by hygiene S2 (`547d18b`) — `backend/pyproject.toml` + `uv.lock` are now the single manifest. `.python-version` no longer exists anywhere; the toolchain pins `requires-python` in `pyproject.toml`.

- [x] **Step 1: Create backend directory and move files**

```bash
mkdir backend
mv app/ backend/
mv requirements.txt backend/
mv pyproject.toml backend/
mv .python-version backend/
mv Dockerfile backend/
```

- [x] **Step 2: Verify the move**

```bash
ls backend/
```
Expected (2026-08-24 tree): `app/`, `pyproject.toml`, `uv.lock`, `Dockerfile` + later additions (`alembic.ini`, `migrations/`, `conftest.py`, `data/`, `uploads/`)

- [x] **Step 3: Commit**

Landed as `db48836` — "refactor: move backend code into backend/ directory".

### Task 2: Create frontend directory and clean up root

**Files:**
- Create: `frontend/`
- Delete: `package.json`
- Delete: `package-lock.json`

- [x] **Step 1: Create frontend directory and remove orphaned root files**

Executed and landed as `939fdad`. The `rm` half is permanent — no `package.json` / `package-lock.json` at root (verified 2026-08-24). The `mkdir frontend` half did not stick: git does not track empty directories, so after that commit the directory only exists on machines that still have the working tree from the day.

- [x] **Step 2: Verify cleanup**

```bash
ls -la
```
Expected (2026-08-24 tree): `backend/`, `docs/`, `docker/`, `docker-compose.yml`, `.dockerignore`, `.gitattributes`, `.opencode/`, `AGENTS.md`, `README.md`, `STATE.md`, `.graphifyignore`. No root `package.json` / `package-lock.json`.

- [x] **Step 3: Commit**

Landed as `939fdad` — "refactor: create empty frontend/ directory, remove orphaned root package files".

- [ ] **Step 4: Land the frontend directory for real (pending — this semester)**

Stack decision drives this. Create `frontend/` with real content or a `.gitkeep` so git tracks it; CI gains the frontend gate slot per the frontend-ready CI design (2026-08-25 team-config session); the `2026-05-26-monorepo-restructure` plan then reads fully complete or is superseded by the frontend plan.

### Task 3: Update docker-compose.yml to point to backend/Dockerfile

**Files:**
- Modify: `docker-compose.yml`

- [x] **Step 1: Update Dockerfile path**

In `docker-compose.yml`, change:
```yaml
      dockerfile: Dockerfile
```
to:
```yaml
      dockerfile: backend/Dockerfile
```

- [x] **Step 2: Verify the change**

```bash
grep dockerfile docker-compose.yml
```
Expected: `dockerfile: backend/Dockerfile` (verified 2026-08-24)

- [x] **Step 3: Commit**

Landed as `e81a7ed` — "refactor: update docker-compose to use backend/Dockerfile".
