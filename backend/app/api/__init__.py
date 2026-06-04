# app/routes/__init__.py
from . import auth_router, book_router, tag_router, video_router, audio_router, setup_router


__all__ = ["auth_router", "book_router", "tag_router", "video_router", "audio_router", "setup_router"]