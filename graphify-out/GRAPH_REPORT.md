# Graph Report - jirani_offline_library_backend  (2026-06-19)

## Corpus Check
- 56 files · ~18,021 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 419 nodes · 768 edges · 23 communities (21 shown, 2 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 146 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ffb44e87`
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
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]

## God Nodes (most connected - your core abstractions)
1. `Auth System Redesign — Implementation Plan (Learning Edition)` - 29 edges
2. `AuthService` - 25 edges
3. `BookService` - 20 edges
4. `BookRepo` - 17 edges
5. `TagCreate` - 17 edges
6. `TagRead` - 15 edges
7. `Audio_Repo` - 14 edges
8. `RoleChecker` - 13 edges
9. `Video_Repo` - 13 edges
10. `Video_Create` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Session` --uses--> `BookCreate`  [INFERRED]
  backend/app/repositories/book_repo.py → backend/app/schemas/book_schema.py
- `login()` --calls--> `TokenResponse`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/schemas/auth_schema.py
- `LoginRequest` --uses--> `Account`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/models/account.py
- `LoginRequest` --uses--> `AuthService`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/services/auth_service.py
- `ResetPasswordRequest` --uses--> `Account`  [INFERRED]
  backend/app/api/auth_router.py → backend/app/models/account.py

## Import Cycles
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`
- 1-file cycle: `backend/app/api/__init__.py -> backend/app/api/__init__.py`
- 1-file cycle: `backend/app/__init__.py -> backend/app/__init__.py`

## Communities (23 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (25): delete_book(), get_book_details(), _get_book_file_path(), get_book_service(), _iter_file_chunks(), Get book details by UID., Teacher endpoint to update book metadata and optional cover., Teacher endpoint to delete a book by UID. (+17 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (32): AccountCreateRequest, BulkCreateRequest, BulkCreateResponse, Session, RoleEnum, BaseModel, ChangePasswordRequest, RoleChecker (+24 more)

### Community 2 - "Community 2"
Cohesion: 0.20
Nodes (19): _build_audio_view(), delete_audio(), get_audio(), stream_audio(), update_audio(), upload_audio(), upload_multiple(), validate_audio() (+11 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (19): _build_video_view(), delete_video(), get_videos(), stream_video(), update_video(), upload_file(), upload_multiple(), Session (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (36): Auth System Redesign — Implementation Plan (Learning Edition), File Map, Final verification, `GET /auth/me` (current user — new), `GET /auth/users` (list users — new), How to read this plan, Important: SQLite schema reset, `POST /auth/change-password` (fix) (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (9): Account, RoleEnum, Session, Session, TagCreate, TagCreate, AuthRepo, TagRepo (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (8): AuthRepo, Account, AccountCreateRequest, AccountRead, BulkCreateRequest, BulkCreateResponse, RoleEnum, AuthService

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (26): get_auth_service(), setup_page(), get_all_tags(), get_secret_key(), Settings, get_db(), Jirani Offline Library Backend  A FastAPI-based backend for managing an offlin, lifespan() (+18 more)

### Community 8 - "Community 8"
Cohesion: 0.18
Nodes (10): Constraints, Context, Design, Design: Mass Account Creation for Students/Teachers, Endpoint: `POST /auth/users/bulk`, Error Handling, Future: Spreadsheet Upload, Problem (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.20
Nodes (9): 1. Single Table: `accounts`, 2. Role Enum, 3. Credential Policy (matched to digital literacy level), 4. Account Creation, 5. First Admin Bootstrap, 6. Zero-Config Deployment, Auth System Redesign — Design Spec, Context (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.20
Nodes (9): code:bash (docker compose up --build), code:bash (docker compose down), code:bash (docker compose down -v), 1. Build and start containers, 2. Stop containers, 3. Stop containers and remove database volume, Jirani Offline Library Backend, Notes (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (8): Build & Test Commands (Definition of Done), Execution Boundaries, External Knowledge & Global Search (MCPs), Failure Protocol, graphify, OpenCode Agent Instructions, Operating Mode: Advisory Assistant, superpowers

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (8): Approach (Recommended), Components, Data Flow, Docker entrypoint upload dirs, Error Handling, Goal, Scope, Testing

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (30): agent, architect, coder, general, manager, tester, mode, model (+22 more)

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (8): ## Active Tasks, API Endpoints & Routers, Container startup behavior, ## Current State, Database Models & Schemas, Docker publish workflow, ## Project Overview, ## Tech Stack & Architecture

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (7): `backend/Dockerfile`, Directory Structure, Docker Build, docker-compose.yml, Migration Steps, Monorepo Restructure: Jirani Offline Library, Overview

### Community 17 - "Community 17"
Cohesion: 0.40
Nodes (4): Monorepo Restructure Implementation Plan, Task 1: Create `backend/` directory and move backend files, Task 2: Create frontend directory and clean up root, Task 3: Update docker-compose.yml to point to backend/Dockerfile

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (13): Path, UploadFile, BookBase, BookDetail, BookRead, BookRepo, BookUpload, BookService (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.31
Nodes (12): AccountCreateResponse, bulk_create_users(), change_password(), create_user(), get_all_users(), get_auth_service(), get_user_by_id(), login() (+4 more)

## Knowledge Gaps
- **113 isolated node(s):** `AccountCreateResponse`, `AccountRead`, `Session`, `RoleEnum`, `AuthRepo` (+108 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BookService` connect `Community 21` to `Community 0`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `AuthService` connect `Community 6` to `Community 1`, `Community 21`, `Community 7`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `TagCreate` connect `Community 1` to `Community 0`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AuthService` (e.g. with `ChangePasswordRequest` and `RoleChecker`) actually correct?**
  _`AuthService` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `BookService` (e.g. with `Path` and `Session`) actually correct?**
  _`BookService` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `BookRepo` (e.g. with `Path` and `Session`) actually correct?**
  _`BookRepo` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `AccountCreateResponse`, `AccountRead`, `Session` to the rest of the system?**
  _125 weakly-connected nodes found - possible documentation gaps or missing edges._