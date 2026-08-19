# Jirani Offline Library Backend

## Run With Docker

### 1. Build and start containers

```bash
docker compose up --build
```

This starts:
- API at http://localhost:8000
- PostgreSQL at localhost:5432

### 2. Stop containers

```bash
docker compose down
```

### 3. Stop containers and remove database volume

```bash
docker compose down -v
```

## Notes

- The API container uses `DATABASE_URL=postgresql://postgres:postgres@db:5432/jirani_library`.
- Uploaded books and covers are persisted through the `./uploads:/app/uploads` bind mount.
- Tables are created automatically on startup through SQLAlchemy `Base.metadata.create_all`.
