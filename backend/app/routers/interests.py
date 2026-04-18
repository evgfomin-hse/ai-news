from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import Interest, User
from app.services.interests import get_interest_row, naive_utc_now

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
    db: Annotated[Session, Depends(get_db)],
) -> InterestMeOut:
    row = get_interest_row(db, user.id)
    if row is None:
        return InterestMeOut()
    text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestMeOut(interestId=row.id, interests=text)


@router.patch("/me", response_model=InterestMeOut)
def patch_interests_me(
    body: InterestMePatch,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InterestMeOut:
    now = naive_utc_now()
    row = get_interest_row(db, user.id)
    text = body.interests.strip()

    if row is None:
        row = Interest(
            user_id=user.id,
            interests=text or None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.interests = text or None
        row.updated_at = now
        db.add(row)

    db.commit()
    db.refresh(row)
    out_text = (row.interests or "").strip() if row.interests is not None else ""
    return InterestMeOut(interestId=row.id, interests=out_text)
