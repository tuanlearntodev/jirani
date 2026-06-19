# Monorepo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flat project into a monorepo with `backend/` and `frontend/` directories.

**Architecture:** Move all backend code into `backend/`, create empty `frontend/`, update Docker path, clean up orphaned root files.

**Tech Stack:** Python, FastAPI, Docker

---

### Task 1: Create `backend/` directory and move backend files

**Files:**
- Create: `backend/`
- Move: `app/` → `backend/app/`
- Move: `requirements.txt` → `backend/requirements.txt`
- Move: `pyproject.toml` → `backend/pyproject.toml`
- Move: `.python-version` → `backend/.python-version`
- Move: `Dockerfile` → `backend/Dockerfile`

- [ ] **Step 1: Create backend directory and move files**

```bash
mkdir backend
mv app/ backend/
mv requirements.txt backend/
mv pyproject.toml backend/
mv .python-version backend/
mv Dockerfile backend/
```

- [ ] **Step 2: Verify the move**

```bash
ls backend/
```
Expected: `app/`, `requirements.txt`, `pyproject.toml`, `.python-version`, `Dockerfile`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move backend code into backend/ directory"
```

### Task 2: Create frontend directory and clean up root

**Files:**
- Create: `frontend/`
- Delete: `package.json`
- Delete: `package-lock.json`

- [ ] **Step 1: Create frontend directory and remove orphaned root files**

```bash
mkdir frontend
rm package.json package-lock.json
```

- [ ] **Step 2: Verify cleanup**

```bash
ls -la
```
Expected: `backend/`, `frontend/`, `docker-compose.yml`, `.gitignore`, etc. No `package.json` or `package-lock.json` at root.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: create empty frontend/ directory, remove orphaned root package files"
```

### Task 3: Update docker-compose.yml to point to backend/Dockerfile

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update Dockerfile path**

In `docker-compose.yml`, change:
```yaml
      dockerfile: Dockerfile
```
to:
```yaml
      dockerfile: backend/Dockerfile
```

- [ ] **Step 2: Verify the change**

```bash
grep dockerfile docker-compose.yml
```
Expected: `dockerfile: backend/Dockerfile`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: update docker-compose to use backend/Dockerfile"
```
