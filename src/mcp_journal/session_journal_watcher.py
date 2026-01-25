"""Session Journal Watcher - Background indexer and hang detector.

Monitors ~/.claude/session-journal/*.jsonl files, indexes them to SQLite,
and detects hung tool calls (tool_start without matching tool_end).

This module provides:
1. SessionJournalIndex - SQLite index for fast queries
2. SessionJournalWatcher - Background thread that monitors and indexes JSONL files
3. Hang detection - Identifies orphaned tool_start entries after timeout + grace period
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Default configuration
DEFAULT_JOURNAL_DIR = Path.home() / ".claude" / "session-journal"
DEFAULT_POLL_INTERVAL = 5.0  # seconds
DEFAULT_HANG_TIMEOUT = 120  # seconds (matches mcp-cygwin default)
DEFAULT_HANG_GRACE = 30  # additional seconds before declaring hang


def get_session_journal_dir() -> Path:
    """Get session journal directory.

    Uses ~/.claude/session-journal/ by default.
    Can be overridden with MCP_SESSION_JOURNAL_DIR environment variable.
    """
    custom_dir = os.environ.get("MCP_SESSION_JOURNAL_DIR")
    if custom_dir:
        return Path(custom_dir)
    return DEFAULT_JOURNAL_DIR


class SessionJournalIndex:
    """SQLite index for session journal entries."""

    SCHEMA_VERSION = 1

    def __init__(self, journal_dir: Optional[Path] = None):
        """Initialize the session journal index.

        Args:
            journal_dir: Path to session journal directory (default: ~/.claude/session-journal)
        """
        self.journal_dir = journal_dir or get_session_journal_dir()
        self.db_path = self.journal_dir / "index.sqlite"
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection (thread-safe)."""
        with self._lock:
            if self._connection is None:
                self.journal_dir.mkdir(parents=True, exist_ok=True)
                self._connection = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,  # We use our own lock
                )
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA journal_mode = WAL")
                self._ensure_schema()
            return self._connection

    def _ensure_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        conn = self._connection
        if conn is None:
            return

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cursor.fetchone() is None:
            self._init_schema(conn)

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize the database schema."""
        conn.executescript("""
            -- Schema version tracking
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );
            INSERT OR REPLACE INTO schema_version (version) VALUES (1);

            -- Session journal entries
            CREATE TABLE IF NOT EXISTS entries (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,              -- ISO 8601 timestamp
                src TEXT NOT NULL,             -- Source (mcp-cygwin, mcp-journal, etc.)
                ev TEXT NOT NULL,              -- Event type (tool_start, tool_end, etc.)
                id TEXT,                       -- Correlation ID for start/end pairing
                tool TEXT,                     -- Tool name
                args TEXT,                     -- JSON serialized args
                dur_ms INTEGER,                -- Duration in milliseconds
                exit_code INTEGER,             -- Exit code
                err TEXT,                      -- Error message
                daemon_id TEXT,                -- Daemon identifier
                pid INTEGER,                   -- Process ID
                cmd TEXT,                      -- Command string
                msg TEXT,                      -- Message for note/error events
                caused_by TEXT,                -- Causality reference
                file_path TEXT,                -- Source JSONL file
                line_num INTEGER,              -- Line number in file
                raw_json TEXT                  -- Original JSON for reference
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_ts ON entries(ts);
            CREATE INDEX IF NOT EXISTS idx_src ON entries(src);
            CREATE INDEX IF NOT EXISTS idx_ev ON entries(ev);
            CREATE INDEX IF NOT EXISTS idx_id ON entries(id);
            CREATE INDEX IF NOT EXISTS idx_tool ON entries(tool);

            -- Track which files have been indexed
            CREATE TABLE IF NOT EXISTS indexed_files (
                file_path TEXT PRIMARY KEY,
                last_line INTEGER NOT NULL,    -- Last line number indexed
                last_modified REAL NOT NULL,   -- File mtime when last indexed
                indexed_at TEXT NOT NULL       -- When we indexed it
            );

            -- Track pending tool_start entries (for hang detection)
            CREATE TABLE IF NOT EXISTS pending_starts (
                id TEXT PRIMARY KEY,           -- Correlation ID
                ts TEXT NOT NULL,              -- Start timestamp
                src TEXT NOT NULL,             -- Source
                tool TEXT,                     -- Tool name
                timeout_at TEXT NOT NULL       -- When to consider it hung
            );
        """)
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def index_entry(self, entry: dict[str, Any], file_path: str, line_num: int) -> None:
        """Index a single JSONL entry.

        Args:
            entry: Parsed JSON entry
            file_path: Source file path
            line_num: Line number in file
        """
        conn = self._get_connection()
        with self._lock:
            conn.execute("""
                INSERT INTO entries (
                    ts, src, ev, id, tool, args, dur_ms, exit_code, err,
                    daemon_id, pid, cmd, msg, caused_by, file_path, line_num, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("ts"),
                entry.get("src"),
                entry.get("ev"),
                entry.get("id"),
                entry.get("tool"),
                json.dumps(entry.get("args")) if entry.get("args") else None,
                entry.get("dur_ms"),
                entry.get("exit"),
                entry.get("err"),
                entry.get("daemon_id"),
                entry.get("pid"),
                entry.get("cmd"),
                entry.get("msg"),
                entry.get("caused_by"),
                file_path,
                line_num,
                json.dumps(entry),
            ))
            conn.commit()

    def track_pending_start(
        self,
        entry: dict[str, Any],
        timeout_seconds: int = DEFAULT_HANG_TIMEOUT,
        grace_seconds: int = DEFAULT_HANG_GRACE,
    ) -> None:
        """Track a tool_start entry for hang detection.

        Args:
            entry: The tool_start entry
            timeout_seconds: Expected max duration
            grace_seconds: Extra time before declaring hang
        """
        correlation_id = entry.get("id")
        if not correlation_id:
            return

        ts = entry.get("ts", "")
        try:
            start_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            start_time = datetime.now(timezone.utc)

        timeout_at = start_time.timestamp() + timeout_seconds + grace_seconds
        timeout_at_iso = datetime.fromtimestamp(timeout_at, timezone.utc).isoformat()

        conn = self._get_connection()
        with self._lock:
            conn.execute("""
                INSERT OR REPLACE INTO pending_starts (id, ts, src, tool, timeout_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                correlation_id,
                ts,
                entry.get("src"),
                entry.get("tool"),
                timeout_at_iso,
            ))
            conn.commit()

    def clear_pending_start(self, correlation_id: str) -> bool:
        """Remove a pending start entry (when tool_end is received).

        Args:
            correlation_id: The correlation ID to clear

        Returns:
            True if entry was found and removed
        """
        conn = self._get_connection()
        with self._lock:
            cursor = conn.execute(
                "DELETE FROM pending_starts WHERE id = ?",
                (correlation_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_hung_operations(self) -> list[dict[str, Any]]:
        """Get operations that have exceeded their timeout.

        Returns:
            List of hung operation entries
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        with self._lock:
            cursor = conn.execute("""
                SELECT id, ts, src, tool, timeout_at
                FROM pending_starts
                WHERE timeout_at < ?
            """, (now_iso,))
            return [dict(row) for row in cursor.fetchall()]

    def remove_pending_start(self, correlation_id: str) -> None:
        """Remove a pending start after recording hang."""
        conn = self._get_connection()
        with self._lock:
            conn.execute("DELETE FROM pending_starts WHERE id = ?", (correlation_id,))
            conn.commit()

    def get_file_position(self, file_path: str) -> tuple[int, float]:
        """Get the last indexed position for a file.

        Args:
            file_path: Path to JSONL file

        Returns:
            Tuple of (last_line, last_mtime)
        """
        conn = self._get_connection()
        with self._lock:
            cursor = conn.execute(
                "SELECT last_line, last_modified FROM indexed_files WHERE file_path = ?",
                (file_path,)
            )
            row = cursor.fetchone()
            if row:
                return (row["last_line"], row["last_modified"])
            return (0, 0.0)

    def update_file_position(self, file_path: str, last_line: int, mtime: float) -> None:
        """Update the indexed position for a file.

        Args:
            file_path: Path to JSONL file
            last_line: Last line number indexed
            mtime: File modification time
        """
        conn = self._get_connection()
        with self._lock:
            conn.execute("""
                INSERT OR REPLACE INTO indexed_files (file_path, last_line, last_modified, indexed_at)
                VALUES (?, ?, ?, ?)
            """, (
                file_path,
                last_line,
                mtime,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

    def query(
        self,
        src: Optional[str] = None,
        ev: Optional[str] = None,
        tool: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query indexed entries.

        Args:
            src: Filter by source
            ev: Filter by event type
            tool: Filter by tool name
            since: Filter entries after this timestamp
            until: Filter entries before this timestamp
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching entries
        """
        conditions = []
        params: list[Any] = []

        if src:
            conditions.append("src = ?")
            params.append(src)
        if ev:
            conditions.append("ev = ?")
            params.append(ev)
        if tool:
            conditions.append("tool = ?")
            params.append(tool)
        if since:
            conditions.append("ts >= ?")
            params.append(since)
        if until:
            conditions.append("ts <= ?")
            params.append(until)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        with self._lock:
            cursor = conn.execute(f"""
                SELECT * FROM entries
                {where_clause}
                ORDER BY ts DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset])
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with statistics
        """
        conn = self._get_connection()
        with self._lock:
            stats: dict[str, Any] = {}

            cursor = conn.execute("SELECT COUNT(*) FROM entries")
            stats["total_entries"] = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT src, COUNT(*) FROM entries GROUP BY src ORDER BY COUNT(*) DESC"
            )
            stats["by_source"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                "SELECT ev, COUNT(*) FROM entries GROUP BY ev ORDER BY COUNT(*) DESC"
            )
            stats["by_event"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                "SELECT tool, COUNT(*) FROM entries WHERE tool IS NOT NULL GROUP BY tool ORDER BY COUNT(*) DESC LIMIT 10"
            )
            stats["top_tools"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT COUNT(*) FROM pending_starts")
            stats["pending_operations"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT MIN(ts), MAX(ts) FROM entries")
            row = cursor.fetchone()
            stats["time_range"] = {"min": row[0], "max": row[1]}

            return stats


class SessionJournalWatcher:
    """Background watcher that indexes JSONL files and detects hangs."""

    def __init__(
        self,
        journal_dir: Optional[Path] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        hang_timeout: int = DEFAULT_HANG_TIMEOUT,
        hang_grace: int = DEFAULT_HANG_GRACE,
        on_hang_detected: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        """Initialize the watcher.

        Args:
            journal_dir: Path to session journal directory
            poll_interval: How often to check for new entries (seconds)
            hang_timeout: Expected max tool duration (seconds)
            hang_grace: Extra time before declaring hang (seconds)
            on_hang_detected: Callback when hang is detected
        """
        self.journal_dir = journal_dir or get_session_journal_dir()
        self.poll_interval = poll_interval
        self.hang_timeout = hang_timeout
        self.hang_grace = hang_grace
        self.on_hang_detected = on_hang_detected

        self.index = SessionJournalIndex(self.journal_dir)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background watcher thread.

        Args:
            timeout: How long to wait for thread to stop
        """
        if not self._running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        self._running = False
        self.index.close()

    def _run(self) -> None:
        """Main watcher loop."""
        while not self._stop_event.is_set():
            try:
                self._poll_files()
                self._check_hangs()
            except Exception as e:
                # Log error but continue running
                import sys
                print(f"[SessionJournalWatcher] Error: {e}", file=sys.stderr)

            self._stop_event.wait(self.poll_interval)

    def _poll_files(self) -> None:
        """Scan JSONL files for new entries."""
        if not self.journal_dir.exists():
            return

        for jsonl_file in sorted(self.journal_dir.glob("*.jsonl")):
            self._index_file(jsonl_file)

    def _index_file(self, file_path: Path) -> None:
        """Index new entries from a JSONL file.

        Args:
            file_path: Path to JSONL file
        """
        file_str = str(file_path)

        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            return

        last_line, last_mtime = self.index.get_file_position(file_str)

        # Skip if file hasn't changed
        if mtime <= last_mtime:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    # Skip already indexed lines
                    if line_num <= last_line:
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        self._process_entry(entry, file_str, line_num)
                    except json.JSONDecodeError:
                        continue

            self.index.update_file_position(file_str, line_num, mtime)
        except OSError:
            pass

    def _process_entry(self, entry: dict[str, Any], file_path: str, line_num: int) -> None:
        """Process a single JSONL entry.

        Args:
            entry: Parsed JSON entry
            file_path: Source file path
            line_num: Line number in file
        """
        # Index the entry
        self.index.index_entry(entry, file_path, line_num)

        ev = entry.get("ev")
        correlation_id = entry.get("id")

        # Track tool_start for hang detection
        if ev == "tool_start" and correlation_id:
            self.index.track_pending_start(entry, self.hang_timeout, self.hang_grace)

        # Clear pending start when tool_end received
        elif ev == "tool_end" and correlation_id:
            self.index.clear_pending_start(correlation_id)

    def _check_hangs(self) -> None:
        """Check for and record hung operations."""
        hung_ops = self.index.get_hung_operations()

        for op in hung_ops:
            self._record_hang(op)
            self.index.remove_pending_start(op["id"])

    def _record_hang(self, op: dict[str, Any]) -> None:
        """Record a hang_detected event.

        Args:
            op: The hung operation info
        """
        hang_entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "src": "mcp-journal",
            "ev": "hang_detected",
            "id": op.get("id"),
            "tool": op.get("tool"),
            "original_src": op.get("src"),
            "started_at": op.get("ts"),
            "msg": f"Tool {op.get('tool')} started at {op.get('ts')} did not complete within timeout",
        }

        # Write to JSONL file
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.journal_dir / f"{today}.jsonl"

        try:
            self.journal_dir.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(hang_entry, separators=(",", ":")) + "\n")
        except OSError:
            pass

        # Call callback if provided
        if self.on_hang_detected:
            try:
                self.on_hang_detected(hang_entry)
            except Exception:
                pass


# Convenience function to write to session journal (like mcp-cygwin does)
def append_session_entry(src: str, ev: str, **fields) -> None:
    """Append an entry to the session journal.

    Args:
        src: Source identifier
        ev: Event type
        **fields: Additional fields
    """
    journal_dir = get_session_journal_dir()
    journal_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "src": src,
        "ev": ev,
    }
    for key, value in fields.items():
        if value is not None:
            entry[key] = value

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = journal_dir / f"{today}.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
