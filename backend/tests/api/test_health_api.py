from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_health_service
from app.main import app
from app.services.health_service import HealthService


def test_liveness_always_ok(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/health+json")
    assert resp.json() == {"status": "pass"}


def test_readiness_ok_reports_database_check(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/health+json")
    body = resp.json()
    assert body["status"] == "pass"
    db = body["checks"]["database"]
    assert db["status"] == "pass"
    assert db["observedUnit"] == "ms"
    assert isinstance(db["observedValue"], (int, float))
    assert "output" not in db  # no failure detail on success


def test_readiness_returns_503_when_database_unreachable(client):
    class _DownDatabase:
        def ping(self):
            raise OperationalError("SELECT 1", {}, Exception("could not connect"))

    class _Down(HealthService):
        def __init__(self):  # bypass real session; inject a failing dependency
            self._database = _DownDatabase()

    app.dependency_overrides[get_health_service] = lambda: _Down()
    try:
        resp = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "fail"
    db = body["checks"]["database"]
    assert db["status"] == "fail"
    assert "could not connect" in db["output"]


def test_liveness_does_not_touch_the_database(client):
    class _Boom(HealthService):
        def __init__(self):
            pass

        def check_readiness(self):
            raise AssertionError("liveness must not run dependency checks")

    app.dependency_overrides[get_health_service] = lambda: _Boom()
    try:
        resp = client.get("/health/live")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert resp.status_code == 200
