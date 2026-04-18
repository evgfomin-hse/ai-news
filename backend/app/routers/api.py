import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
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
