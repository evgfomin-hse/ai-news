import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.services.users import get_or_create_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600


class GoogleLoginBody(BaseModel):
    token: str = Field(..., min_length=1, description="Google ID token (JWT) from credential")


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class GoogleLoginJson(BaseModel):
    """Returned in the response body; session JWT is only in an HttpOnly cookie."""

    user: UserOut


def _issue_app_token(user_id: str, name: str, picture: str | None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "name": name,
        "picture": picture,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        path=settings.cookie_path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.cookie_path,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post("/google-login", response_model=GoogleLoginJson)
def google_login(
    body: GoogleLoginBody,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> GoogleLoginJson:
    if not settings.google_client_id.strip():
        raise HTTPException(
            status_code=503,
            detail="Server is missing GOOGLE_CLIENT_ID; set it to the same OAuth client ID as the frontend.",
        )
    try:
        idinfo = id_token.verify_oauth2_token(
            body.token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        logger.info("Google token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Google credential") from exc

    google_sub = idinfo.get("sub")
    if not google_sub:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    email = idinfo.get("email")
    if not isinstance(email, str):
        email = None
    name = (idinfo.get("name") or (email.split("@", 1)[0] if email else None) or "user")
    picture = idinfo.get("picture")
    if isinstance(picture, str) and not picture.strip():
        picture = None

    user = get_or_create_user(
        db,
        google_id=str(google_sub),
        name=str(name),
        picture=picture,
        email=email,
    )

    app_token = _issue_app_token(str(user.id), user.name or "", user.picture)
    _set_session_cookie(response, app_token)

    return GoogleLoginJson(
        user=UserOut(
            id=str(user.id),
            username=user.name or "",
            email=user.email,
            avatarUrl=user.picture,
        ),
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    _clear_session_cookie(response)
    return {"ok": True}


E2E_GOOGLE_SUBJECT = "e2e-playwright-google-subject"
E2E_USER_EMAIL = "e2e-playwright@example.invalid"


@router.post("/e2e/bootstrap-session", response_model=GoogleLoginJson)
def e2e_bootstrap_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> GoogleLoginJson:
    """Real session + DB user for browser e2e. Disabled unless E2E_BOOTSTRAP_SECRET is set."""
    configured = settings.e2e_bootstrap_secret.strip()
    if not configured:
        raise HTTPException(status_code=404, detail="Not found")
    if request.headers.get("x-e2e-bootstrap-secret") != configured:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = get_or_create_user(
        db,
        google_id=E2E_GOOGLE_SUBJECT,
        name="E2E User",
        picture=None,
        email=E2E_USER_EMAIL,
    )
    app_token = _issue_app_token(str(user.id), user.name or "", user.picture)
    _set_session_cookie(response, app_token)
    return GoogleLoginJson(
        user=UserOut(
            id=str(user.id),
            username=user.name or "",
            email=user.email,
            avatarUrl=user.picture,
        ),
    )
