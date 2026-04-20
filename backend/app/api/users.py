from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_current_user,
    get_summary_maintenance_service,
    get_summary_service,
    get_user_service,
)
from app.models import User
from app.schemas.summary import UserSummaryResponse
from app.schemas.user import UserMeOut, UserMePatch
from app.services.summary_service import SummaryMaintenanceService, SummaryService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


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
    maintenance: Annotated[SummaryMaintenanceService, Depends(get_summary_maintenance_service)],
) -> dict[str, bool | int]:
    """Insert one `summaries` row for the current user (same template as the nightly job)."""
    n = maintenance.append_placeholder_for_user(user.id)
    return {"ok": True, "rows_inserted": n}


@router.patch("/me", response_model=UserMeOut)
def patch_me(
    body: UserMePatch,
    user: Annotated[User, Depends(get_current_user)],
    users: Annotated[UserService, Depends(get_user_service)],
) -> UserMeOut:
    users.patch_profile(user, name=body.name, picture=body.picture)
    return _user_me_out(user)
