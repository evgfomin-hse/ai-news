from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base, Interest, Summary, Transport, User
from app.routers.api import router as api_router
from app.routers.auth import router as auth_router
from app.routers.interests import router as interests_router
from app.routers.tasks import router as tasks_router
from app.routers.transports import router as transports_router
from app.routers.users import router as users_router
from app.scheduler import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    setup_scheduler()
    yield
    shutdown_scheduler()
    engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(interests_router)
app.include_router(transports_router)
app.include_router(tasks_router)
app.include_router(api_router)
