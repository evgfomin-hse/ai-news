from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_single_book():
    response = client.get("/books?id=1")
    assert response.status_code == 200
    json = response.json()
    assert json == {"id": 1, "title": "To be", "author": "Shakespeare", "category": "Drama"}

def test_get_single_book_not_found():
    response = client.get("/books?id=12")
    assert response.status_code == 404

def test_get_list_of_users_books():
    response = client.get("/books")
    assert response.status_code == 200
    json = response.json()
    assert json == [{"id": 1, "title": "To be", "author": "Shakespeare", "category": "Drama"}, {"id": 2, "title": "To be", "author": "Shakespeare", "category": "Drama"}, {"id": 3, "title": "To be", "author": "Shakespeare", "category": "Drama"}, {"id": 4, "title": "To be", "author": "Shakespeare", "category": "Drama"}]

def test_favorite_book():
    response = client.post("/books/favorite", json={"id": 1})
    assert response.status_code == 200
    json = response.json()
    assert json == {"id": 1, "title": "To be", "author": "Shakespeare", "category": "Drama", "favorite": True}

def test_unfavorite_book():
    response = client.post("/books/unfavorite", json={"id": 1})
    assert response.status_code == 200
    json = response.json()
    assert json == {"id": 1, "title": "To be", "author": "Shakespeare", "category": "Drama", "favorite": False}

def test_score_book():
    response = client.post("/books/score", json={"id": 1, "score": 1})
    assert response.status_code == 200
    json = response.json()
    assert json == {"id": 1, "title": "To be", "author": "Shakespeare", "category": "Drama", "favorite": False, "score":1}