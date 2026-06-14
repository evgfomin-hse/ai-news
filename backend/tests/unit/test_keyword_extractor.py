"""Unit tests for KeywordExtractor — LLM is replaced with an injected fake."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.services.keyword_extractor import KeywordExtractor
from app.services.llm_service import LLMError


@dataclass
class _FakeSummarizer:
    response: str | Exception

    def generate(self, *, prompt: str) -> str:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_returns_none_when_no_users():
    ext = KeywordExtractor(_FakeSummarizer(response="never called"))
    assert ext.extract([]) is None


def test_returns_none_when_all_interests_empty():
    ext = KeywordExtractor(_FakeSummarizer(response="never called"))
    assert ext.extract([(1, ""), (2, "   "), (3, "\n")]) is None


def test_returns_query_string_from_valid_json():
    payload = json.dumps({"global_query_keywords": ["AI", "robotics", "climate"]})
    ext = KeywordExtractor(_FakeSummarizer(response=payload))
    result = ext.extract([(1, "AI, robotics"), (2, "climate change")])
    assert result == "(AI OR robotics OR climate)"


def test_dedupes_case_insensitively_preserving_first_occurrence():
    payload = json.dumps({"global_query_keywords": ["AI", "ai", "Robotics", "ROBOTICS"]})
    ext = KeywordExtractor(_FakeSummarizer(response=payload))
    assert ext.extract([(1, "tech")]) == "(AI OR Robotics)"


def test_returns_none_on_llm_error():
    ext = KeywordExtractor(_FakeSummarizer(response=LLMError("boom")))
    assert ext.extract([(1, "AI")]) is None


def test_returns_none_on_malformed_json():
    ext = KeywordExtractor(_FakeSummarizer(response="not json"))
    assert ext.extract([(1, "AI")]) is None


def test_returns_none_when_keyword_list_missing_or_empty():
    ext = KeywordExtractor(_FakeSummarizer(response=json.dumps({})))
    assert ext.extract([(1, "AI")]) is None

    ext2 = KeywordExtractor(_FakeSummarizer(response=json.dumps({"global_query_keywords": []})))
    assert ext2.extract([(1, "AI")]) is None


def test_truncates_at_max_query_chars():
    keywords = [f"kw{i}" for i in range(200)]  # plenty to overflow
    payload = json.dumps({"global_query_keywords": keywords})
    ext = KeywordExtractor(_FakeSummarizer(response=payload), max_query_chars=30)
    query = ext.extract([(1, "tech")])
    assert query is not None
    assert len(query) <= 30
    assert query.startswith("(")
    assert query.endswith(")")
