from datetime import UTC, datetime

from app.services.summary.base import SummaryService
from app.services.summary.schemas import SummaryItem, UserSummaryResponse


def _total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size


class MockSummaryService(SummaryService):
    """In-memory paginated sample (not wired in dependencies by default)."""

    EMPTY_NOTICE = """## No summary sections yet

The mock has **no items** for this request. When sections exist, they render as markdown below."""

    _SAMPLE_BODY = "\n".join(
        [
            "## Hello from the mock summary",
            "",
            "This line mixes **bold**, *italic*, and `inline code`.",
            "",
            "- First bullet",
            "- Second bullet with a [link](https://example.org)",
            "",
            "> A short blockquote for styling checks.",
            "",
            "| Feature | Status |",
            "|---------|--------|",
            "| Markdown | OK |",
        ]
    )

    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        _ = user_id
        all_items = [
            SummaryItem(
                id=f"mock-{i}",
                title=f"Sample {i}",
                body=self._SAMPLE_BODY if i == 1 else f"Body **{i}**",
            )
            for i in range(1, 48)
        ]
        total = len(all_items)
        tp = _total_pages(total, page_size)
        safe_page = min(max(page, 1), max(tp, 1))
        offset = (safe_page - 1) * page_size
        slice_items = all_items[offset : offset + page_size]
        return UserSummaryResponse(
            items=slice_items,
            total=total,
            page=safe_page,
            page_size=page_size,
            total_pages=tp,
            generated_at=datetime.now(UTC),
            notice=self.EMPTY_NOTICE if total == 0 else "",
        )
