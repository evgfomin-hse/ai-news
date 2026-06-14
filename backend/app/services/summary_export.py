"""CSV export of a user's summaries (with their score row, if any).

Pure functions; the route hands in already-joined rows so this module has no DB
or HTTP dependency and can be unit-tested directly.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from app.models import Score, Summary

CSV_HEADER: tuple[str, ...] = (
    "summary_id",
    "created_at_utc",
    "body",
    "score",
    "score_description",
)


def _score_value(score: Score | None) -> str:
    if score is None or score.score is None:
        return ""
    return "TRUE" if score.score else "FALSE"


def _score_description(score: Score | None) -> str:
    if score is None or score.description is None:
        return ""
    return score.description


def build_summaries_csv(rows: Iterable[tuple[Summary, Score | None]]) -> str:
    """Render the CSV body for the given joined rows.

    Output is UTF-8 text. Newlines and quotes inside the markdown body are
    escaped per RFC 4180 by the stdlib `csv` module.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for summary, score in rows:
        writer.writerow(
            [
                summary.id,
                summary.created_at.isoformat() if summary.created_at is not None else "",
                (summary.summary or "").strip(),
                _score_value(score),
                _score_description(score),
            ]
        )
    return buf.getvalue()
