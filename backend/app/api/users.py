from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_user_service
from app.models import User
from app.schemas.user import UserProfileOut, UserProfilePatch
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


@router.patch("", response_model=UserProfileOut)
def patch_profile(
    body: UserProfilePatch,
    user: Annotated[User, Depends(get_current_user)],
    users: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileOut:
    users.patch_profile(user, name=body.name, picture=body.picture)
    return _user_profile_out(user)
