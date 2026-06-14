"""OpenAI-compatible chat-completion client.

Talks to any `/v1/chat/completions` endpoint that follows the OpenAI schema:
OpenRouter (the hosted default) or a local LM Studio server, selected via `base_url`.
"""

from __future__ import annotations

import logging
from typing import Protocol

import requests

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class LLMError(RuntimeError):
    """Raised when the LLM call cannot complete or returns an unusable response."""


class LLMSummarizer(Protocol):
    """Strategy boundary so the summary pipeline can be tested without HTTP."""

    def generate(self, *, prompt: str) -> str: ...


class ChatCompletionsSummarizer:
    """Calls an OpenAI-compatible /v1/chat/completions endpoint with a single user message.

    Backend-agnostic: the same client serves OpenRouter (hosted) or LM Studio (local),
    chosen via `base_url`. Errors name the configured endpoint so logs stay truthful.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_FREE_MODEL,
        base_url: str = OPENROUTER_CHAT_URL,
        timeout_seconds: int = 60,
        require_api_key: bool = True,
        http_post=requests.post,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._require_api_key = require_api_key
        self._http_post = http_post

    def generate(self, *, prompt: str) -> str:
        if self._require_api_key and not self._api_key.strip():
            raise LLMError("LLM API key is not configured")
        try:
            r = self._http_post(
                self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning("LLM request to %s failed: %s", self._base_url, exc)
            raise LLMError(f"Could not reach LLM endpoint at {self._base_url}") from exc

        try:
            payload = r.json()
        except ValueError as exc:
            raise LLMError("LLM endpoint returned a non-JSON response") from exc

        if not r.ok:
            err = payload.get("error") if isinstance(payload, dict) else None
            message = err.get("message") if isinstance(err, dict) else None
            raise LLMError(f"LLM HTTP {r.status_code}: {message or payload}")

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise LLMError("LLM response missing choices")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM response missing text content")
        return content.strip()


# Backwards-compatible alias (the client is no longer OpenRouter-specific).
OpenRouterSummarizer = ChatCompletionsSummarizer
