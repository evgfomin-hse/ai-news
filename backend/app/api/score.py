from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

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
