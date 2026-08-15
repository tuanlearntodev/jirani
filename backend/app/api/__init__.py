# app/routes/__init__.py
from . import (
    audio_router,
    auth_router,
    book_router,
    setup_router,
    tag_router,
    video_router,
)

__all__ = [
    "audio_router",
    "auth_router",
    "book_router",
    "setup_router",
    "tag_router",
    "video_router",
]
