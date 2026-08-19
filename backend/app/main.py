from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models
from app.api import (
    audio_router,
    auth_router,
    book_router,
    setup_router,
    tag_router,
    video_router,
)
from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.COVER_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    settings.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown (if needed)
    engine.dispose()


app = FastAPI(
    title="Jirani Offline Library Backend",
    description="A FastAPI backend for offline library management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount covers directory for public access (books require auth)

app.mount(
    "/static/covers", StaticFiles(directory=str(settings.COVER_DIR)), name="covers"
)

app.include_router(auth_router.router)
app.include_router(book_router.router)
app.include_router(video_router.router)
app.include_router(tag_router.router)
app.include_router(audio_router.router)
app.include_router(setup_router.router)


@app.get("/")
async def root():
    return {"message": "Welcome to Jirani Offline Library Backend"}
