from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import engine
from app.models import Base
from app.scheduler import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    setup_scheduler()
    yield
    shutdown_scheduler()
    engine.dispose()
