from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_db,
    get_summary_service,
)
from app.models import User
from app.repositories.summary_repository import SummaryRepository
from app.schemas.summary import UserSummaryResponse
from app.services.summary_export import build_summaries_csv
from app.services.summary_import import CsvImportError, parse_summaries_csv
from app.services.summary_service import SummaryService

# Reject oversized uploads before reading them into memory.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

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
    return summary.get_summary_for_user(user.id, page=page, page_size=page_size)


@router.delete("/{summary_id}", status_code=204)
def delete_summary(
    summary_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
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
    """
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


@router.post("/import.csv")
async def import_summaries_csv(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(description="CSV in the export format.")],
) -> dict[str, int]:
    raw = await file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is too large.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.") from exc

    try:
        rows = parse_summaries_csv(text)
    except CsvImportError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_csv", "problems": exc.problems},
        ) from exc

    summaries, scores = SummaryRepository(db).insert_imported_for_user(user.id, rows)
    db.commit()
    return {"summaries_imported": summaries, "scores_imported": scores}
