"""File system watcher using watchdog.

Monitors a configurable inbox directory and triggers the ingestion pipeline
when new files are closed after writing (``IN_CLOSE_WRITE``).

Events are debounced (5-second cooldown per file) and temp/swap files
(``.swp``, ``.swo``, ``~`` suffix, files starting with ``.``, ``.tmp``)
are silently ignored.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from llmwiki.config import LLMWikiConfig
from llmwiki.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# ── Temp-file patterns ──────────────────────────────────────────────
_TEMP_SUFFIXES: frozenset[str] = frozenset({".swp", ".swo", "~", ".tmp"})

_DEBOUNCE_SECONDS: float = 5.0


class WikiIngestHandler(FileSystemEventHandler):
    """Watchdog event handler that triggers the ingestion pipeline.

    Args:
        config: Application configuration (used to build pipelines).
    """

    def __init__(self, config: LLMWikiConfig) -> None:
        super().__init__()
        self.config = config
        # src_path → last event timestamp (monotonic clock)
        self._debounce_timer: dict[str, float] = {}

    # ── Event handlers ──────────────────────────────────────────────

    def on_closed(self, event: object) -> None:
        """Called when a file is closed after being written.

        The *event* parameter is a ``watchdog.events.FileClosedEvent``
        (or a subclass thereof).  We ignore directory events, temp files,
        and rapid repeats of the same path.
        """
        # Duck-type check — watchdog may use different event types
        # across platforms.  Any object with src_path + is_directory works.
        src_path: str = getattr(event, "src_path", "")
        is_directory: bool = getattr(event, "is_directory", False)

        if not src_path or is_directory:
            return
        if self._is_temp_file(src_path):
            return

        # Debounce
        now = time.monotonic()
        last = self._debounce_timer.get(src_path, 0.0)
        if now - last < _DEBOUNCE_SECONDS:
            logger.debug("Debounced %s (%.1fs since last event)", src_path, now - last)
            return
        self._debounce_timer[src_path] = now

        logger.info("New file detected: %s", src_path)

        # Run the pipeline in a fresh event loop (this handler runs on a
        # watchdog thread, not the main thread).
        try:
            asyncio.run(self._process(src_path))
        except Exception as exc:
            logger.exception("Pipeline failed for %s: %s", src_path, exc)

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _is_temp_file(path: str) -> bool:
        """Return ``True`` if *path* looks like a temporary / swap file."""
        name = Path(path).name

        # Hidden files (dotfiles)
        if name.startswith("."):
            return True

        # Known temp suffixes
        if any(name.endswith(suffix) for suffix in _TEMP_SUFFIXES):
            return True

        return False

    async def _process(self, src_path: str) -> None:
        """Run the ingestion pipeline for a single file."""
        from typer import echo  # lazy import — avoids circular import at module level

        result = await run_pipeline(self.config, Path(src_path))

        if result.get("skipped"):
            echo(f"  ⏭ Already processed — skipped ({Path(src_path).name})")
        elif result.get("output_path"):
            errors = result.get("errors", [])
            echo(f"  ✓ {Path(src_path).name} → {result['output_path']}")
            if errors:
                for err in errors:
                    echo(f"    ⚠ {err}")
        else:
            errors = result.get("errors", [])
            echo(f"  ✗ Failed to process {Path(src_path).name}")
            for err in errors:
                echo(f"    ✗ {err}")


class FileWatcherService:
    """Manages a watchdog observer that monitors a directory.

    Args:
        config: Application configuration.
        directory: Absolute path to the directory to watch.  Must exist.
    """

    def __init__(self, config: LLMWikiConfig, directory: Path) -> None:
        self.config = config
        self.directory = directory.resolve()
        self._observer: Observer | PollingObserver | None = None

    def start(self) -> None:
        """Start the watchdog observer.

        Attempts to use the native ``Observer`` (inotify on Linux).
        Falls back to ``PollingObserver`` if inotify is unavailable
        (e.g. on NFS, FUSE, or non-Linux platforms).
        """
        handler = WikiIngestHandler(self.config)

        try:
            self._observer = Observer()
            self._observer.schedule(handler, str(self.directory), recursive=False)
            self._observer.start()
            logger.info("Watching %s (native observer)", self.directory)
        except OSError:
            logger.warning(
                "inotify not available for %s — falling back to PollingObserver",
                self.directory,
            )
            self._observer = PollingObserver()
            self._observer.schedule(handler, str(self.directory), recursive=False)
            self._observer.start()
            logger.info("Watching %s (polling observer)", self.directory)

    def stop(self) -> None:
        """Stop the watchdog observer and wait for it to join."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=10)
            self._observer = None
            logger.info("Watcher stopped")
