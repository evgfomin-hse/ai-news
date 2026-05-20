from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_health_service
from app.main import app
from app.services.health_service import HealthService


def test_health_db_ok(client):
    resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json() == {"database": "ok"}


def test_health_db_returns_503_when_database_unreachable(client):
    class _Down(HealthService):
        def __init__(self):  # bypass real session
            pass

        def check_database_connection(self):
            raise OperationalError("SELECT 1", {}, Exception("could not connect"))

    app.dependency_overrides[get_health_service] = lambda: _Down()
    try:
        resp = client.get("/health/db")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["error"] == "database_unavailable"
    assert "DATABASE_URL" in detail["hint"]
