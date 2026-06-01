"""YouTube transcript enrichment for the ingestion pipeline.

Detects YouTube video URLs inside extracted text and fetches their
transcripts via ``youtube-transcript-api`` (no API key required). The
transcript text is appended to the original content so the LLM classifier
can use it for wiki page generation.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── YouTube URL patterns ────────────────────────────────────────────────
# Matches all common YouTube URL formats:
#   https://www.youtube.com/watch?v=VIDEO_ID
#   https://youtu.be/VIDEO_ID
#   https://www.youtube.com/embed/VIDEO_ID
#   https://www.youtube.com/shorts/VIDEO_ID
#   https://m.youtube.com/watch?v=VIDEO_ID
_YOUTUBE_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.|m\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"(?:"
    r"  /watch\?v=([\w-]{11})"          # /watch?v=VIDEO_ID
    r"  |/embed/([\w-]{11})"            # /embed/VIDEO_ID
    r"  |/shorts/([\w-]{11})"           # /shorts/VIDEO_ID
    r"  |/([\w-]{11})"                  # youtu.be/VIDEO_ID
    r")",
    re.VERBOSE | re.IGNORECASE,
)

# Maximum transcript length in characters (conservative)
_MAX_TRANSCRIPT_CHARS = 50_000


def extract_video_ids(text: str) -> list[str]:
    """Extract all unique YouTube video IDs from *text*.

    Handles multiple URL formats and deduplicates IDs.
    """
    ids: list[str] = []
    seen: set[str] = set()

    for match in _YOUTUBE_RE.finditer(text):
        # Only one of the four capture groups will be set
        vid = next(g for g in match.groups() if g is not None)
        if vid not in seen:
            seen.add(vid)
            ids.append(vid)

    return ids


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch the English transcript for *video_id*.

    Returns the transcript as a single string (segments joined by spaces),
    or ``None`` if no transcript is available (disabled, unavailable,
    no English captions).

    Uses ``youtube-transcript-api`` which does **not** require an API key.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError:
        logger.warning(
            "youtube-transcript-api not installed — "
            "install with: uv pip install 'llmwiki-ingest[youtube]'"
        )
        return None

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        text = " ".join(segment.text for segment in transcript)
        logger.info(
            "Fetched transcript for video %s (%d chars)", video_id, len(text)
        )
        return text[: _MAX_TRANSCRIPT_CHARS]

    except TranscriptsDisabled:
        logger.debug("Transcripts disabled for video %s", video_id)
    except NoTranscriptFound:
        logger.debug("No English transcript found for video %s", video_id)
    except VideoUnavailable:
        logger.debug("Video %s is unavailable", video_id)
    except Exception:
        logger.exception("Unexpected error fetching transcript for %s", video_id)

    return None


def enrich_with_transcripts(text: str) -> str:
    """Scan *text* for YouTube URLs and append transcript content.

    For each unique video URL found in the text, the transcript is
    fetched and appended as a formatted section::

        [YouTube Transcript: <video_id>]
        <transcript text>

    If no YouTube URLs are found, the original text is returned unchanged.
    If a transcript cannot be fetched, the original text is returned with
    a warning logged (no interruption to the pipeline).
    """
    video_ids = extract_video_ids(text)
    if not video_ids:
        return text

    logger.info("Found %d YouTube URL(s) in content", len(video_ids))

    parts = [text]
    for vid in video_ids:
        transcript = fetch_transcript(vid)
        if transcript:
            parts.append(f"\n\n[YouTube Transcript: {vid}]\n{transcript}")
        else:
            logger.info(
                "No transcript available for video %s — "
                "proceeding with original content only",
                vid,
            )

    enriched = "".join(parts)
    logger.info(
        "Enriched text with %d transcript(s) (%d → %d chars)",
        len(video_ids),
        len(text),
        len(enriched),
    )
    return enriched
