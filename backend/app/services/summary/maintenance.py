from sqlalchemy.orm import Session

from app.services.summary.generation import (
    insert_generated_summary_for_user,
    run_summary_generation_for_all_users,
)


class SummaryMaintenanceService:
    """Write-side summary operations (job + manual append), owns transaction commit."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append_placeholder_for_user(self, user_id: int) -> int:
        n = insert_generated_summary_for_user(self._session, user_id)
        self._session.commit()
        return n

    def run_bulk_for_all_users(self) -> dict[str, int]:
        stats = run_summary_generation_for_all_users(self._session)
        self._session.commit()
        return stats
