"""Typer CLI for llmwiki-ingest.

Provides the ``ingest``, ``watch``, ``config``, and ``status`` commands
that drive the pipeline from the command line.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sqlite3
import threading
from pathlib import Path

import typer

from llmwiki.config import LLMWikiConfig
from llmwiki.pipeline import run_pipeline

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="llmwiki-ingest",
    help="LLM Wiki — automatic ingestion and classification pipeline.",
)


@app.command()
def ingest(
    file: Path = typer.Argument(
        ...,
        help="File to ingest and classify",
        exists=False,
        readable=True,
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the LLM model configured in .env",
    ),
) -> None:
    """Process a single file through the ingestion pipeline.

    Loads configuration from ``.env`` and environment variables, builds the
    LangGraph pipeline, and runs
    ``Hash-Check → Extract → Classify → Generate → Write`` on the given
    *file*.

    For continuous directory monitoring use ``llmwiki-ingest watch`` instead.
    """
    # -- Pre-flight checks --------------------------------------------------
    if not file.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(1)

    config = LLMWikiConfig()
    if not config.llmwiki_api_key:
        typer.echo(
            "Error: LLMWIKI_API_KEY is not configured.\n"
            "Set it in a .env file or as an environment variable.",
            err=True,
        )
        raise typer.Exit(1)

    if model:
        config.llmwiki_model = model

    _warn_ocr_config(config)

    # -- Run pipeline -------------------------------------------------------
    asyncio.run(_run_ingest(config, file))


@app.command()
def watch(
    directory: Path = typer.Argument(
        None,
        help="Directory to watch for new files.  Defaults to LLMWIKI_INBOX_DIR from config.",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the LLM model configured in .env",
    ),
) -> None:
    """Watch a directory for new files and process them automatically.

    Uses ``watchdog`` to monitor the directory for ``IN_CLOSE_WRITE``
    events.  Each new file (or modified file) is fed through the ingestion
    pipeline: Hash-Check → Extract → Classify → Generate → Write.

    Temp files (``.swp``, ``.swo``, ``~`` suffix, dotfiles, ``.tmp``) are
    ignored.  Rapid writes of the same file are debounced (5-second
    cooldown).

    Press :kbd:`Ctrl+C` to stop watching.
    """
    config = LLMWikiConfig()
    if not config.llmwiki_api_key:
        typer.echo(
            "Error: LLMWIKI_API_KEY is not configured.\n"
            "Set it in a .env file or as an environment variable.",
            err=True,
        )
        raise typer.Exit(1)

    if model:
        config.llmwiki_model = model

    _warn_ocr_config(config)

    watch_dir = directory if directory is not None else config.resolved_inbox_dir
    if not watch_dir.is_dir():
        typer.echo(f"Error: Directory not found: {watch_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Watching directory: {watch_dir}")
    typer.echo("Press Ctrl+C to stop.")

    from llmwiki.file_watcher import FileWatcherService

    watcher = FileWatcherService(config, watch_dir)
    watcher.start()

    # Wait until a signal tells us to shut down
    stop_event = threading.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        typer.echo("\nShutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        stop_event.wait()
    finally:
        watcher.stop()
        typer.echo("Watcher stopped.")


@app.command()
def config() -> None:
    """Show current runtime configuration.

    Displays all :class:`~llmwiki.config.LLMWikiConfig` values with the
    API key partially masked.
    """
    cfg = LLMWikiConfig()
    key = cfg.llmwiki_api_key

    if len(key) > 12:
        masked = key[:8] + "…" + key[-4:]
    elif key:
        masked = "(set)"
    else:
        masked = "(not set)"

    typer.echo("LLMWiki Configuration")
    typer.echo("=====================")
    typer.echo(f"  Base directory:   {cfg.llmwiki_base_dir or '(current dir)'}")
    typer.echo(f"  Inbox directory:  {cfg.resolved_inbox_dir}")
    typer.echo(f"  Wiki directory:   {cfg.resolved_wiki_dir}")
    typer.echo(f"  Model:            {cfg.llmwiki_model}")
    typer.echo(f"  API Key:          {masked}")
    typer.echo(f"  API Endpoint:     {cfg.llmwiki_api_endpoint}")
    typer.echo(f"  Watch enabled:    {cfg.llmwiki_watch}")
    typer.echo(f"  OCR enabled:      {cfg.llmwiki_ocr_enabled}")


@app.command()
def status() -> None:
    """Show pipeline statistics.

    Reports the number of processed files (from the hash-tracking database)
    and the number of wiki pages in the output directory.
    """
    cfg = LLMWikiConfig()
    base = Path(cfg.llmwiki_base_dir) if cfg.llmwiki_base_dir else Path.cwd()
    hash_db_path = base / "data" / "hash.db"
    wiki_dir = cfg.resolved_wiki_dir

    typer.echo("Pipeline Status")
    typer.echo("===============")

    # -- Hash DB stats ------------------------------------------------------
    if hash_db_path.exists():
        try:
            conn = sqlite3.connect(str(hash_db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.execute("SELECT COUNT(*) FROM hashes")
            count = cursor.fetchone()[0]
            conn.close()
            typer.echo(f"  Processed files:  {count}")
        except sqlite3.DatabaseError:
            typer.echo("  Processed files:  (DB corrupted)")
    else:
        typer.echo("  Processed files:  0 (no hash DB yet)")

    # -- Wiki page count ----------------------------------------------------
    if wiki_dir.is_dir():
        pages = list(wiki_dir.glob("*.md"))
        typer.echo(f"  Wiki pages:       {len(pages)}")
    else:
        typer.echo("  Wiki pages:       0 (wiki directory does not exist)")


# ── Pre-flight helpers ───────────────────────────────────────────────────


def _warn_ocr_config(config: LLMWikiConfig) -> None:
    """Warn about missing OCR dependencies when OCR is enabled.

    Checks for:
    * ``docling`` availability (installed via ``llmwiki-ingest[pdf]``)
    * System ``tesseract`` binary availability
    """
    if not config.llmwiki_ocr_enabled:
        return

    try:
        import docling  # noqa: F401
    except ImportError:
        typer.echo(
            "Warning: OCR is enabled (LLMWIKI_OCR_ENABLED=true) but docling is "
            "not installed.\n"
            "  Install it with: pip install llmwiki-ingest[pdf]\n",
            err=True,
        )
        return

    # Check for system tesseract
    import shutil

    if shutil.which("tesseract") is None:
        typer.echo(
            "Warning: OCR is enabled (LLMWIKI_OCR_ENABLED=true) but Tesseract "
            "is not installed on this system.\n"
            "  Install it with your package manager, e.g.:\n"
            "    apt install tesseract-ocr          # Debian/Ubuntu\n"
            "    brew install tesseract              # macOS\n"
            "    choco install tesseract             # Windows\n",
            err=True,
        )


# ── Async helpers ────────────────────────────────────────────────────────


async def _run_ingest(config: LLMWikiConfig, file: Path) -> None:
    """Run the ingestion pipeline for a single file."""
    typer.echo(f"Ingesting: {file}")
    result = await run_pipeline(config, file)

    # -- Report results -------------------------------------------------
    if result.get("skipped"):
        typer.echo(f"⏭ Already processed — skipped (hash: {result.get('hash', '')[:12]})")
        return

    errors = result.get("errors", [])
    output_path = result.get("output_path", "")

    if output_path:
        typer.echo(f"✓ Wiki page written to: {output_path}")

    if errors:
        typer.echo("\nWarnings / Errors:")
        for err in errors:
            typer.echo(f"  ⚠ {err}")

    if output_path:
        typer.echo("\nDone — file ingested successfully.")
    else:
        if errors:
            typer.echo("\nPipeline completed with warnings.")
        else:
            typer.echo("\nPipeline completed (no output generated).")


# ── Entry point (also used from __main__.py) ────────────────────────────

if __name__ == "__main__":
    app()
