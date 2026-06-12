"""CSV import of a user's summaries (with their score row, if any).

The inverse of `summary_export.py`: parses the exact CSV the export produces back
into structured rows. Pure functions — no DB or HTTP dependency — so the route can
unit-test parsing directly and own the transaction.

Validation is all-or-nothing: `parse_summaries_csv` collects every problem and
raises `CsvImportError` if any row is invalid, so a partially-bad file imports
nothing.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from app.services.summary_export import CSV_HEADER


@dataclass(frozen=True)
class ParsedRow:
    """One import row. `summary_id` from the file is intentionally not carried —
    every row becomes a brand-new summary owned by the importing user."""

    body: str
    created_at: datetime | None
    score: bool | None
    score_description: str | None

    @property
    def has_score(self) -> bool:
        """A score row is created only when the line carries a rating or a note."""
        return self.score is not None or self.score_description is not None


class CsvImportError(Exception):
    """Raised when the CSV header or any row is invalid. Carries human-readable
    problems for the API to surface; no rows are imported when this is raised."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def _parse_score(raw: str) -> bool | None:
    value = raw.strip().upper()
    if value == "":
        return None
    if value == "TRUE":
        return True
    if value == "FALSE":
        return False
    raise ValueError(f"score must be TRUE, FALSE or blank (got {raw!r})")


def _parse_created_at(raw: str) -> datetime | None:
    value = raw.strip()
    if value == "":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"created_at_utc must be ISO-8601 or blank (got {raw!r})") from exc


def parse_summaries_csv(text: str) -> list[ParsedRow]:
    """Parse the export-format CSV into rows, or raise `CsvImportError`.

    The header must match the export header exactly. Every data row is validated;
    all problems are reported together so the caller can fix the file in one pass.
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise CsvImportError(["File is empty; expected a header row."]) from None

    if tuple(h.strip() for h in header) != CSV_HEADER:
        raise CsvImportError(
            [
                "Unexpected header. Expected the export columns: "
                + ", ".join(CSV_HEADER)
                + "."
            ]
        )

    problems: list[str] = []
    rows: list[ParsedRow] = []
    expected_cols = len(CSV_HEADER)

    # `enumerate(start=2)` so the reported line number matches the file (header is line 1).
    for line_no, raw_row in enumerate(reader, start=2):
        if not raw_row or all(cell.strip() == "" for cell in raw_row):
            continue  # tolerate trailing blank lines
        if len(raw_row) != expected_cols:
            problems.append(
                f"Row {line_no}: expected {expected_cols} columns, got {len(raw_row)}."
            )
            continue

        _summary_id, created_at_raw, body_raw, score_raw, description_raw = raw_row

        body = body_raw.strip()
        if not body:
            problems.append(f"Row {line_no}: body is required and cannot be blank.")
            continue

        try:
            created_at = _parse_created_at(created_at_raw)
        except ValueError as exc:
            problems.append(f"Row {line_no}: {exc}")
            continue

        try:
            score = _parse_score(score_raw)
        except ValueError as exc:
            problems.append(f"Row {line_no}: {exc}")
            continue

        description = description_raw.strip() or None
        rows.append(
            ParsedRow(
                body=body,
                created_at=created_at,
                score=score,
                score_description=description,
            )
        )

    if problems:
        raise CsvImportError(problems)
    return rows
