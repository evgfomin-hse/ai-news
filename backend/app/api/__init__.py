"""HTTP API layer — route registration and shared dependencies."""

from fastapi import FastAPI

from . import auth, health, interests, score, summary, tasks, transports, users


def register_routes(app: FastAPI) -> None:
    """Attach all domain routers to the FastAPI application."""
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(summary.router)
    app.include_router(interests.router)
    app.include_router(score.router)
    app.include_router(transports.router)
    app.include_router(tasks.router)
    app.include_router(health.router)
