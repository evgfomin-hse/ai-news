import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_health_service
from app.services.health_service import HealthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/db")
def health_db(health: Annotated[HealthService, Depends(get_health_service)]):
    try:
        health.check_database_connection()
    except SQLAlchemyError as exc:
        root = getattr(exc, "orig", None) or exc
        msg = str(root).strip().splitlines()[0]
        logger.warning("Database health check failed: %s", msg)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "database_unavailable",
                "message": msg,
                "hint": "Set DATABASE_URL in backend/.env to your real PostgreSQL user, password, host, port, and database.",
            },
        ) from exc
    return {"database": "ok"}
