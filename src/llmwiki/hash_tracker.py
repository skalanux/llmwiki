"""Hash-based deduplication tracker.

Uses SQLite to store BLAKE2b digests of processed files so the pipeline
can skip files that have already been ingested.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HashTracker:
    """Tracks processed file hashes to avoid re-processing.

    Stores hashes in a local SQLite database with WAL journal mode for
    concurrent-read safety.

    If the database file is corrupted on open, it backs up the corrupted
    file (suffixed ``.corrupted``) and creates a fresh database.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._connect()

    # ── Public API ────────────────────────────────────────────────────

    def is_duplicate(self, file_hash: str) -> bool:
        """Return ``True`` if *file_hash* has already been recorded."""
        cursor = self._conn.execute(
            "SELECT 1 FROM hashes WHERE hash = ?", (file_hash,)
        )
        return cursor.fetchone() is not None

    def record(self, file_hash: str, file_path: str, file_size: int = 0) -> None:
        """Record *file_hash* as processed for the given *file_path*.

        Uses ``INSERT OR IGNORE`` so duplicates are silently ignored.
        The *file_size* (in bytes) is stored for audit purposes.
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO hashes (hash, file_path, size, processed_at) "
            "VALUES (?, ?, ?, ?)",
            (file_hash, file_path, file_size, datetime.now().isoformat()),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Internal ──────────────────────────────────────────────────────

    def _connect(self) -> None:
        """Open (or create) the SQLite database and initialise the schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._init_db()
        except sqlite3.DatabaseError:
            logger.warning(
                "Corrupted hash DB at %s — backing up and recreating",
                self.db_path,
            )
            self._recover()

    def _init_db(self) -> None:
        """Create the ``hashes`` table if it does not exist.

        Schema includes ``hash`` (BLAKE2b hex digest), ``file_path``,
        ``size`` (file size in bytes), and ``processed_at`` (ISO-8601
        timestamp).  Existing databases missing the ``size`` column are
        migrated via ``ALTER TABLE``.
        """
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS hashes ("
            "  hash TEXT PRIMARY KEY,"
            "  file_path TEXT NOT NULL,"
            "  size INTEGER DEFAULT 0,"
            "  processed_at TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

        # Migration: add size column if the table was created before P2
        try:
            self._conn.execute("ALTER TABLE hashes ADD COLUMN size INTEGER DEFAULT 0")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists — nothing to do

    def _recover(self) -> None:
        """Back up the corrupted DB file and create a fresh database."""
        backup = self.db_path.with_name(self.db_path.name + ".corrupted")
        if self.db_path.exists():
            shutil.copy2(str(self.db_path), str(backup))
            logger.info("Corrupted DB backed up to %s", backup)
        self.db_path.unlink(missing_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()
