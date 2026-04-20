from datetime import datetime

from pydantic import BaseModel, Field


class SummaryItem(BaseModel):
    id: str
    title: str
    body: str


class UserSummaryResponse(BaseModel):
    """Paginated `public.summaries` rows for the current user."""

    items: list[SummaryItem] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total rows for this user (all pages).")
    page: int = Field(..., ge=1, description="1-based page index.")
    page_size: int = Field(..., ge=1, description="Page size used for this response.")
    total_pages: int = Field(
        ...,
        ge=0,
        description="Number of pages (0 when total is 0).",
    )
    generated_at: datetime | None = Field(
        None,
        description="Latest `created_at` among items on this page; null if this page is empty.",
    )
    notice: str = Field(
        default="",
        description="Markdown when `total` is 0 (empty table for this user).",
    )
