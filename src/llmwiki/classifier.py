"""LLM classification service.

Sends extracted text to an OpenAI-compatible endpoint (OpenCode Zen) and
returns a structured ``LLMResponse`` result.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from llmwiki.config import LLMWikiConfig
from llmwiki.models import LLMResponse

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM_PROMPT = """\
You are a wiki content classifier. Analyze the provided text and return a \
JSON object with the following structure:
{
  "title": "Suggested page title",
  "summary": "2-3 sentence summary of the content",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "category": "High-level category for the page",
  "related_pages": [],
  "sections": [
    {"heading": "Section heading", "content": "Section body text"}
  ]
}

Rules:
- title: Concise, descriptive title derived from the content
- summary: 2-3 sentences capturing the key points
- tags: 3-5 relevant tags
- category: One of: technology, concept, tutorial, reference, guide, opinion, other
- related_pages: Leave empty for now
- sections: Break the content into structured sections with headings and body

Return ONLY valid JSON — no markdown fences, no extra text."""


class ClassifierService:
    """Service that sends text to an LLM for structured classification.

    Uses the OpenAI-compatible ``/v1/chat/completions`` endpoint exposed by
    the configured API provider.

    Transient errors (5xx, 429, network) are retried up to 3 times with
    exponential backoff. Auth errors (401, 403) fail immediately.
    """

    MAX_RETRIES = 3
    TEXT_TRUNCATION_LIMIT = 100_000  # chars — conservative for 200K context
    REQUEST_TIMEOUT = 60.0  # seconds

    def __init__(self, config: LLMWikiConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def classify(self, text: str, filename: str) -> LLMResponse:
        """Send *text* to the LLM and return structured classification.

        Args:
            text: The extracted text content to classify.
            filename: The original source filename (used in the prompt).

        Returns:
            An ``LLMResponse`` with the parsed classification.

        Raises:
            ValueError: If the API key is not configured.
            httpx.HTTPStatusError: For auth errors (401/403).
            RuntimeError: After 3 failed attempts.
        """
        if not self.config.llmwiki_api_key:
            raise ValueError(
                "llmwiki_api_key is not configured. "
                "Set LLMWIKI_API_KEY in your .env file or environment."
            )

        client = self._get_client()

        # Truncate to stay within model context limits
        truncated_text = text[: self.TEXT_TRUNCATION_LIMIT]
        if len(text) > self.TEXT_TRUNCATION_LIMIT:
            logger.info(
                "Truncated input text from %d to %d chars for %s",
                len(text), self.TEXT_TRUNCATION_LIMIT, filename,
            )

        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"File: {filename}\n\n---\n\n{truncated_text}",
            },
        ]

        payload: dict[str, Any] = {
            "model": self.config.llmwiki_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                return self._parse_response(data)

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise  # Auth errors — fail fast, no retry
                if status >= 500 or status == 429:
                    last_error = exc
                    if attempt < self.MAX_RETRIES - 1:
                        wait = 2**attempt
                        logger.warning(
                            "LLM API error (attempt %d/%d): HTTP %d. "
                            "Retrying in %ds...",
                            attempt + 1, self.MAX_RETRIES, status, wait,
                        )
                        await asyncio.sleep(wait)
                    continue
                raise  # Other 4xx — not retried

            except (httpx.RequestError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Transient error (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1, self.MAX_RETRIES, exc, wait,
                    )
                    await asyncio.sleep(wait)
                continue

        raise RuntimeError(
            f"LLM classification failed after {self.MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Internal helpers ──────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.llmwiki_api_endpoint,
                timeout=self.REQUEST_TIMEOUT,
                headers={
                    "Authorization": f"Bearer {self.config.llmwiki_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse the LLM API response into an ``LLMResponse``.

        Attempts to deserialise ``choices[0].message.content`` as JSON.
        If parsing fails, returns an ``LLMResponse`` with only
        ``raw_response`` populated and empty fields.
        """
        try:
            raw_content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected LLM API response structure: %s", exc)
            return LLMResponse(raw_response=str(data))

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse LLM response as JSON: %.200s…",
                raw_content,
            )
            return LLMResponse(raw_response=raw_content)

        return LLMResponse(
            title=parsed.get("title", ""),
            summary=parsed.get("summary", ""),
            tags=parsed.get("tags", []),
            category=parsed.get("category", ""),
            related_pages=parsed.get("related_pages", []),
            sections=parsed.get("sections", []),
            raw_response=raw_content,
        )
