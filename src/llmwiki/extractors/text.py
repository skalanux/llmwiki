"""Plain text extractor for ``.md`` and ``.txt`` files."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from llmwiki.extractors.base import BaseExtractor
from llmwiki.models import Metadata


class PlainTextExtractor(BaseExtractor):
    """Extracts text from plain text files with UTF-8/Latin-1 fallback."""

    supported_extensions: ClassVar[frozenset[str]] = frozenset({".md", ".txt", ".text"})

    _MIME_MAP: dict[str, str] = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".text": "text/plain",
    }

    async def extract(self, path: Path) -> tuple[str, Metadata]:
        """Read the file and return its contents with metadata.

        Tries UTF-8 encoding first; falls back to Latin-1 if that fails.
        If neither succeeds, decodes with replacement characters.

        Returns:
            A tuple of ``(extracted_text, Metadata)``.
        """
        raw_bytes = path.read_bytes()
        file_size = len(raw_bytes)

        # Handle empty files
        if file_size == 0:
            empty_hash = hashlib.blake2b(b"").hexdigest()
            return "", Metadata(
                source_path=str(path),
                file_type=self._mime_type(path),
                file_size=0,
                encoding="utf-8",
                hash=empty_hash,
                extracted_at=datetime.now(),
            )

        # Try UTF-8 first, then Latin-1
        text: str | None = None
        detected_encoding: str = "utf-8"

        for enc in ("utf-8", "latin-1"):
            try:
                text = raw_bytes.decode(enc)
                detected_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            text = raw_bytes.decode("utf-8", errors="replace")
            detected_encoding = "utf-8"

        file_hash = hashlib.blake2b(raw_bytes).hexdigest()
        metadata = Metadata(
            source_path=str(path),
            file_type=self._mime_type(path),
            file_size=file_size,
            encoding=detected_encoding,
            hash=file_hash,
            extracted_at=datetime.now(),
        )

        return text, metadata

    def _mime_type(self, path: Path) -> str:
        return self._MIME_MAP.get(path.suffix.lower(), "text/plain")
