from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_interest_service
from app.models import User
from app.schemas.interest import InterestOut, InterestPatch
from app.services.interest_service import InterestService

router = APIRouter(prefix="/interests", tags=["interests"])


@router.get("", response_model=InterestOut)
def get_interests(
    user: Annotated[User, Depends(get_current_user)],
    interests: Annotated[InterestService, Depends(get_interest_service)],
) -> InterestOut:
    row = interests.get_latest_for_user(user.id)
    if row is None:
        return InterestOut()
    text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestOut(interestId=row.id, interests=text)


@router.patch("", response_model=InterestOut)
def patch_interests(
    body: InterestPatch,
    user: Annotated[User, Depends(get_current_user)],
    interests: Annotated[InterestService, Depends(get_interest_service)],
) -> InterestOut:
    row = interests.upsert_for_user(user.id, interests_text=body.interests)
    out_text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestOut(interestId=row.id, interests=out_text)
