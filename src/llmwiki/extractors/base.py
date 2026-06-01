"""Abstract base extractor.

All extractors inherit from ``BaseExtractor`` and implement the ``extract``
method, returning ``(text, metadata)``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from llmwiki.models import Metadata


class ExtractionError(RuntimeError):
    """Raised when text extraction from a file fails.

    Wraps underlying errors from third-party libraries (docling,
    pytesseract, etc.) with a user-facing message.
    """


class BaseExtractor(ABC):
    """Abstract base for all text extractors.

    Each subclass declares the file extensions it supports via
    ``supported_extensions`` and implements ``extract()``.
    """

    supported_extensions: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    async def extract(self, path: Path) -> tuple[str, Metadata]:
        """Extract text and metadata from *path*.

        Returns ``(raw_text, Metadata)``.
        """
