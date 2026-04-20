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
from app.schemas.user import UserProfileOut, UserProfilePatch
from app.services.summary_service import SummaryMaintenanceService, SummaryService
from app.services.user_service import UserService

router = APIRouter(prefix="/user", tags=["user"])


def _user_profile_out(user: User) -> UserProfileOut:
    return UserProfileOut(
        id=str(user.id),
        username=user.name or "",
        email=user.email,
        avatarUrl=user.picture,
    )


@router.get("", response_model=UserProfileOut)
def get_profile(user: Annotated[User, Depends(get_current_user)]) -> UserProfileOut:
    return _user_profile_out(user)


@router.get("/summary", response_model=UserSummaryResponse)
def get_summary(
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


@router.post("/summary/generate")
def generate_summary(
    user: Annotated[User, Depends(get_current_user)],
    maintenance: Annotated[SummaryMaintenanceService, Depends(get_summary_maintenance_service)],
) -> dict[str, bool | int]:
    """Insert one `summaries` row for the current user (same template as the nightly job)."""
    n = maintenance.append_placeholder_for_user(user.id)
    return {"ok": True, "rows_inserted": n}


@router.patch("", response_model=UserProfileOut)
def patch_profile(
    body: UserProfilePatch,
    user: Annotated[User, Depends(get_current_user)],
    users: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileOut:
    users.patch_profile(user, name=body.name, picture=body.picture)
    return _user_profile_out(user)
