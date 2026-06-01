"""Wiki page generator.

Builds a Markdown file with YAML frontmatter from a ``ClassificationResult``
and writes it to the configured wiki directory.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml

from llmwiki.models import ClassificationResult, PageData


class WikiWriter:
    """Writes classified content as wiki pages with YAML frontmatter.

    Generates a slug from the page title, checks whether the content has
    changed via hash comparison, and skips the write if the file already
    exists with the same hash.

    If the ``ClassificationResult`` contains ``additional_pages`` (from
    links covering different topics), each one is written as a separate
    ``.md`` file in the wiki directory.
    """

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir

    async def write(self, result: ClassificationResult) -> str:
        """Generate a markdown page and write it to the wiki directory.

        Also writes any ``additional_pages`` from the classification
        result as separate ``.md`` files.

        Args:
            result: The full classification result with source metadata
                and LLM classification response.

        Returns:
            The absolute path of the **main** written file as a string.
        """
        output_path = await self._write_page(
            title=result.classification.title or Path(result.metadata.source_path).stem,
            summary=result.classification.summary,
            tags=result.classification.tags,
            category=result.classification.category,
            sections=result.classification.sections,
            related_pages=result.classification.related_pages,
            source=result.metadata.source_path,
            hash_val=result.metadata.hash,
        )

        # ── Write additional pages for linked content ─────────────────
        for ap in result.additional_pages:
            await self._write_page(
                title=ap.title or "Linked Content",
                summary=ap.summary,
                tags=ap.tags,
                category=ap.category,
                sections=ap.sections,
                related_pages=[],
                source=ap.source_url or result.metadata.source_path,
                hash_val=result.metadata.hash,
            )

        return output_path

    # ── Internal page writer ──────────────────────────────────────────

    async def _write_page(
        self,
        *,
        title: str,
        summary: str,
        tags: list[str],
        category: str,
        sections: list[dict[str, str]],
        related_pages: list[str],
        source: str,
        hash_val: str,
    ) -> str:
        """Render and write a single wiki page, returning its path."""
        slug = self._sanitize_title(title)
        output_path = self.wiki_dir / f"{slug}.md"

        # Hash-check skip: if the file exists with the same hash, no-op
        if output_path.exists():
            existing_hash = self._read_frontmatter_hash(output_path)
            if existing_hash == hash_val:
                return str(output_path)

        # ── Build YAML frontmatter ────────────────────────────────────
        frontmatter = {
            "title": title,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tags": tags or None,
            "category": category or None,
            "source": source,
            "hash": hash_val,
        }
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

        # ── Build markdown body ───────────────────────────────────────
        parts: list[str] = [
            "---",
            yaml.dump(frontmatter, default_flow_style=False).rstrip(),
            "---",
            "",
            f"# {title}",
            "",
        ]

        if summary:
            parts.append(summary)
            parts.append("")

        for section in sections:
            heading = section.get("heading", "")
            content = section.get("content", "")
            if heading:
                parts.append(f"## {heading}")
                parts.append("")
            if content:
                parts.append(content)
                parts.append("")

        if related_pages:
            parts.append("## Related Pages")
            parts.append("")
            for page in related_pages:
                parts.append(f"- [[{page}]]")
            parts.append("")

        # ── Write ─────────────────────────────────────────────────────
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
        return str(output_path)

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _sanitize_title(title: str) -> str:
        """Convert *title* to a URL-friendly slug.

        1. Lowercases the string.
        2. Replaces non-alphanumeric characters (except accented letters,
           ñ, ü) with a single hyphen.
        3. Collapses consecutive hyphens.
        4. Strips leading/trailing hyphens.
        """
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9áéíóúüñ]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return slug or "untitled"

    @staticmethod
    def _read_frontmatter_hash(path: Path) -> str:
        """Extract the ``hash`` field from an existing file's frontmatter.

        Returns an empty string if:
        * The file does not exist or cannot be read.
        * No valid YAML frontmatter delimiters (``---``) are found.
        * The frontmatter contains no ``hash`` field.
        """
        try:
            content = path.read_text("utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            return ""

        match = re.match(r"^---\s*\n(.*?)\n(?:---|\.\.\.)", content, re.DOTALL)
        if not match:
            return ""

        try:
            data = yaml.safe_load(match.group(1))
            if isinstance(data, dict):
                return str(data.get("hash", ""))
        except yaml.YAMLError:
            return ""

        return ""
