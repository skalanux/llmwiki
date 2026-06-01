"""Application configuration via pydantic-settings.

Loads configuration from ``.env`` and environment variables.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMWikiConfig(BaseSettings):
    """Configuration for the LLM wiki ingestion pipeline.

    All values can be overridden via environment variables or a ``.env`` file.

    Directory resolution:
    - ``base_dir`` is the root for all data directories (inbox, wiki).
      If empty, the current working directory is used.
    - ``inbox_dir`` and ``wiki_dir`` can be **absolute** paths or
      **relative** to ``base_dir``.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llmwiki_api_key: str = ""
    llmwiki_api_endpoint: str = "https://api.opencode.ai/v1"
    llmwiki_model: str = "deepseek-v4-flash-free"

    # ── External directories ──────────────────────────────────────────
    # Base directory for all runtime data.  Empty = current directory.
    llmwiki_base_dir: str = ""
    # Inbox and wiki dirs — relative to base_dir, or absolute paths.
    llmwiki_inbox_dir: str = "inbox"
    llmwiki_wiki_dir: str = "wiki"

    llmwiki_watch: bool = False
    llmwiki_ocr_enabled: bool = False

    @property
    def resolved_inbox_dir(self) -> Path:
        """Return the absolute inbox path."""
        return self._resolve(self.llmwiki_inbox_dir)

    @property
    def resolved_wiki_dir(self) -> Path:
        """Return the absolute wiki path."""
        return self._resolve(self.llmwiki_wiki_dir)

    # ── Internal helpers ──────────────────────────────────────────────

    def _resolve(self, candidate: str) -> Path:
        path = Path(candidate)
        if path.is_absolute():
            return path
        base = Path(self.llmwiki_base_dir) if self.llmwiki_base_dir else Path.cwd()
        return base / path
