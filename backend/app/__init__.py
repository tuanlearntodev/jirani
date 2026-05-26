"""
Jirani Offline Library Backend

A FastAPI-based backend for managing an offline library system.
Designed for deployment on Rock 5B with ARM64 architecture.
"""

__version__ = "1.0.0"
__author__ = "tuanlearntodev"
__description__ = "FastAPI backend for offline library management"

# Import core components for easy access
from .config import settings
from .database import get_db, SessionLocal, Base

# Import all packages for easy access
from . import models
from . import schemas
from . import repositories
from . import api
from . import services

# Package metadata and core exports
__all__ = [
    # Core components
    "app",
    "settings",
    "get_db", 
    "SessionLocal",
    "Base",
    
    # Packages
    "models",
    "schemas", 
    "repositories",
    "api",
    "services",
    
    # Metadata
    "__version__",
    "__author__",
    "__description__"
]