from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from app.models import NewsArticle
from app.services.llm_service import LLMError, LLMSummarizer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You select news articles relevant to a user's interests.

Input: the user's free-text interests, followed by a numbered list of article titles.
Task: return the indices of the most relevant articles, most relevant first.

Rules:
- Output ONLY a JSON object: {"indices": [int, int, ...]}.
- At most K indices (K is specified in the request).
- Indices refer to positions in the provided list (0-based).
- If nothing is relevant, return {"indices": []}.
"""


class PerUserCandidateFilter:
    def __init__(
        self,
        summarizer: LLMSummarizer,
        *,
        batch_size: int = 500,
        top_per_batch: int = 25,
    ) -> None:
        self._summarizer = summarizer
        self._batch_size = batch_size
        self._top_per_batch = top_per_batch

    def pick_top(
        self,
        *,
        interests_text: str,
        articles: list[NewsArticle],
        top_n: int,
    ) -> list[NewsArticle]:
        if not articles:
            return []

        picked: list[NewsArticle] = []
        seen_urls: set[str] = set()
        any_batch_succeeded = False

        for _offset, batch in self._iter_batches(articles):
            indices = self._ask_llm_for_indices(
                interests_text=interests_text,
                batch=batch,
                limit=self._top_per_batch,
            )
            if indices is None:
                continue
            any_batch_succeeded = True
            for local_idx in indices:
                if local_idx < 0 or local_idx >= len(batch):
                    continue
                article = batch[local_idx]
                if not article.url or article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                picked.append(article)
                if len(picked) >= top_n:
                    return picked

        if not any_batch_succeeded:
            return articles[:top_n]

        return picked[:top_n]

    def _iter_batches(self, articles: list[NewsArticle]) -> Iterable[tuple[int, list[NewsArticle]]]:
        for offset in range(0, len(articles), self._batch_size):
            yield offset, articles[offset : offset + self._batch_size]

    def _ask_llm_for_indices(
        self,
        *,
        interests_text: str,
        batch: list[NewsArticle],
        limit: int,
    ) -> list[int] | None:
        lines = "\n".join(f"{i}. {a.title}" for i, a in enumerate(batch))
        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"User interests:\n{interests_text}\n\n"
            f"Articles (K = {limit}):\n{lines}\n\n"
            "Return the JSON object now."
        )
        try:
            raw = self._summarizer.generate(prompt=prompt)
        except LLMError as exc:
            logger.warning("Candidate filter LLM failed: %s", exc)
            return None

        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Candidate filter returned non-JSON: %r", raw[:200])
            return None

        if not isinstance(payload, dict):
            return None
        indices_raw = payload.get("indices")
        if not isinstance(indices_raw, list):
            return None

        result: list[int] = []
        for item in indices_raw:
            if isinstance(item, bool):
                continue  # bools are ints in Python; reject.
            if isinstance(item, int):
                result.append(item)
        return result[:limit]
