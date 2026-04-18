from abc import ABC, abstractmethod

from app.services.summary.schemas import UserSummaryResponse


class SummaryService(ABC):
    """Application port for user-scoped summaries (swap mock / LLM / DB implementations)."""

    @abstractmethod
    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        """Return a page of summary rows plus pagination metadata."""
