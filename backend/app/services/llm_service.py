"""OpenRouter chat-completion client. Uses the OpenAI-compatible /v1/chat/completions endpoint."""

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


class OpenRouterSummarizer:
    """Calls OpenRouter's chat-completions endpoint with a single user message."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_FREE_MODEL,
        timeout_seconds: int = 60,
        http_post=requests.post,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._http_post = http_post

    def generate(self, *, prompt: str) -> str:
        if not self._api_key.strip():
            raise LLMError("OPENROUTER_API_KEY is not configured")
        try:
            r = self._http_post(
                OPENROUTER_CHAT_URL,
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
            logger.warning("OpenRouter request failed: %s", exc)
            raise LLMError("Could not reach OpenRouter") from exc

        try:
            payload = r.json()
        except ValueError as exc:
            raise LLMError("OpenRouter returned a non-JSON response") from exc

        if not r.ok:
            err = payload.get("error") if isinstance(payload, dict) else None
            message = err.get("message") if isinstance(err, dict) else None
            raise LLMError(f"OpenRouter HTTP {r.status_code}: {message or payload}")

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise LLMError("OpenRouter response missing choices")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("OpenRouter response missing text content")
        return content.strip()
