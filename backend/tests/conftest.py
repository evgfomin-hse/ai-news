"""Shared pytest fixtures: in-memory SQLite, ORM session, FastAPI test client."""

from __future__ import annotations

import os
from collections.abc import Generator, Iterator

# `Settings()` validates required env at import time; satisfy it before app imports.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_SUMMARY_NIGHTLY_SCHEDULER", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, Interest, NewsArticle, Score, Summary, User

# `Transport` uses Postgres JSONB and is intentionally excluded from the SQLite schema —
# tests that need transports must mock at the service layer instead.
_SQLITE_TABLES = (
    User.__table__,
    Interest.__table__,
    Summary.__table__,
    Score.__table__,
    NewsArticle.__table__,
)


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Fresh in-memory database per test — full isolation, no cross-test bleed."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng, tables=list(_SQLITE_TABLES))
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user(db: Session) -> User:
    row = User(
        google_id="google-sub-test",
        email="test@example.com",
        name="Test User",
        picture=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # Detach so the same instance can be reattached to the route's session
    # (FastAPI's `get_db` override creates a different `Session` per request).
    db.expunge(row)
    return row


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """TestClient with DB override; routes that need auth must override `get_current_user`."""

    def _override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def authed_client(client: TestClient, user: User) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return client
