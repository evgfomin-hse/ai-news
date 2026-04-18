from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.routers.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
