"""Pure prompt construction for the per-user daily summary.

Kept separate from `summary_service.py` so it can be unit-tested without DB or HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import NewsArticle, Score


@dataclass(frozen=True)
class ScoreSignal:
    """The minimal score data the LLM needs: the rating and the user's reason for it."""

    value: bool
    description: str | None


_CONTENT_TRUNCATE = 1000


@dataclass(frozen=True)
class NewsItem:
    """The minimal article data the LLM needs."""

    title: str
    description: str | None
    url: str | None
    content: str | None = None


def score_signals_from_rows(rows: list[Score]) -> list[ScoreSignal]:
    return [
        ScoreSignal(value=bool(r.score), description=(r.description or None))
        for r in rows
        if r.score is not None
    ]


def news_items_from_rows(rows: list[NewsArticle]) -> list[NewsItem]:
    return [
        NewsItem(title=r.title, description=r.description, url=r.url, content=getattr(r, "content", None))
        for r in rows
        if getattr(r, "content", None)
    ]


_SYSTEM_RULES = """\
You are an editorial assistant generating one personalized daily news digest in Markdown.

Rules:
- Output Markdown only, no preamble, no closing remarks.
- Open with a single H2 heading: `## Daily summary — <today>` (use the date
  placeholder you receive).
- Then 4-8 bullets. Each bullet must be 1-2 sentences that summarize WHAT THE
  ARTICLE ACTUALLY SAYS — drawn from its content, not its title. Do not simply
  restate the headline; explain the key finding, decision, or development.
- EVERY bullet MUST end with a parenthesized markdown link to its source article's
  URL, e.g. `([source](https://example.com/article))`. This is mandatory — never
  emit a bullet without a source link.
- Only write bullets for items that have a URL in "Today's news". Skip any item
  that has no URL rather than inventing or omitting a source.
- Bias toward the user's interests; deprioritize topics the user has previously
  disliked.
- If "Recent feedback" tells you the user liked or disliked similar items, mention
  nothing about that fact — just adjust selection.
- If interests are empty, pick a balanced cross-section of the day's news.
- If there is no news, output exactly:
  `## Daily summary — <today>\\n\\n_No fresh news today._`
"""


def build_summary_prompt(
    *,
    date_label: str,
    interests_text: str | None,
    recent_scores: list[ScoreSignal],
    news: list[NewsItem],
) -> str:
    """Build the full user-message prompt for a single user's daily summary.

    `date_label` is the date string to embed in the H2 header (e.g. "2026-05-23").
    """
    sections: list[str] = [_SYSTEM_RULES, f"Today's date: {date_label}"]

    interests = (interests_text or "").strip()
    if interests:
        sections.append("User interests (free-text, single source of truth):\n" + interests)
    else:
        sections.append("User interests: (not set; pick a balanced cross-section)")

    if recent_scores:
        lines = []
        for s in recent_scores:
            tag = "LIKED" if s.value else "DISLIKED"
            desc = (s.description or "").strip()
            lines.append(f"- {tag}: {desc}" if desc else f"- {tag}")
        sections.append("Recent feedback (most recent first):\n" + "\n".join(lines))
    else:
        sections.append("Recent feedback: (none yet)")

    if news:
        lines = []
        for n in news:
            head = f"- {n.title}"
            if n.url:
                head += f" [{n.url}]"
            if n.content:
                head += f"\n  {n.content[:_CONTENT_TRUNCATE]}"
            lines.append(head)
        sections.append("Today's news (raw):\n" + "\n".join(lines))
    else:
        sections.append("Today's news: (none)")

    sections.append("Now write the Markdown digest.")
    return "\n\n".join(sections)
