from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_interest_service
from app.models import User
from app.services.interest_service import InterestService

router = APIRouter(prefix="/interests", tags=["interests"])


class InterestMeOut(BaseModel):
    interestId: int | None = None
    interests: str = ""


class InterestMePatch(BaseModel):
    interests: str = Field(
        default="",
        max_length=50_000,
        description="Free-text interests for this user.",
    )


@router.get("/me", response_model=InterestMeOut)
def get_interests_me(
    user: Annotated[User, Depends(get_current_user)],
    interests: Annotated[InterestService, Depends(get_interest_service)],
) -> InterestMeOut:
    row = interests.get_latest_for_user(user.id)
    if row is None:
        return InterestMeOut()
    text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestMeOut(interestId=row.id, interests=text)


@router.patch("/me", response_model=InterestMeOut)
def patch_interests_me(
    body: InterestMePatch,
    user: Annotated[User, Depends(get_current_user)],
    interests: Annotated[InterestService, Depends(get_interest_service)],
) -> InterestMeOut:
    row = interests.upsert_for_user(user.id, interests_text=body.interests)
    out_text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestMeOut(interestId=row.id, interests=out_text)
