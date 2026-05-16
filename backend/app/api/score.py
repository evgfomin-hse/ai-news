from fastapi import APIRouter

from app.schemas.score import ScoreCreateRequest

router = APIRouter(tags=["score"])


@router.post("/score")
def create_score(payload: ScoreCreateRequest) -> dict[str, bool]:
    _ = payload
    return {"ok": True}
