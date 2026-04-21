from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import get_summary_maintenance_service
from app.core.config import settings
from app.services.summary_service import SummaryMaintenanceService

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/summary/run-bulk")
def run_bulk_summary_generation(
    request: Request,
    maintenance: Annotated[SummaryMaintenanceService, Depends(get_summary_maintenance_service)],
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

    return maintenance.run_bulk_for_all_users()
