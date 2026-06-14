"""Unit tests for the pure CSV builder. No DB, no HTTP."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from app.models import Score, Summary
from app.services.summary_export import CSV_HEADER, build_summaries_csv


def _summary(rid: int, body: str | None, ts: datetime | None) -> Summary:
    s = Summary(user_id=1, summary=body, created_at=ts)
    s.id = rid
    return s


def _score(value: bool | None, description: str | None) -> Score:
    s = Score(summary_id=1, score=value, description=description)
    s.id = 1
    return s


def _parse(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def test_empty_input_returns_only_the_header_row():
    out = build_summaries_csv([])
    rows = _parse(out)
    assert rows == [list(CSV_HEADER)]


def test_renders_summary_without_score_with_blank_score_columns():
    out = build_summaries_csv(
        [(_summary(1, "hello\nworld", datetime(2026, 5, 23, 12, 0, 0)), None)]
    )
    rows = _parse(out)
    assert rows[0] == list(CSV_HEADER)
    assert rows[1] == ["1", "2026-05-23T12:00:00", "hello\nworld", "", ""]


def test_renders_summary_with_score_true_and_description():
    out = build_summaries_csv(
        [
            (
                _summary(7, "body", datetime(2026, 5, 23)),
                _score(True, "loved it"),
            )
        ]
    )
    rows = _parse(out)
    assert rows[1] == ["7", "2026-05-23T00:00:00", "body", "TRUE", "loved it"]


def test_renders_score_false():
    out = build_summaries_csv([(_summary(7, "body", datetime(2026, 5, 23)), _score(False, None))])
    rows = _parse(out)
    assert rows[1][3] == "FALSE"
    assert rows[1][4] == ""


def test_renders_score_with_null_value_as_blank():
    out = build_summaries_csv(
        [(_summary(7, "body", datetime(2026, 5, 23)), _score(None, "no rating"))]
    )
    rows = _parse(out)
    assert rows[1][3] == ""
    assert rows[1][4] == "no rating"


def test_renders_summary_with_null_created_at_as_blank():
    out = build_summaries_csv([(_summary(1, "body", None), None)])
    rows = _parse(out)
    assert rows[1][1] == ""


def test_trims_summary_body_whitespace():
    out = build_summaries_csv([(_summary(1, "  body \n\n", datetime(2026, 5, 23)), None)])
    rows = _parse(out)
    assert rows[1][2] == "body"


def test_escapes_commas_quotes_and_newlines_in_body():
    nasty = 'line1,with,commas\n"quoted" line2\nline3'
    out = build_summaries_csv([(_summary(1, nasty, datetime(2026, 5, 23)), None)])
    # Roundtrip via csv.reader: the parsed body should equal the original (trimmed).
    rows = _parse(out)
    assert rows[1][2] == nasty


def test_preserves_input_order():
    rows_in = [
        (_summary(3, "third", datetime(2026, 5, 23)), None),
        (_summary(2, "second", datetime(2026, 5, 22)), None),
        (_summary(1, "first", datetime(2026, 5, 21)), None),
    ]
    out_rows = _parse(build_summaries_csv(rows_in))
    assert [r[0] for r in out_rows[1:]] == ["3", "2", "1"]
