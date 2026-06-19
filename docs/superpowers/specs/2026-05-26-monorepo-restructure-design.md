# Monorepo Restructure: Jirani Offline Library

## Overview
Restructure the flat Jirani Offline Library backend into a monorepo with Turborepo, splitting the codebase into `backend/` (FastAPI) and `frontend/` (React + Vite). The React build is served by FastAPI via `StaticFiles` for production.

## Directory Structure

```
jirani/
├── backend/
│   ├── app/                  # existing FastAPI code
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── dependencies/
│   │   ├── scripts/
│   │   ├── tests/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── uploads/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .python-version
│   └── Dockerfile
├── frontend/                 # empty — scaffold later
├── docker/
│   └── entrypoint.sh
├── docker-compose.yml
├── .gitignore
├── .dockerignore
├── .env.example
├── AGENTS.md
├── README.md
├── memory.md
└── graphify-out/
```

## Docker Build

### `backend/Dockerfile`
Move existing `Dockerfile` to `backend/`. No content changes.

### docker-compose.yml
- `build.dockerfile` changes from `Dockerfile` → `backend/Dockerfile`
- `context: .` stays the same

## Migration Steps
1. Move `app/`, `requirements.txt`, `pyproject.toml`, `.python-version`, `Dockerfile` into `backend/`
2. Create empty `frontend/` directory
3. Update `docker-compose.yml` to point to `backend/Dockerfile`
4. Update internal references from `jirani_offline_library_backend` → `jirani` (in `.env.example`, `AGENTS.md`, `README.md`, etc.)
