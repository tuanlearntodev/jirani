# ## Project Overview
Jirani Offline Library Backend is a FastAPI-based system designed for managing an offline library. It provides functionalities for book and video management, user authentication, and tagging systems, all optimized for offline or local network environments.

# ## Tech Stack & Architecture
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL via SQLAlchemy
- **Architecture Patterns:** 
    - **Service Layer:** Business logic encapsulated in services (e.g., `BookService`, `AuthService`).
    - **Repository Pattern:** Data access abstraction via repositories (e.g., `BookRepo`, `TagRepo`, `Video_Repo`).
    - **Schema/DTO Layer:** Pydantic models for request/response validation.
- **Storage:** Local file system for book uploads and cover images.

# ## Current State
### Database Models & Schemas
- **Account/Auth:** `Account`, `AccountRole`, `Role` (Handles user identity and permissions).
- **Books:** `Book`, `BookTag` (Core entity for library management).
- **Tags:** `Tag` (Metadata categorization).
- **Videos:** `Video` (Multimedia content support).

### API Endpoints & Routers
- **Auth Router:** Handles login, signup, and token management.
- **Book Router:** Manages book CRUD operations, searching, and streaming.
- **Tag Router:** Manages tag creation and retrieval.
- **Video Router:** Manages video content lifecycle.

### Container startup behavior
- `docker/entrypoint.sh` creates `/app/uploads/books` and `/app/uploads/covers` on container start.

### Docker publish workflow
- Use `scripts/build-and-push.ps1` to publish multi-arch images for `linux/amd64` and `linux/arm64`.
- ARM64 pushes require Docker Desktop plus buildx/QEMU binfmt support.
- For local-only checks, run the script with `-Platforms linux/amd64 -Push:$false`.

# ## Active Tasks
*No active tasks currently.*
