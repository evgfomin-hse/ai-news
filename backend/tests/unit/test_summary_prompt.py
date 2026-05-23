"""Unit tests for the pure prompt builder."""

from __future__ import annotations

from app.services.summary_prompt import (
    NewsItem,
    ScoreSignal,
    build_summary_prompt,
)


def test_prompt_includes_today_label_in_rules_and_body():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="ML, hiking",
        recent_scores=[],
        news=[NewsItem(title="A", description=None, url=None)],
    )
    assert "Today's date: 2026-05-23" in prompt


def test_prompt_renders_interests_when_present():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="  Machine learning, cinema  ",
        recent_scores=[],
        news=[],
    )
    assert "User interests (free-text" in prompt
    assert "Machine learning, cinema" in prompt


def test_prompt_marks_interests_as_not_set_when_empty():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="",
        recent_scores=[],
        news=[],
    )
    assert "(not set; pick a balanced cross-section)" in prompt


def test_prompt_lists_recent_feedback_tagged_with_liked_or_disliked():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="",
        recent_scores=[
            ScoreSignal(value=True, description="loved the LLM coverage"),
            ScoreSignal(value=False, description=None),
        ],
        news=[],
    )
    assert "LIKED: loved the LLM coverage" in prompt
    assert "- DISLIKED\n" in prompt or prompt.rstrip().endswith("DISLIKED") or "DISLIKED" in prompt


def test_prompt_marks_feedback_as_none_when_empty():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="ML",
        recent_scores=[],
        news=[],
    )
    assert "Recent feedback: (none yet)" in prompt


def test_prompt_renders_news_with_optional_description_and_url():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="",
        recent_scores=[],
        news=[
            NewsItem(title="Headline A", description="desc A", url="https://a.example"),
            NewsItem(title="Headline B", description=None, url=None),
        ],
    )
    assert "- Headline A — desc A [https://a.example]" in prompt
    assert "- Headline B" in prompt


def test_prompt_marks_news_as_none_when_empty():
    prompt = build_summary_prompt(
        today_label="2026-05-23",
        interests_text="ML",
        recent_scores=[],
        news=[],
    )
    assert "Today's news: (none)" in prompt
