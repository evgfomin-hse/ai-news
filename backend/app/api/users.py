from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models import User
from app.schemas.user import UserProfileOut

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
