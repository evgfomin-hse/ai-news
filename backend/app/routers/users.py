from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_summary_service
from app.models import User
from app.services.summary import SummaryService, UserSummaryResponse
from app.services.summary.generation import insert_generated_summary_for_user

router = APIRouter(prefix="/users", tags=["users"])


class UserMeOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class UserMePatch(BaseModel):
    name: str | None = None
    picture: str | None = None


def _user_me_out(user: User) -> UserMeOut:
    return UserMeOut(
        id=str(user.id),
        username=user.name or "",
        email=user.email,
        avatarUrl=user.picture,
    )


@router.get("/me", response_model=UserMeOut)
def get_me(user: Annotated[User, Depends(get_current_user)]) -> UserMeOut:
    return _user_me_out(user)


@router.get("/me/summary", response_model=UserSummaryResponse)
def get_my_summary(
    user: Annotated[User, Depends(get_current_user)],
    summary: Annotated[SummaryService, Depends(get_summary_service)],
    page: Annotated[int, Query(ge=1, description="1-based page")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100, description="Rows per page (max 100)"),
    ] = 20,
) -> UserSummaryResponse:
    """Paginated rows from `public.summaries` for the signed-in user."""
    return summary.get_summary_for_user(user.id, page=page, page_size=page_size)


@router.post("/me/summary/generate")
def generate_my_summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, bool | int]:
    """Insert one `summaries` row for the current user (same template as the nightly job)."""
    n = insert_generated_summary_for_user(db, user.id)
    db.commit()
    return {"ok": True, "rows_inserted": n}


@router.patch("/me", response_model=UserMeOut)
def patch_me(
    body: UserMePatch,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserMeOut:
    changed = False
    if body.name is not None:
        user.name = body.name
        changed = True
    if body.picture is not None:
        user.picture = body.picture
        changed = True
    if changed:
        db.add(user)
        db.commit()
        db.refresh(user)
    return _user_me_out(user)
