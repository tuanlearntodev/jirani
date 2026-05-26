# Docker entrypoint upload dirs

## Goal
Ensure required upload directories exist at container startup so the API can write files immediately after the container begins running.

## Scope
- Create `/app/uploads/books` and `/app/uploads/covers` on container start.
- Keep the existing Uvicorn command and runtime behavior unchanged.

## Approach (Recommended)
Use an entrypoint script that runs on every container start:
- Create directories with `mkdir -p` (idempotent).
- `exec` the existing Uvicorn command so signals and exit codes behave correctly.

## Components
- `docker/entrypoint.sh`
  - Create `/app/uploads/books` and `/app/uploads/covers`.
  - `exec "$@"` to run the container command.
- `Dockerfile`
  - Copy the entrypoint script into the image.
  - Mark it executable.
  - Set `ENTRYPOINT` to the script, keep `CMD` as the Uvicorn command.

## Data Flow
Container start → entrypoint runs → directories created → Uvicorn starts → FastAPI runs normally.

## Error Handling
- `mkdir -p` is idempotent.
- If creation fails (permissions, read-only filesystem), the container exits with the error, making the issue visible early.

## Testing
- `docker compose up --build` and confirm directories exist in the running container.
- Validate API starts and can save uploads.
