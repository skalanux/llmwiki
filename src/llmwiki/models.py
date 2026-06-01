"""Pydantic models for the ingestion pipeline data structures."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    """File metadata collected during the text-extraction step.

    Attributes:
        source_path: Original file path of the source document.
        file_type: MIME type or file extension (e.g. ``text/markdown``).
        file_size: Size of the source file in bytes.
        encoding: Detected text encoding (e.g. ``utf-8``, ``latin-1``).
        hash: BLAKE2b hex digest used for deduplication.
        extracted_at: Timestamp when extraction completed.
    """

    source_path: str = Field(description="Original file path of the source document")
    file_type: str = Field(description="MIME type or file extension of the source")
    file_size: int = Field(description="Size of the source file in bytes", ge=0)
    encoding: str = Field(default="utf-8", description="Detected text encoding")
    hash: str = Field(description="BLAKE2b hex digest for deduplication")
    extracted_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when extraction completed",
    )


class LLMResponse(BaseModel):
    """Structured classification data returned by the LLM.

    Represents the parsed JSON response from the LLM classification step.
    The ``raw_response`` field preserves the original API response for
    debugging and audit trails.
    """

    title: str = Field(description="Suggested title for the wiki page")
    summary: str = Field(description="One-paragraph summary of the source content")
    tags: list[str] = Field(
        default_factory=list,
        description="Relevant tags for categorisation",
    )
    category: str = Field(default="", description="High-level content category")
    related_pages: list[str] = Field(
        default_factory=list,
        description="Slugs or titles of related wiki pages",
    )
    sections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured sections with heading and body content",
    )
    raw_response: str = Field(
        default="",
        description="Raw JSON string returned by the LLM API",
    )


class ClassificationResult(BaseModel):
    """Final output of the classification pipeline.

    Combines the source metadata, the LLM classification response, and the
    destination path where the generated wiki page was written.
    """

    metadata: Metadata = Field(description="File metadata from the extraction step")
    classification: LLMResponse = Field(
        description="LLM classification result",
    )
    wiki_path: str = Field(
        description="Destination path where the wiki page was written",
    )
