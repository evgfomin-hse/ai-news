from fastapi import APIRouter, Body, HTTPException

router = APIRouter()

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