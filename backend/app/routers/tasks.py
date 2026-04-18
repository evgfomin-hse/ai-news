from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.services.summary.generation import run_summary_generation_for_all_users

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/summary/run-bulk")
def run_bulk_summary_generation(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """
    Same work as the nightly job: one new `summaries` row per user.
    Requires `SUMMARY_JOB_SECRET` and matching header `X-Summary-Job-Secret`.
    """
    configured = settings.summary_job_secret.strip()
    if not configured:
        raise HTTPException(status_code=404, detail="Not found")
    if request.headers.get("x-summary-job-secret") != configured:
        raise HTTPException(status_code=401, detail="Unauthorized")

    stats = run_summary_generation_for_all_users(db)
    db.commit()
    return stats
