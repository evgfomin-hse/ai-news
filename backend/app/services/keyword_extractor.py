"""Extracts a GDELT-ready keyword query from the union of all users' interests."""

from __future__ import annotations

import json
import logging

from app.services.llm_service import LLMError, LLMSummarizer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are extracting search keywords for a news API query.

Input: a list of free-text "interests" strings from different users.
Task: produce a single deduplicated keyword/short-phrase list that, when joined
with " OR ", will surface news articles any of these users would care about.

Rules:
- Output ONLY a JSON object: {"global_query_keywords": ["kw1", "kw2", ...]}.
- Up to 25 entries. Prefer single nouns or 2-word phrases.
- Avoid stopwords, articles, generic terms ("news", "stuff").
- Use English keywords (the corpus is sourcelang=eng).
"""


class KeywordExtractor:
    """One LLM call → GDELT query string '(kw1 OR kw2 OR ...)'."""

    def __init__(
        self,
        summarizer: LLMSummarizer,
        *,
        max_query_chars: int = 450,
    ) -> None:
        self._summarizer = summarizer
        self._max_query_chars = max_query_chars

    def extract(self, users_with_interests: list[tuple[int, str]]) -> str | None:
        non_empty = [(uid, txt.strip()) for uid, txt in users_with_interests if txt and txt.strip()]
        if not non_empty:
            return None

        prompt = self._build_prompt(non_empty)
        try:
            raw = self._summarizer.generate(prompt=prompt)
        except LLMError as exc:
            logger.warning("Keyword extraction LLM failed: %s", exc)
            return None

        keywords = self._parse(raw)
        if not keywords:
            return None

        return self._format_query(keywords)

    @staticmethod
    def _build_prompt(non_empty: list[tuple[int, str]]) -> str:
        bullets = "\n".join(f"- user_{uid}: {txt}" for uid, txt in non_empty)
        return f"{_SYSTEM_PROMPT}\n\nInterests:\n{bullets}\n\nReturn the JSON object now."

    @staticmethod
    def _parse(raw: str) -> list[str]:
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Keyword extraction returned non-JSON: %r", raw[:200])
            return []
        if not isinstance(payload, dict):
            return []
        kws = payload.get("global_query_keywords")
        if not isinstance(kws, list):
            return []
        return [str(k).strip() for k in kws if isinstance(k, (str, int)) and str(k).strip()]

    def _format_query(self, keywords: list[str]) -> str:
        seen_lower: set[str] = set()
        deduped: list[str] = []
        for kw in keywords:
            lk = kw.lower()
            if lk in seen_lower:
                continue
            seen_lower.add(lk)
            deduped.append(kw)

        # Build incrementally; stop adding once we would exceed max_query_chars
        # (account for parens and " OR " joiners).
        accepted: list[str] = []
        for kw in deduped:
            candidate = "(" + " OR ".join([*accepted, kw]) + ")"
            if len(candidate) > self._max_query_chars:
                break
            accepted.append(kw)
        if not accepted:
            # Even one keyword overflowed — fall back to the single first keyword truncated.
            first = deduped[0][: max(self._max_query_chars - 2, 1)]
            return f"({first})"
        return "(" + " OR ".join(accepted) + ")"
