# Graph Report - jirani_offline_library_backend  (2026-05-26)

## Corpus Check
- 48 files · ~7,445 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 286 nodes · 747 edges · 23 communities (20 shown, 3 thin omitted)
- Extraction: 70% EXTRACTED · 30% INFERRED · 0% AMBIGUOUS · INFERRED: 222 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

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
- [[_COMMUNITY_Community 20|Community 20]]

## God Nodes (most connected - your core abstractions)
1. `Account` - 26 edges
2. `TagCreate` - 24 edges
3. `BookRepo` - 22 edges
4. `BookService` - 22 edges
5. `TagRead` - 20 edges
6. `Tag` - 19 edges
7. `SignUpRequest` - 18 edges
8. `Session` - 17 edges
9. `Audio` - 17 edges
10. `Audio_Repo` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Session` --uses--> `BookCreate`  [INFERRED]
  app/repositories/book_repo.py → app/schemas/book_schema.py
- `str` --uses--> `Tag`  [INFERRED]
  app/api/audio_router.py → app/models/tag.py
- `Audio` --uses--> `Tag`  [INFERRED]
  app/api/audio_router.py → app/models/tag.py
- `Audio_View` --uses--> `Tag`  [INFERRED]
  app/api/audio_router.py → app/models/tag.py
- `Session` --uses--> `Tag`  [INFERRED]
  app/api/audio_router.py → app/models/tag.py

## Communities (23 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (32): delete_book(), get_book_details(), _get_book_file_path(), get_book_service(), _iter_file_chunks(), Get book details by UID., Teacher endpoint to update book metadata and optional cover., Teacher endpoint to delete a book by UID. (+24 more)

### Community 1 - "Community 1"
Cohesion: 0.17
Nodes (35): admin_exists(), change_own_password(), login(), make_admin(), reset_password(), seed_roles(), signup(), verify_recovery_code() (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.21
Nodes (23): _build_audio_view(), delete_audio(), get_audio(), stream_audio(), update_audio(), upload_audio(), upload_multiple(), validate_audio() (+15 more)

### Community 3 - "Community 3"
Cohesion: 0.25
Nodes (22): _build_video_view(), delete_video(), get_videos(), stream_video(), update_video(), upload_file(), upload_multiple(), int (+14 more)

### Community 4 - "Community 4"
Cohesion: 0.15
Nodes (13): bool, bytes, Path, str, UploadFile, BookBase, BookDetail, BookUpload (+5 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (11): get_all_tags(), Session, lifespan(), int, Session, TagCreate, TagCreate, FastAPI (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.32
Nodes (14): str, str, BookBase, BookCreate, BookDetail, BookRead, BookUpload, cover_url() (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (6): Base, AccountRole, AudioTag, Book, BookTag, VideoTag

### Community 8 - "Community 8"
Cohesion: 0.42
Nodes (11): Account, Session, str, authenticate_user(), create_access_token(), create_token_for_user(), create_user(), get_password_hash() (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.29
Nodes (7): ALLOWED_EXTENSIONS(), ALLOWED_IMAGE_EXTENSIONS(), str, Settings, get_db(), Jirani Offline Library Backend  A FastAPI-based backend for managing an offlin, BaseSettings

### Community 10 - "Community 10"
Cohesion: 0.20
Nodes (9): 1. Build and start containers, 2. Stop containers, 3. Stop containers and remove database volume, code:bash (docker compose up --build), code:bash (docker compose down), code:bash (docker compose down -v), Jirani Offline Library Backend, Notes (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (8): ## Active Tasks, API Endpoints & Routers, Container startup behavior, ## Current State, Database Models & Schemas, Docker publish workflow, ## Project Overview, ## Tech Stack & Architecture

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (8): Approach (Recommended), Components, Data Flow, Docker entrypoint upload dirs, Error Handling, Goal, Scope, Testing

## Knowledge Gaps
- **26 isolated node(s):** `$schema`, `plugin`, `Config`, `str`, `BookRepo` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BookService` connect `Community 0` to `Community 4`, `Community 6`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `get_db()` connect `Community 9` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `FastAPI` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 6`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `Account` (e.g. with `Session` and `str`) actually correct?**
  _`Account` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `TagCreate` (e.g. with `Session` and `BookService`) actually correct?**
  _`TagCreate` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `BookRepo` (e.g. with `Session` and `BookService`) actually correct?**
  _`BookRepo` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `BookService` (e.g. with `Session` and `BookService`) actually correct?**
  _`BookService` has 7 INFERRED edges - model-reasoned connections that need verification._