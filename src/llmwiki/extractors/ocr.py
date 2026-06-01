"""Image OCR text extraction via docling (optional dependency).

Uses ``docling`` (which bundles Tesseract-based OCR) to extract text from
image files — PNG, JPEG, TIFF, BMP.

All docling imports are **lazy** so the package works without it installed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from llmwiki.extractors.base import BaseExtractor, ExtractionError
from llmwiki.models import Metadata

# MIME type lookup for supported image extensions
_IMAGE_MIME_MAP: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}


class OcrExtractor(BaseExtractor):
    """Extract text from images via OCR using docling.

    Docling handles OCR internally — it detects whether Tesseract is
    available and uses it for text recognition on image files.

    Requires docling — install with::

        pip install llmwiki-ingest[pdf]

    Additionally requires **Tesseract** to be installed on the system:
    https://github.com/tesseract-ocr/tesseract

    Raises:
        ExtractionError: If docling or Tesseract is not installed, or
            if the image cannot be processed.
    """

    supported_extensions: ClassVar[frozenset[str]] = frozenset({
        ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
    })

    async def extract(self, path: Path) -> tuple[str, Metadata]:
        """Run OCR on the image at *path*.

        Delegates to docling's ``DocumentConverter`` which internally runs
        Tesseract for text recognition.

        Returns:
            A tuple of ``(extracted_text, Metadata)``.

        Raises:
            ExtractionError: If docling is not installed, Tesseract is
                not available on the system, or the image is corrupted.
        """
        raw_bytes = path.read_bytes()
        file_size = len(raw_bytes)
        file_hash = hashlib.blake2b(raw_bytes).hexdigest()
        mime_type = _IMAGE_MIME_MAP.get(path.suffix.lower(), "image/unknown")

        if file_size == 0:
            return "", Metadata(
                source_path=str(path),
                file_type=mime_type,
                file_size=0,
                encoding="utf-8",
                hash=file_hash,
                extracted_at=datetime.now(),
            )

        # Lazy import — docling is an optional dependency
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ExtractionError(
                "OCR extraction requires docling. "
                "Install it with: pip install llmwiki-ingest[pdf]"
            ) from exc

        try:
            converter = DocumentConverter()
            result = converter.convert(str(path))
            text = result.document.export_to_text()
        except Exception as exc:
            exc_msg = str(exc).lower()
            if "tesseract" in exc_msg or "tesseract not found" in exc_msg:
                raise ExtractionError(
                    "OCR requires Tesseract to be installed on the system. "
                    "Install it with your package manager "
                    "(e.g., apt install tesseract-ocr, brew install tesseract, "
                    "or choco install tesseract)."
                ) from exc
            raise ExtractionError(
                f"Failed to run OCR on image '{path.name}': {exc}"
            ) from exc

        metadata = Metadata(
            source_path=str(path),
            file_type=mime_type,
            file_size=file_size,
            encoding="utf-8",
            hash=file_hash,
            extracted_at=datetime.now(),
        )

        return text, metadata
