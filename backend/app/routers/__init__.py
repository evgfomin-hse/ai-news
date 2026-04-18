from fastapi import FastAPI

from app.routers import auth, health, interests, tasks, transports, users


def register_routes(app: FastAPI) -> None:
    """Attach all versioned and domain routers to the FastAPI application."""
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(interests.router)
    app.include_router(transports.router)
    app.include_router(tasks.router)
    app.include_router(health.router)
