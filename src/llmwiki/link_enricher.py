"""Link enrichment for the ingestion pipeline.

Detects URLs of all kinds inside extracted text and fetches their content:
- **YouTube** → transcript via ``youtube-transcript-api``
- **GitHub** → raw README via ``raw.githubusercontent.com``
- **Generic web** → page text via ``httpx`` + basic HTML-to-text extraction

All fetched content is appended to the original text so the LLM can classify
and summarise everything together.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── URL patterns ────────────────────────────────────────────────────────

_YOUTUBE_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.|m\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"(?:"
    r"  /watch\?v=([\w-]{11})"
    r"  |/embed/([\w-]{11})"
    r"  |/shorts/([\w-]{11})"
    r"  |/([\w-]{11})"
    r")",
    re.VERBOSE | re.IGNORECASE,
)

_GITHUB_REPO_RE = re.compile(
    r"github\.com/([^/\s]+)/([^/\s#?]+)",
    re.IGNORECASE,
)

_GENERIC_URL_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)

# Limits
_MAX_TRANSCRIPT_CHARS = 50_000
_MAX_PAGE_CHARS = 30_000
_HTTP_TIMEOUT = 15.0  # seconds


# ── YouTube ─────────────────────────────────────────────────────────────

def _fetch_youtube(video_id: str) -> Optional[str]:
    """Fetch the English transcript for a YouTube video."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError:
        logger.warning("youtube-transcript-api not installed")
        return None

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        text = " ".join(segment.text for segment in transcript)
        logger.info("Fetched YouTube transcript for %s (%d chars)", video_id, len(text))
        return text[:_MAX_TRANSCRIPT_CHARS]
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        logger.debug("No transcript for video %s", video_id)
    except Exception:
        logger.exception("Error fetching transcript for %s", video_id)
    return None


# ── GitHub ──────────────────────────────────────────────────────────────

_GITHUB_README_CANDIDATES = [
    "master/README.md",
    "main/README.md",
    "master/README.rst",
    "main/README.rst",
    "master/README.txt",
    "main/README.txt",
]


def _fetch_github_readme(owner: str, repo: str) -> Optional[str]:
    """Fetch the README of a GitHub repository via raw.githubusercontent.com."""
    import httpx as _httpx

    for candidate in _GITHUB_README_CANDIDATES:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{candidate}"
        try:
            resp = _httpx.get(url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 50:
                text = resp.text[:_MAX_PAGE_CHARS]
                logger.info("Fetched README for %s/%s (%d chars)", owner, repo, len(text))
                return text
        except Exception:
            continue
    logger.debug("No README found for %s/%s", owner, repo)
    return None


# ── Generic web ─────────────────────────────────────────────────────────

# Minimal HTML-to-text: strip tags, collapse whitespace
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WHITESPACE = re.compile(r"\s+")


def _html_to_text(html: str) -> str:
    """Crude but fast HTML-to-text extraction."""
    text = _RE_TAG.sub("", html)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    text = _RE_WHITESPACE.sub(" ", text)
    return text.strip()


def _fetch_webpage(url: str) -> Optional[str]:
    """Fetch a webpage and return its plain-text content."""
    try:
        resp = httpx.get(url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type:
            logger.debug("Skipping non-text URL: %s (%s)", url, content_type)
            return None
        text = _html_to_text(resp.text)
        text = text[:_MAX_PAGE_CHARS]
        if len(text) < 50:
            logger.debug("Page %s too short (%d chars), skipping", url, len(text))
            return None
        logger.info("Fetched webpage %s (%d chars)", url, len(text))
        return text
    except httpx.HTTPStatusError as e:
        logger.debug("HTTP %d for %s", e.response.status_code, url)
    except Exception:
        logger.debug("Error fetching %s", url)
    return None


# ── Orchestrator ────────────────────────────────────────────────────────


class LinkContent:
    """Content fetched from a single link."""

    def __init__(self, url: str, content: str, source_label: str) -> None:
        self.url = url
        self.content = content
        self.source_label = source_label  # e.g. "YouTube Transcript", "README", "Web Page"


def _classify_url(url: str) -> Optional[LinkContent]:
    """Fetch and return content for a single URL, or ``None`` on failure."""
    # YouTube
    m = _YOUTUBE_RE.search(url)
    if m:
        vid = next(g for g in m.groups() if g is not None)
        text = _fetch_youtube(vid)
        if text:
            return LinkContent(url, text, f"YouTube Transcript ({vid})")
        return None

    # GitHub repo README
    m = _GITHUB_REPO_RE.search(url)
    if m:
        owner, repo = m.group(1), m.group(2).rstrip("/")
        text = _fetch_github_readme(owner, repo)
        if text:
            return LinkContent(url, text, f"GitHub README: {owner}/{repo}")
        return None

    # Generic webpage
    text = _fetch_webpage(url)
    if text:
        return LinkContent(url, text, "Web Page")

    return None


def enrich_all_links(text: str) -> tuple[str, list[LinkContent]]:
    """Scan *text* for all URLs, fetch their content, and return enriched text + link list.

    Returns:
        A tuple ``(enriched_text, link_contents)`` where *enriched_text* has
        all feteched content appended. *link_contents* is the list of
        successfully fetched ``LinkContent`` objects (useful for downstream
        classification).
    """
    # Collect all unique URLs
    seen_urls: set[str] = set()
    all_urls: list[str] = []

    for m in _GENERIC_URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?)'\"")
        if url not in seen_urls:
            seen_urls.add(url)
            all_urls.append(url)

    if not all_urls:
        return text, []

    logger.info("Found %d URL(s) in content", len(all_urls))

    fetched: list[LinkContent] = []
    for url in all_urls:
        content = _classify_url(url)
        if content:
            fetched.append(content)

    if not fetched:
        return text, []

    # Build enriched text
    parts = [text]
    for fc in fetched:
        parts.append(f"\n\n---\n[{fc.source_label}]({fc.url})\n{fc.content}")

    enriched = "".join(parts)
    logger.info("Enriched text with %d link(s) (%d → %d chars)", len(fetched), len(text), len(enriched))
    return enriched, fetched
