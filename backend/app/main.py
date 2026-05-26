from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.api import auth_router, book_router, video_router, tag_router, audio_router
from app import settings  # Import models to register them with Base
from fastapi.middleware.cors import CORSMiddleware
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.COVER_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown (if needed)
    engine.dispose()


app = FastAPI(
    title="Jirani Offline Library Backend",
    description="A FastAPI backend for offline library management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount covers directory for public access (books require auth)

os.makedirs(settings.UPLOAD_DIR / "covers", exist_ok=True)
app.mount("/static/covers", StaticFiles(directory=str(settings.COVER_DIR)), name="covers")

app.include_router(auth_router.router)
app.include_router(book_router.router)
app.include_router(video_router.router)
app.include_router(tag_router.router)
app.include_router(audio_router.router)


@app.get("/")
async def root():
    return {"message": "Welcome to Jirani Offline Library Backend"}