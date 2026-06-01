"""PDF text extraction via docling (optional dependency).

Uses ``docling`` (a heavy dependency — install with ``pip install llmwiki-ingest[pdf]``)
to parse PDF files, including scanned PDFs with OCR, table extraction, and
layout-aware text export.

All docling imports are **lazy** so the package works without it installed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from llmwiki.extractors.base import BaseExtractor, ExtractionError
from llmwiki.models import Metadata


class PdfExtractor(BaseExtractor):
    """Extract text from PDF files using docling.

    Handles both selectable-text PDFs and scanned PDFs (via docling's
    built-in OCR pipeline).

    Requires docling — install with::

        pip install llmwiki-ingest[pdf]

    Raises:
        ExtractionError: If the PDF cannot be parsed (corrupted file,
            permission error, docling not installed, etc.).
    """

    supported_extensions: ClassVar[frozenset[str]] = frozenset({".pdf"})

    async def extract(self, path: Path) -> tuple[str, Metadata]:
        """Extract text from the PDF at *path*.

        Delegates to docling's ``DocumentConverter`` for robust parsing
        that handles selectable text, scanned pages, tables, and layouts.

        Returns:
            A tuple of ``(extracted_text, Metadata)``.

        Raises:
            ExtractionError: If docling is not installed, the PDF is
                corrupted, or any other error occurs during extraction.
        """
        raw_bytes = path.read_bytes()
        file_size = len(raw_bytes)
        file_hash = hashlib.blake2b(raw_bytes).hexdigest()

        if file_size == 0:
            return "", Metadata(
                source_path=str(path),
                file_type="application/pdf",
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
                "PDF extraction requires docling. "
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
                    "PDF OCR requires Tesseract to be installed on the system. "
                    "Install it with your package manager "
                    "(e.g., apt install tesseract-ocr, brew install tesseract)."
                ) from exc
            raise ExtractionError(
                f"Failed to extract text from PDF '{path.name}': {exc}"
            ) from exc

        metadata = Metadata(
            source_path=str(path),
            file_type="application/pdf",
            file_size=file_size,
            encoding="utf-8",
            hash=file_hash,
            extracted_at=datetime.now(),
        )

        return text, metadata
