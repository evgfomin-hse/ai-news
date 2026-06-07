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
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.gdelt_service import GdeltFetcherService
from app.services.health_service import HealthService
from app.services.interest_service import InterestService
from app.services.keyword_extractor import KeywordExtractor
from app.services.llm_service import LLMSummarizer, OpenRouterSummarizer
from app.services.score_service import ScoreService
from app.services.summary_service import (
    PostgresSummaryService,
    SummaryMaintenanceService,
    SummaryService,
)
from app.services.telegram_service import RequestsTelegramSender, TelegramSender
from app.services.transport_service import TransportService
from app.services.user_service import UserService


def _build_summarizer() -> LLMSummarizer | None:
    """Returns a configured OpenRouter summarizer, or None when the API key is unset."""
    if not settings.openrouter_api_key.strip():
        return None
    return OpenRouterSummarizer(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
    )


def _build_gdelt_fetcher(db: Session) -> GdeltFetcherService:
    """Returns a GDELT fetcher. No API key needed; GDELT is always enabled."""
    return GdeltFetcherService(
        db,
        max_articles=settings.gdelt_max_articles,
        max_records_per_request=settings.gdelt_request_max_records,
    )


def _build_keyword_extractor() -> KeywordExtractor | None:
    """Returns a keyword extractor wrapping the configured summarizer, or None when unconfigured."""
    summarizer = _build_summarizer()
    if summarizer is None:
        return None
    return KeywordExtractor(
        summarizer,
        max_query_chars=settings.keyword_extractor_max_query_chars,
    )


def _build_candidate_filter() -> PerUserCandidateFilter | None:
    """Returns a per-user filter wrapping the configured summarizer, or None when unconfigured."""
    summarizer = _build_summarizer()
    if summarizer is None:
        return None
    return PerUserCandidateFilter(
        summarizer,
        batch_size=settings.per_user_filter_batch,
        top_per_batch=settings.per_user_filter_top_per_batch,
    )


def _build_telegram_sender() -> TelegramSender:
    """The sender takes a per-user bot token at call time, so no global key check here."""
    return RequestsTelegramSender()


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
    return SummaryMaintenanceService(
        db,
        summarizer=_build_summarizer(),
        gdelt_fetcher=_build_gdelt_fetcher(db),
        keyword_extractor=_build_keyword_extractor(),
        candidate_filter=_build_candidate_filter(),
        telegram_sender=_build_telegram_sender(),
    )


def get_telegram_sender() -> TelegramSender:
    return _build_telegram_sender()


def get_summary_service(db: Annotated[Session, Depends(get_db)]) -> SummaryService:
    return PostgresSummaryService(SummaryRepository(db))


def get_score_service(db: Annotated[Session, Depends(get_db)]) -> ScoreService:
    return ScoreService(db)


def get_session_jwt(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_optional)],
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
