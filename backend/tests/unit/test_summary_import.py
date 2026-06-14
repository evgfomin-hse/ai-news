"""Unit tests for the pure CSV parser. No DB, no HTTP."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models import Score, Summary
from app.services.summary_export import CSV_HEADER, build_summaries_csv
from app.services.summary_import import CsvImportError, parse_summaries_csv

HEADER_LINE = ",".join(CSV_HEADER)


def _csv(*data_rows: str) -> str:
    return "\n".join([HEADER_LINE, *data_rows]) + "\n"


def test_parses_a_minimal_row():
    rows = parse_summaries_csv(_csv("5,2024-01-01T00:00:00,hello,,"))
    assert len(rows) == 1
    row = rows[0]
    assert row.body == "hello"
    assert row.created_at == datetime(2024, 1, 1)
    assert row.score is None
    assert row.score_description is None
    assert row.has_score is False


def test_summary_id_column_is_ignored():
    # A wild id must not leak into the parsed row (rows always become new summaries).
    rows = parse_summaries_csv(_csv("999999,,body,,"))
    assert not hasattr(rows[0], "id")
    assert rows[0].body == "body"


def test_parses_score_true_false_and_blank():
    rows = parse_summaries_csv(
        _csv(
            "1,,a,TRUE,liked",
            "2,,b,FALSE,",
            "3,,c,,",
        )
    )
    assert [r.score for r in rows] == [True, False, None]
    assert rows[0].score_description == "liked"
    assert rows[0].has_score is True
    assert rows[1].has_score is True  # FALSE still counts as a rating
    assert rows[2].has_score is False


def test_blank_created_at_is_none():
    rows = parse_summaries_csv(_csv("1,,body,,"))
    assert rows[0].created_at is None


def test_trailing_blank_lines_are_tolerated():
    rows = parse_summaries_csv(_csv("1,,body,,", "", "   "))
    assert len(rows) == 1


def test_rejects_unexpected_header():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv("a,b,c\n1,2,3\n")
    assert "Unexpected header" in exc.value.problems[0]


def test_rejects_empty_file():
    with pytest.raises(CsvImportError):
        parse_summaries_csv("")


def test_rejects_blank_body():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv(_csv("1,2024-01-01T00:00:00,   ,,"))
    assert "body is required" in exc.value.problems[0]
    assert "Row 2" in exc.value.problems[0]


def test_rejects_bad_score_value():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv(_csv("1,,body,MAYBE,"))
    assert "score must be TRUE, FALSE or blank" in exc.value.problems[0]


def test_rejects_bad_created_at():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv(_csv("1,not-a-date,body,,"))
    assert "ISO-8601" in exc.value.problems[0]


def test_rejects_wrong_column_count():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv(_csv("1,,body"))
    assert "expected 5 columns, got 3" in exc.value.problems[0]


def test_reports_every_problem_at_once():
    with pytest.raises(CsvImportError) as exc:
        parse_summaries_csv(
            _csv(
                "1,,,,",  # blank body
                "2,,ok,MAYBE,",  # bad score
            )
        )
    assert len(exc.value.problems) == 2


def test_round_trips_export_output():
    s1 = Summary(user_id=1, summary="hello\nworld", created_at=datetime(2024, 1, 1))
    s1.id = 5
    s2 = Summary(user_id=1, summary='rated, with "comma"', created_at=datetime(2024, 6, 2))
    s2.id = 6
    csv_text = build_summaries_csv(
        [(s1, None), (s2, Score(summary_id=6, score=True, description="great"))]
    )

    rows = parse_summaries_csv(csv_text)

    assert len(rows) == 2
    assert rows[0].body == "hello\nworld"
    assert rows[0].created_at == datetime(2024, 1, 1)
    assert rows[0].has_score is False
    assert rows[1].body == 'rated, with "comma"'
    assert rows[1].score is True
    assert rows[1].score_description == "great"
