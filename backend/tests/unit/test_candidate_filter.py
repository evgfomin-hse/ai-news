"""Unit tests for PerUserCandidateFilter — LLM replaced with a programmable fake."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from app.models import NewsArticle
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.llm_service import LLMError


@dataclass
class _ScriptedSummarizer:
    """Returns the next scripted response for each `generate` call."""

    responses: list[str | Exception]
    prompts: list[str] = field(default_factory=list)

    def generate(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("Unexpected extra LLM call")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _article(idx: int) -> NewsArticle:
    return NewsArticle(
        fetched_at=datetime(2026, 6, 6, 3, 0, 0),
        source="gdelt:doc",
        title=f"Title {idx}",
        description=None,
        url=f"https://example.test/a{idx}",
        published_at=datetime(2026, 6, 5, 12, 0, 0),
    )


def _picks(indices: list[int]) -> str:
    return json.dumps({"indices": indices})


def test_empty_input_returns_empty_no_llm_call():
    summ = _ScriptedSummarizer(responses=[])
    f = PerUserCandidateFilter(summ)
    assert f.pick_top(interests_text="AI", articles=[], top_n=50) == []
    assert summ.prompts == []


def test_chunks_at_batch_size_and_dedupes_across_batches():
    # 600 articles → batches of 500 + 100.
    pool = [_article(i) for i in range(600)]
    # Each batch returns indices 0..24 (top 25 per batch).
    summ = _ScriptedSummarizer(responses=[_picks(list(range(25))), _picks(list(range(25)))])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)

    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)

    # Batch 1 → articles 0..24; batch 2 → articles 500..524. Total 50, no dup.
    urls = [a.url for a in picked]
    assert len(picked) == 50
    assert len(set(urls)) == 50
    assert urls[:25] == [pool[i].url for i in range(25)]
    assert urls[25:] == [pool[500 + i].url for i in range(25)]


def test_returns_first_top_n_preserving_pool_order_when_more_picked():
    # 300 articles, batch_size 500 → single batch. LLM returns 30 indices, we want top 20.
    pool = [_article(i) for i in range(300)]
    summ = _ScriptedSummarizer(responses=[_picks(list(range(30)))])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=30)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=20)
    assert [a.url for a in picked] == [pool[i].url for i in range(20)]


def test_one_failed_batch_does_not_drop_other_batches():
    pool = [_article(i) for i in range(800)]
    # Batch 1 fails; batches 2 returns picks.
    summ = _ScriptedSummarizer(responses=[LLMError("boom"), _picks([0, 1, 2])])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)
    # Only batch 2's picks survive (indices 0..2 inside batch 2 = pool[500..502]).
    assert [a.url for a in picked] == [pool[500 + i].url for i in range(3)]


def test_all_batches_failing_falls_back_to_first_top_n():
    pool = [_article(i) for i in range(800)]
    summ = _ScriptedSummarizer(responses=[LLMError("boom"), LLMError("boom2")])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=10)
    assert [a.url for a in picked] == [pool[i].url for i in range(10)]


def test_malformed_json_treated_as_batch_failure():
    pool = [_article(i) for i in range(200)]
    summ = _ScriptedSummarizer(responses=["not json"])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    # Single batch, fails → fallback to first 5.
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=5)
    assert [a.url for a in picked] == [pool[i].url for i in range(5)]


def test_out_of_range_and_non_integer_indices_are_dropped():
    pool = [_article(i) for i in range(10)]
    summ = _ScriptedSummarizer(responses=[json.dumps({"indices": [0, 999, "x", -1, 3]})])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)
    assert [a.url for a in picked] == [pool[0].url, pool[3].url]
