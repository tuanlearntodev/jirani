# Graph Report - jirani  (2026-08-15)

## Corpus Check
- 57 files · ~30,912 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 450 nodes · 756 edges · 32 communities (26 shown, 6 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 157 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b016b381`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 31|Community 31]]

## God Nodes (most connected - your core abstractions)
1. `Auth System Redesign — Implementation Plan (Learning Edition)` - 29 edges
2. `AuthService` - 24 edges
3. `Book Feature Refactor — Implementation Plan (Learning Edition)` - 22 edges
4. `TagCreate` - 19 edges
5. `BookService` - 19 edges
6. `TagRead` - 17 edges
7. `RoleChecker` - 16 edges
8. `BookRepo` - 16 edges
9. `Audio_Repo` - 14 edges
10. `Tag` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Session` --uses--> `BookCreate`  [INFERRED]
  backend/app/repositories/book_repo.py → backend/app/schemas/book_schema.py
- `login()` --calls--> `TokenResponse`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/schemas/auth_schema.py
- `LoginRequest` --uses--> `AuthService`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/services/auth_service.py
- `ResetPasswordRequest` --uses--> `AuthService`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/services/auth_service.py
- `ChangePasswordRequest` --uses--> `AuthService`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/services/auth_service.py

## Import Cycles
- 1-file cycle: `backend/app/__init__.py -> backend/app/__init__.py`
- 1-file cycle: `backend/app/api/__init__.py -> backend/app/api/__init__.py`
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`

## Communities (32 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (25): delete_book(), get_book_details(), _get_book_file_path(), get_book_service(), _iter_file_chunks(), Get book details by UID., Teacher endpoint to update book metadata and optional cover., Teacher endpoint to delete a book by UID. (+17 more)

### Community 1 - "Community 1"
Cohesion: 0.17
Nodes (28): AccountCreateResponse, bulk_create_users(), change_password(), create_user(), get_all_users(), get_auth_service(), get_user_by_id(), login() (+20 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (28): _build_audio_view(), delete_audio(), get_audio(), stream_audio(), update_audio(), upload_audio(), upload_multiple(), validate_audio() (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (18): _build_video_view(), delete_video(), get_videos(), stream_video(), update_video(), upload_file(), upload_multiple(), Session (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (36): Auth System Redesign — Implementation Plan (Learning Edition), File Map, Final verification, `GET /auth/me` (current user — new), `GET /auth/users` (list users — new), How to read this plan, Important: SQLite schema reset, `POST /auth/change-password` (fix) (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (4): Account, RoleEnum, Session, AuthRepo

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (8): AuthRepo, Account, AccountCreateRequest, AccountRead, BulkCreateRequest, BulkCreateResponse, RoleEnum, AuthService

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (13): get_auth_service(), setup_page(), get_secret_key(), Settings, lifespan(), AuthService, Session, Account (+5 more)

### Community 8 - "Community 8"
Cohesion: 0.18
Nodes (10): Constraints, Context, Design, Design: Mass Account Creation for Students/Teachers, Endpoint: `POST /auth/users/bulk`, Error Handling, Future: Spreadsheet Upload, Problem (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.20
Nodes (9): 1. Single Table: `accounts`, 2. Role Enum, 3. Credential Policy (matched to digital literacy level), 4. Account Creation, 5. First Admin Bootstrap, 6. Zero-Config Deployment, Auth System Redesign — Design Spec, Context (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (10): Build & Test Commands (Definition of Done), Cross-Machine Setup, Execution Boundaries, External Knowledge & Global Search (MCPs), Failure Protocol, graphify — MUST USE FIRST, OpenCode Agent Instructions, Operating Mode: Advisory Assistant (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (8): Approach (Recommended), Components, Data Flow, Docker entrypoint upload dirs, Error Handling, Goal, Scope, Testing

### Community 13 - "Community 13"
Cohesion: 0.23
Nodes (18): BaseModel, AccountBase, AccountCreateRequest, AccountCreateResponse, AccountRead, BulkCredentialItem, TokenResponse, BookBase (+10 more)

### Community 14 - "Community 14"
Cohesion: 0.23
Nodes (7): get_all_tags(), Session, Session, TagCreate, TagCreate, TagRepo, Tag

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (7): `backend/Dockerfile`, Directory Structure, Docker Build, docker-compose.yml, Migration Steps, Monorepo Restructure: Jirani Offline Library, Overview

### Community 17 - "Community 17"
Cohesion: 0.40
Nodes (4): Monorepo Restructure Implementation Plan, Task 1: Create `backend/` directory and move backend files, Task 2: Create frontend directory and clean up root, Task 3: Update docker-compose.yml to point to backend/Dockerfile

### Community 20 - "Community 20"
Cohesion: 0.09
Nodes (22): Book Feature Refactor — Implementation Plan (Learning Edition), File Map, How to read this plan, Important: PostgreSQL schema reset, Task 10: Create `CoverGenerator`, Task 11: Shrink `BookService` to thin orchestration, Task 12: Rewrite `book_router.py` (auth guards, Range streaming, paginated list), Task 13: Update `main.py` (if needed) (+14 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (12): Path, UploadFile, BookBase, BookRead, BookRepo, BookUpload, BookService, Validate book file content matches its extension (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (18): 1. Decompose the god class into focused modules, 2. Data model — single `books` table, SQLAlchemy 2.0, hybrid attributes, 3. Extensible search — one criteria object, one dynamic builder, 4. Streaming — one endpoint, HTTP Range / 206, 5. CRUD + auth — RoleChecker, matching the auth router, 6. Error layering — services raise domain errors, routers map to HTTP, 7. Logging, not print, 8. Type hints + strict mypy (+10 more)

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (9): Instructions, On commit confirmation ("yes", "commit it", "go ahead", etc.), On "remind me to do X", On "session handoff" / "switching machines", On task completion, Rules, STATE.md template, What I do (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.25
Nodes (7): Current State, Decisions Log, Graveyard (Tried & Didn't Work), In Progress, Next Steps, Project State — Jirani Offline Library Backend, Remind Me (Future)

### Community 25 - "Community 25"
Cohesion: 0.29
Nodes (6): 1. Build and start containers, 2. Stop containers, 3. Stop containers and remove database volume, Jirani Offline Library Backend, Notes, Run With Docker

### Community 26 - "Community 26"
Cohesion: 0.40
Nodes (4): Instructions, Rules, What I do, When to use me

### Community 31 - "Community 31"
Cohesion: 0.25
Nodes (7): Blockers / Warnings, Briefing — Wednesday, Aug 12 2026, Done So Far, Next Up, Reminders, Today's Plan (30 min), Urgent (Overdue from last session)

## Knowledge Gaps
- **152 isolated node(s):** `@opencode-ai/plugin`, `Session`, `Session`, `RoleEnum`, `Session` (+147 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FastAPI` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 14`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `TagCreate` connect `Community 13` to `Community 0`, `Community 3`, `Community 14`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `BookService` connect `Community 21` to `Community 0`, `Community 7`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AuthService` (e.g. with `ChangePasswordRequest` and `RoleChecker`) actually correct?**
  _`AuthService` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagCreate` (e.g. with `Path` and `Session`) actually correct?**
  _`TagCreate` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@opencode-ai/plugin`, `Jirani Offline Library Backend  A FastAPI-based backend for managing an offlin`, `Dynamic search endpoint for books with multiple optional filters.     All param` to the rest of the system?**
  _164 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.10695187165775401 - nodes in this community are weakly interconnected._