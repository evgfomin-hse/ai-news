from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.repositories.summary_repository import SummaryRepository
from app.services.health_service import HealthService
from app.services.interest_service import InterestService
from app.services.score_service import ScoreService
from app.services.summary_service import (
    PostgresSummaryService,
    SummaryMaintenanceService,
    SummaryService,
)
from app.services.transport_service import TransportService
from app.services.user_service import UserService

bearer_optional = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_service(db: Annotated[Session, Depends(get_db)]) -> UserService:
    return UserService(db)


def get_interest_service(db: Annotated[Session, Depends(get_db)]) -> InterestService:
    return InterestService(db)


def get_transport_service(db: Annotated[Session, Depends(get_db)]) -> TransportService:
    return TransportService(db)


def get_health_service(db: Annotated[Session, Depends(get_db)]) -> HealthService:
    return HealthService(db)


def get_summary_maintenance_service(
        db: Annotated[Session, Depends(get_db)],
) -> SummaryMaintenanceService:
    return SummaryMaintenanceService(db)


def get_summary_service(db: Annotated[Session, Depends(get_db)]) -> SummaryService:
    return PostgresSummaryService(SummaryRepository(db))


def get_score_service(db: Annotated[Session, Depends(get_db)]) -> ScoreService:
    return ScoreService(db)


def get_session_jwt(
        request: Request,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(bearer_optional)
        ],
) -> str:
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        return raw
    if credentials is not None:
        return credentials.credentials
    raise HTTPException(status_code=401, detail="Not authenticated")


def get_current_user(
        token: Annotated[str, Depends(get_session_jwt)],
        users: Annotated[UserService, Depends(get_user_service)],
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(sub)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = users.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
