from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_db,
    get_summary_maintenance_service,
    get_summary_service,
)
from app.models import User
from app.repositories.summary_repository import SummaryRepository
from app.schemas.summary import GenerateSummaryRequest, UserSummaryResponse
from app.services.summary_export import build_summaries_csv
from app.services.summary_service import SummaryMaintenanceService, SummaryService

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=UserSummaryResponse)
def get_summary(
    user: Annotated[User, Depends(get_current_user)],
    summary: Annotated[SummaryService, Depends(get_summary_service)],
    page: Annotated[int, Query(ge=1, description="1-based page")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100, description="Rows per page (max 100)"),
    ] = 20,
) -> UserSummaryResponse:
    """Paginated rows from `public.summaries` for the signed-in user."""
    return summary.get_summary_for_user(user.id, page=page, page_size=page_size)


@router.post("/generate")
def generate_summary(
    user: Annotated[User, Depends(get_current_user)],
    maintenance: Annotated[SummaryMaintenanceService, Depends(get_summary_maintenance_service)],
    body: GenerateSummaryRequest | None = None,
) -> dict[str, bool | int]:
    """Insert one `summaries` row for the current user.

    Runs the real LLM pipeline when configured. Pass `{"placeholder": true}` to skip the
    LLM and insert a deterministic placeholder instead (used by e2e/CI).
    """
    force_placeholder = body.placeholder if body is not None else False
    n = maintenance.append_placeholder_for_user(user.id, force_placeholder=force_placeholder)
    return {"ok": True, "rows_inserted": n}


@router.delete("/{summary_id}", status_code=204)
def delete_summary(
    summary_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a single summary row owned by the current user."""
    from fastapi import HTTPException

    repo = SummaryRepository(db)
    deleted = repo.delete_for_user(summary_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    db.commit()


@router.get("/export.csv")
def export_summaries_csv(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Return every summary for the current user as a CSV download.

    Columns: `summary_id`, `created_at_utc`, `body`, `score`, `score_description`.
    Score columns are blank for summaries the user hasn't rated.
    """
    rows = SummaryRepository(db).list_all_with_scores_for_user(user.id)
    csv_text = build_summaries_csv(rows)
    filename = f"summaries-{datetime.now(UTC).strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
