"""SQLite index for fast journal queries.

The markdown files remain the source of truth; SQLite provides fast
structured queries and aggregations.

Index location: journal/.index.db
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .models import JournalEntry, format_timestamp, parse_timestamp


class JournalIndex:
    """SQLite index for journal entries."""

    SCHEMA_VERSION = 1

    def __init__(self, journal_path: Path):
        """Initialize the journal index.

        Args:
            journal_path: Path to the journal directory
        """
        self.journal_path = journal_path
        self.db_path = journal_path / ".index.db"
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys and WAL mode for better concurrency
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    def _ensure_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        conn = self._get_connection()

        # Check schema version
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cursor.fetchone() is None:
            self._init_schema(conn)
        else:
            # Check if we need to migrate
            cursor = conn.execute("SELECT version FROM schema_version")
            row = cursor.fetchone()
            if row is None or row[0] < self.SCHEMA_VERSION:
                self._migrate_schema(conn, row[0] if row else 0)

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize the database schema."""
        conn.executescript("""
            -- Schema version tracking
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );
            INSERT INTO schema_version (version) VALUES (1);

            -- Main entries table
            CREATE TABLE IF NOT EXISTS entries (
                entry_id TEXT PRIMARY KEY,      -- 2026-01-17-001
                timestamp TEXT NOT NULL,        -- ISO 8601
                date TEXT NOT NULL,             -- YYYY-MM-DD (for fast date filtering)
                author TEXT NOT NULL,
                entry_type TEXT NOT NULL,       -- entry, amendment
                outcome TEXT,                   -- success, failure, partial

                -- Template
                template TEXT,

                -- Content fields (for full-text search)
                context TEXT,
                intent TEXT,
                action TEXT,
                observation TEXT,
                analysis TEXT,
                next_steps TEXT,

                -- Amendment fields
                references_entry TEXT,
                correction TEXT,
                actual TEXT,
                impact TEXT,

                -- Causality
                config_used TEXT,
                log_produced TEXT,
                caused_by TEXT,                 -- JSON array of entry IDs
                causes TEXT,                    -- JSON array of entry IDs

                -- References
                refs TEXT,                      -- JSON array of references

                -- Diagnostic fields (for mcp-cygwin integration)
                tool TEXT,                      -- bash, read_file, etc.
                duration_ms INTEGER,
                exit_code INTEGER,
                command TEXT,
                error_type TEXT,

                -- Metadata
                file_path TEXT NOT NULL         -- journal/2026-01-17.md
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_date ON entries(date);
            CREATE INDEX IF NOT EXISTS idx_author ON entries(author);
            CREATE INDEX IF NOT EXISTS idx_outcome ON entries(outcome);
            CREATE INDEX IF NOT EXISTS idx_tool ON entries(tool);
            CREATE INDEX IF NOT EXISTS idx_entry_type ON entries(entry_type);
            CREATE INDEX IF NOT EXISTS idx_template ON entries(template);

            -- Full-text search virtual table
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                entry_id,
                context,
                intent,
                action,
                observation,
                analysis,
                next_steps,
                correction,
                actual,
                impact,
                content='entries',
                content_rowid='rowid'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
                INSERT INTO entries_fts(rowid, entry_id, context, intent, action, observation, analysis, next_steps, correction, actual, impact)
                VALUES (new.rowid, new.entry_id, new.context, new.intent, new.action, new.observation, new.analysis, new.next_steps, new.correction, new.actual, new.impact);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, entry_id, context, intent, action, observation, analysis, next_steps, correction, actual, impact)
                VALUES ('delete', old.rowid, old.entry_id, old.context, old.intent, old.action, old.observation, old.analysis, old.next_steps, old.correction, old.actual, old.impact);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, entry_id, context, intent, action, observation, analysis, next_steps, correction, actual, impact)
                VALUES ('delete', old.rowid, old.entry_id, old.context, old.intent, old.action, old.observation, old.analysis, old.next_steps, old.correction, old.actual, old.impact);
                INSERT INTO entries_fts(rowid, entry_id, context, intent, action, observation, analysis, next_steps, correction, actual, impact)
                VALUES (new.rowid, new.entry_id, new.context, new.intent, new.action, new.observation, new.analysis, new.next_steps, new.correction, new.actual, new.impact);
            END;
        """)
        conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Migrate schema from an older version."""
        # Currently only version 1 exists, so no migrations needed
        if from_version < 1:
            self._init_schema(conn)

    def close(self) -> None:
        """Close the database connection.

        On Windows, we need to checkpoint WAL and switch to DELETE journal
        mode before closing to ensure all file handles are released.
        """
        if self._connection is not None:
            try:
                # Checkpoint WAL to merge it into main database
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                # Switch to DELETE mode to remove WAL files
                self._connection.execute("PRAGMA journal_mode = DELETE")
            except Exception:
                pass  # Ignore errors during cleanup
            self._connection.close()
            self._connection = None

    def index_entry(
        self,
        entry: JournalEntry,
        file_path: Path,
        diagnostic_fields: Optional[dict[str, Any]] = None,
    ) -> None:
        """Index a journal entry.

        Args:
            entry: The journal entry to index
            file_path: Path to the markdown file containing the entry
            diagnostic_fields: Optional diagnostic metadata (tool, duration_ms, etc.)
        """
        conn = self._get_connection()
        diag = diagnostic_fields or {}

        # Extract date from entry_id (YYYY-MM-DD-NNN)
        date_str = entry.entry_id[:10]

        conn.execute(
            """
            INSERT OR REPLACE INTO entries (
                entry_id, timestamp, date, author, entry_type, outcome,
                template, context, intent, action, observation, analysis, next_steps,
                references_entry, correction, actual, impact,
                config_used, log_produced, caused_by, causes, refs,
                tool, duration_ms, exit_code, command, error_type,
                file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.entry_id,
                format_timestamp(entry.timestamp),
                date_str,
                entry.author,
                entry.entry_type.value,
                entry.outcome,
                entry.template,
                entry.context,
                entry.intent,
                entry.action,
                entry.observation,
                entry.analysis,
                entry.next_steps,
                entry.references_entry,
                entry.correction,
                entry.actual,
                entry.impact,
                entry.config_used,
                entry.log_produced,
                json.dumps(entry.caused_by) if entry.caused_by else None,
                json.dumps(entry.causes) if entry.causes else None,
                json.dumps(entry.references) if entry.references else None,
                diag.get("tool"),
                diag.get("duration_ms"),
                diag.get("exit_code"),
                diag.get("command"),
                diag.get("error_type"),
                str(file_path),
            ),
        )
        conn.commit()

    def index_entry_from_dict(self, entry_dict: dict[str, Any], file_path: Path) -> None:
        """Index a journal entry from a dictionary representation.

        Args:
            entry_dict: Dictionary representation of the entry (from parsing markdown)
            file_path: Path to the markdown file
        """
        conn = self._get_connection()

        # Extract date from entry_id
        entry_id = entry_dict.get("entry_id", "")
        date_str = entry_id[:10] if len(entry_id) >= 10 else ""

        conn.execute(
            """
            INSERT OR REPLACE INTO entries (
                entry_id, timestamp, date, author, entry_type, outcome,
                template, context, intent, action, observation, analysis, next_steps,
                references_entry, correction, actual, impact,
                config_used, log_produced, caused_by, causes, refs,
                tool, duration_ms, exit_code, command, error_type,
                file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry_dict.get("timestamp"),
                date_str,
                entry_dict.get("author", ""),
                entry_dict.get("entry_type", "entry"),
                entry_dict.get("outcome"),
                entry_dict.get("template"),
                entry_dict.get("context"),
                entry_dict.get("intent"),
                entry_dict.get("action"),
                entry_dict.get("observation"),
                entry_dict.get("analysis"),
                entry_dict.get("next_steps"),
                entry_dict.get("amends") or entry_dict.get("references_entry"),
                entry_dict.get("correction"),
                entry_dict.get("actual"),
                entry_dict.get("impact"),
                entry_dict.get("config_used"),
                entry_dict.get("log_produced"),
                json.dumps(entry_dict.get("caused_by")) if entry_dict.get("caused_by") else None,
                json.dumps(entry_dict.get("causes")) if entry_dict.get("causes") else None,
                json.dumps(entry_dict.get("references")) if entry_dict.get("references") else None,
                entry_dict.get("tool"),
                entry_dict.get("duration_ms"),
                entry_dict.get("exit_code"),
                entry_dict.get("command"),
                entry_dict.get("error_type"),
                str(file_path),
            ),
        )
        conn.commit()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from the index.

        Args:
            entry_id: The entry ID to delete

        Returns:
            True if entry was deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_entry(self, entry_id: str) -> Optional[dict[str, Any]]:
        """Get a single entry by ID.

        Args:
            entry_id: The entry ID to retrieve

        Returns:
            Entry dictionary or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM entries WHERE entry_id = ?", (entry_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def query(
        self,
        filters: Optional[dict[str, Any]] = None,
        text_search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "timestamp",
        order_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """Query journal entries with filters.

        Args:
            filters: Dictionary of field=value filters
            text_search: Full-text search query
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum results to return
            offset: Number of results to skip
            order_by: Field to order by
            order_desc: True for descending order

        Returns:
            List of matching entry dictionaries
        """
        conn = self._get_connection()
        filters = filters or {}

        # Build the query
        conditions = []
        params: list[Any] = []

        # Add filter conditions
        for field, value in filters.items():
            if value is not None:
                # Sanitize field name to prevent injection
                if not re.match(r"^[a-z_]+$", field):
                    continue
                conditions.append(f"{field} = ?")
                params.append(value)

        # Add date range conditions
        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)

        # Handle full-text search
        if text_search:
            # Use FTS5 for text search
            conditions.append(
                "entry_id IN (SELECT entry_id FROM entries_fts WHERE entries_fts MATCH ?)"
            )
            # Escape special FTS5 characters
            escaped_search = self._escape_fts_query(text_search)
            params.append(escaped_search)

        # Build WHERE clause
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Validate order_by to prevent injection
        valid_order_fields = [
            "timestamp", "date", "author", "entry_type", "outcome", "tool", "entry_id"
        ]
        if order_by not in valid_order_fields:
            order_by = "timestamp"

        order_direction = "DESC" if order_desc else "ASC"

        query = f"""
            SELECT * FROM entries
            {where_clause}
            ORDER BY {order_by} {order_direction}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search_text(
        self,
        query: str,
        filters: Optional[dict[str, Any]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Full-text search across entry content.

        Args:
            query: Search query
            filters: Additional filters to apply
            date_from: Start date filter
            date_to: End date filter
            limit: Maximum results

        Returns:
            List of matching entries with relevance ranking
        """
        return self.query(
            filters=filters,
            text_search=query,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def aggregate(
        self,
        group_by: str,
        aggregations: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Aggregate statistics over entries.

        Args:
            group_by: Field to group by (e.g., "tool", "outcome", "author")
            aggregations: List of aggregation expressions (e.g., ["count", "avg:duration_ms"])
            filters: Additional filters
            date_from: Start date
            date_to: End date

        Returns:
            Dictionary with aggregation results
        """
        conn = self._get_connection()
        filters = filters or {}
        aggregations = aggregations or ["count"]

        # Validate group_by field
        valid_group_fields = ["tool", "outcome", "author", "entry_type", "date", "template"]
        if group_by not in valid_group_fields:
            raise ValueError(f"Invalid group_by field: {group_by}")

        # Build aggregation expressions
        agg_exprs = []
        agg_names = []
        for agg in aggregations:
            if agg == "count":
                agg_exprs.append("COUNT(*)")
                agg_names.append("count")
            elif ":" in agg:
                func, field = agg.split(":", 1)
                # Validate function and field
                if func not in ["avg", "sum", "min", "max"]:
                    continue
                if not re.match(r"^[a-z_]+$", field):
                    continue
                agg_exprs.append(f"{func.upper()}({field})")
                agg_names.append(f"{func}_{field}")

        if not agg_exprs:
            agg_exprs = ["COUNT(*)"]
            agg_names = ["count"]

        # Build conditions
        conditions = []
        params: list[Any] = []

        for field, value in filters.items():
            if value is not None and re.match(r"^[a-z_]+$", field):
                conditions.append(f"{field} = ?")
                params.append(value)

        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT {group_by}, {', '.join(agg_exprs)}
            FROM entries
            {where_clause}
            GROUP BY {group_by}
            ORDER BY {agg_exprs[0]} DESC
        """

        cursor = conn.execute(query, params)
        results = []
        for row in cursor.fetchall():
            result = {group_by: row[0]}
            for i, name in enumerate(agg_names):
                result[name] = row[i + 1]
            results.append(result)

        # Also compute totals
        total_query = f"""
            SELECT {', '.join(agg_exprs)}
            FROM entries
            {where_clause}
        """
        cursor = conn.execute(total_query, params)
        total_row = cursor.fetchone()
        totals = {}
        if total_row:
            for i, name in enumerate(agg_names):
                totals[name] = total_row[i]

        return {
            "group_by": group_by,
            "groups": results,
            "totals": totals,
        }

    def get_active_operations(
        self,
        threshold_ms: int = 30000,
        tool_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Find potentially active/hanging operations.

        This looks for entries with diagnostic fields indicating long-running
        or incomplete operations.

        Args:
            threshold_ms: Duration threshold in milliseconds
            tool_filter: Optional tool name filter

        Returns:
            List of entries that might be active/hanging
        """
        conn = self._get_connection()

        conditions = ["duration_ms > ?"]
        params: list[Any] = [threshold_ms]

        if tool_filter:
            conditions.append("tool = ?")
            params.append(tool_filter)

        # Also look for entries without an outcome (potentially incomplete)
        query = f"""
            SELECT * FROM entries
            WHERE ({" AND ".join(conditions)})
               OR (outcome IS NULL AND tool IS NOT NULL)
            ORDER BY timestamp DESC
            LIMIT 50
        """

        cursor = conn.execute(query, params)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def rebuild_from_markdown(
        self,
        parse_entry_func,
        progress_callback=None,
    ) -> dict[str, int]:
        """Rebuild the entire index from markdown files.

        Args:
            parse_entry_func: Function that parses a journal file and returns entries
            progress_callback: Optional callback(current, total, file_path) for progress

        Returns:
            Dictionary with rebuild statistics
        """
        conn = self._get_connection()

        # Clear existing entries
        conn.execute("DELETE FROM entries")
        conn.commit()

        # Find all journal files
        journal_files = sorted(self.journal_path.glob("*.md"))
        total_files = len(journal_files)
        total_entries = 0
        errors = 0

        for i, journal_file in enumerate(journal_files):
            if journal_file.name == "INDEX.md":
                continue

            if progress_callback:
                progress_callback(i + 1, total_files, journal_file)

            try:
                content = journal_file.read_text(encoding="utf-8")
                entries = parse_entry_func(content, journal_file)

                for entry in entries:
                    self.index_entry_from_dict(entry, journal_file)
                    total_entries += 1

            except Exception as e:
                errors += 1
                # Continue processing other files

        return {
            "files_processed": total_files,
            "entries_indexed": total_entries,
            "errors": errors,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with index statistics
        """
        conn = self._get_connection()

        stats = {}

        # Total entries
        cursor = conn.execute("SELECT COUNT(*) FROM entries")
        stats["total_entries"] = cursor.fetchone()[0]

        # Entries by type
        cursor = conn.execute(
            "SELECT entry_type, COUNT(*) FROM entries GROUP BY entry_type"
        )
        stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Entries by outcome
        cursor = conn.execute(
            "SELECT outcome, COUNT(*) FROM entries WHERE outcome IS NOT NULL GROUP BY outcome"
        )
        stats["by_outcome"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Date range
        cursor = conn.execute("SELECT MIN(date), MAX(date) FROM entries")
        row = cursor.fetchone()
        stats["date_range"] = {"min": row[0], "max": row[1]}

        # Top authors
        cursor = conn.execute(
            "SELECT author, COUNT(*) FROM entries GROUP BY author ORDER BY COUNT(*) DESC LIMIT 10"
        )
        stats["top_authors"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Top tools (if any)
        cursor = conn.execute(
            "SELECT tool, COUNT(*) FROM entries WHERE tool IS NOT NULL GROUP BY tool ORDER BY COUNT(*) DESC LIMIT 10"
        )
        stats["top_tools"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = dict(row)

        # Parse JSON fields
        for field in ["caused_by", "causes", "refs"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = []
            else:
                result[field] = []

        # Rename refs back to references
        if "refs" in result:
            result["references"] = result.pop("refs")

        return result

    def _escape_fts_query(self, query: str) -> str:
        """Escape special characters in FTS5 query.

        FTS5 uses double quotes for phrase matching, so we escape them.
        """
        # Remove special FTS5 operators for simple search
        # Users can use advanced syntax if they know what they're doing
        escaped = query.replace('"', '""')
        # Wrap in quotes for exact phrase matching if it contains spaces
        if " " in query and not any(c in query for c in ["AND", "OR", "NOT", "*"]):
            return f'"{escaped}"'
        return escaped
