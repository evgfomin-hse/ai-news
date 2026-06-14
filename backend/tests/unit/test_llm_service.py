"""Unit tests for the OpenRouter summarizer. HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from app.services.llm_service import ChatCompletionsSummarizer, LLMError

# The summarizer is backend-agnostic; the historical name still works via alias.
OpenRouterSummarizer = ChatCompletionsSummarizer


@dataclass
class _Resp:
    payload: Any
    status_code: int = 200

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _fake_post(response: _Resp):
    captured: dict[str, Any] = {}

    def _post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return response

    return _post, captured


def test_generate_raises_when_api_key_missing():
    post, _ = _fake_post(_Resp({}))
    svc = OpenRouterSummarizer(api_key="", http_post=post)
    with pytest.raises(LLMError, match="API key is not configured"):
        svc.generate(prompt="hello")


def test_generate_raises_on_network_error():
    def _raise(*_a, **_k):
        raise requests.RequestException("boom")

    svc = OpenRouterSummarizer(api_key="k", http_post=_raise)
    with pytest.raises(LLMError, match="Could not reach LLM endpoint"):
        svc.generate(prompt="hello")


def test_generate_raises_on_non_json():
    post, _ = _fake_post(_Resp(ValueError("not json")))
    svc = OpenRouterSummarizer(api_key="k", http_post=post)
    with pytest.raises(LLMError, match="non-JSON"):
        svc.generate(prompt="hello")


def test_generate_raises_on_http_error_with_message():
    post, _ = _fake_post(_Resp({"error": {"message": "model is busy"}}, status_code=503))
    svc = OpenRouterSummarizer(api_key="k", http_post=post)
    with pytest.raises(LLMError, match="model is busy"):
        svc.generate(prompt="hello")


def test_generate_raises_when_choices_missing():
    post, _ = _fake_post(_Resp({"choices": []}))
    svc = OpenRouterSummarizer(api_key="k", http_post=post)
    with pytest.raises(LLMError, match="missing choices"):
        svc.generate(prompt="hello")


def test_generate_raises_when_content_empty():
    post, _ = _fake_post(_Resp({"choices": [{"message": {"content": "   "}}]}))
    svc = OpenRouterSummarizer(api_key="k", http_post=post)
    with pytest.raises(LLMError, match="missing text content"):
        svc.generate(prompt="hello")


def test_generate_returns_trimmed_content_and_sends_authorization():
    post, captured = _fake_post(
        _Resp({"choices": [{"message": {"content": "  ## hello\n\nworld  "}}]})
    )
    svc = OpenRouterSummarizer(api_key="my-key", model="some/model:free", http_post=post)
    out = svc.generate(prompt="please summarize")
    assert out == "## hello\n\nworld"
    assert captured["headers"]["Authorization"] == "Bearer my-key"
    assert captured["json"]["model"] == "some/model:free"
    assert captured["json"]["messages"] == [{"role": "user", "content": "please summarize"}]


def test_generate_posts_to_configured_base_url():
    post, captured = _fake_post(_Resp({"choices": [{"message": {"content": "hi"}}]}))
    svc = OpenRouterSummarizer(
        api_key="k",
        base_url="http://127.0.0.1:1234/v1/chat/completions",
        http_post=post,
    )
    svc.generate(prompt="hello")
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"


def test_generate_allows_empty_key_when_not_required():
    """LM Studio needs no auth: an empty key must not short-circuit the call."""
    post, captured = _fake_post(_Resp({"choices": [{"message": {"content": "hi"}}]}))
    svc = OpenRouterSummarizer(
        api_key="",
        base_url="http://127.0.0.1:1234/v1/chat/completions",
        require_api_key=False,
        http_post=post,
    )
    assert svc.generate(prompt="hello") == "hi"
    assert captured["headers"]["Authorization"] == "Bearer "
