from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_user_service, get_score_service
from app.models import User
from app.schemas.score import ScoreCreateRequest
from app.schemas.user import UserProfileOut, UserProfilePatch
from app.services.score_service import ScoreService
from app.services.user_service import UserService

router = APIRouter(prefix="/score", tags=["score"])


@router.patch("", response_model=UserProfileOut)
def patch_score(
    body: ScoreCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    scores: Annotated[ScoreService, Depends(get_score_service)],
) -> UserProfileOut:
    res = scores.upsert_score(body)
    return res
