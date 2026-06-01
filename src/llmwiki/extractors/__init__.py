"""Extractor dispatch — maps file extensions to extractor classes."""
from __future__ import annotations

from pathlib import Path

from llmwiki.extractors.base import BaseExtractor, ExtractionError
from llmwiki.extractors.ocr import OcrExtractor
from llmwiki.extractors.pdf import PdfExtractor
from llmwiki.extractors.text import PlainTextExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionError",
    "PlainTextExtractor",
    "PdfExtractor",
    "OcrExtractor",
    "get_extractor",
]

_EXTRACTOR_REGISTRY: list[type[BaseExtractor]] = [
    PlainTextExtractor,
    PdfExtractor,
    OcrExtractor,
]


def get_extractor(file_path: Path) -> BaseExtractor:
    """Return the appropriate extractor for the given *file_path*.

    The selection is based on the file's extension:

    * ``.md``, ``.txt``, ``.text`` → :class:`PlainTextExtractor`
    * ``.pdf`` → :class:`PdfExtractor`
    * ``.png``, ``.jpg``, ``.jpeg``, ``.tiff``, ``.bmp`` → :class:`OcrExtractor`

    Raises:
        ValueError: If no extractor supports the file extension.
    """
    suffix = file_path.suffix.lower()

    for extractor_cls in _EXTRACTOR_REGISTRY:
        if suffix in extractor_cls.supported_extensions:
            return extractor_cls()

    raise ValueError(
        f"No extractor found for extension '{suffix}'. "
        f"Supported: .md, .txt, .text, .pdf, .png, .jpg, .jpeg, .tiff, .bmp"
    )
