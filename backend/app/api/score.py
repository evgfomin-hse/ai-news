from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.dependencies import get_current_user, get_score_service
from app.models import User
from app.schemas.score import ScoreOut, ScoreUpsertRequest
from app.services.score_service import ScoreService, SummaryNotFoundError

router = APIRouter(prefix="/score", tags=["score"])


@router.put("", response_model=ScoreOut)
def upsert_score(
    body: ScoreUpsertRequest,
    user: Annotated[User, Depends(get_current_user)],
    scores: Annotated[ScoreService, Depends(get_score_service)],
) -> ScoreOut:
    try:
        row = scores.upsert_for_user(user.id, body)
    except SummaryNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Summary not found for this user.",
        ) from exc
    return ScoreOut.model_validate(row)


@router.get("/{summary_id}", response_model=ScoreOut | None)
def get_score(
    user: Annotated[User, Depends(get_current_user)],
    scores: Annotated[ScoreService, Depends(get_score_service)],
    summary_id: Annotated[int, Path(ge=1)],
) -> ScoreOut | None:
    try:
        row = scores.get_for_user_summary(user.id, summary_id)
    except SummaryNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Summary not found for this user.",
        ) from exc
    if row is None:
        return None
    return ScoreOut.model_validate(row)
