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

@router.get("/search")
def search_book(query: str = None):
    return query

@router.get("/books")
def book(id: int):
    if id == 12:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": id, "author": "Shakespeare", "title": "To be", "category": "Drama"}

@router.get("/books/favorite")
def get_favorite_books():
    return "favorite list"

@router.post("/books/favorite")
def make_favorite_book(id: int = Body(...)):
    return id

# Курсорная пагинация
@router.get("/books/read")
def read_books():
    return None

@router.post("/books/read")
def read_book():
    return None