"""Application-wide primitives (settings, database engine)."""

from app.core.config import Settings, settings
from app.core.database import SessionLocal, engine

__all__ = ["SessionLocal", "Settings", "engine", "settings"]
