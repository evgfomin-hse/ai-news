from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User

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
