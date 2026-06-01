"""LangGraph state definition for the ingestion pipeline."""
from __future__ import annotations

from typing import Optional, TypedDict

from llmwiki.models import ClassificationResult, Metadata


class State(TypedDict):
    """Shared state passed between pipeline nodes.

    Each node reads from and writes to this state as it moves through the
    Extract → Classify → Generate → Write sequence.
    """

    file_path: str                         # Source file being processed
    hash: str                              # BLAKE2b hash for dedup
    raw_text: str                          # Extracted text content
    metadata: Optional[Metadata]           # File metadata after extraction
    classification: Optional[ClassificationResult]  # LLM classification result
    wiki_content: str                      # Generated markdown content
    output_path: str                       # Where the wiki page will be written
    errors: list[str]                      # Accumulated errors during pipeline
    skipped: bool                          # True if pipeline was bypassed (hash duplicate)
