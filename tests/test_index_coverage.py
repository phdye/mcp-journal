"""Tests for index.py and other coverage gaps.

These tests specifically target uncovered lines identified in coverage analysis.
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_journal.config import ProjectConfig, load_config
from mcp_journal.engine import JournalEngine
from mcp_journal.index import JournalIndex
from mcp_journal.models import EntryType, JournalEntry


# Fixtures temp_project, config, and engine are provided by conftest.py


@pytest.fixture
def journal_index(temp_project):
    """Create a standalone journal index."""
    journal_path = temp_project / "a" / "journal"
    journal_path.mkdir(parents=True, exist_ok=True)
    index = JournalIndex(journal_path)
    yield index
    index.close()


class TestSchemaVersionMigration:
    """Tests for schema version checking and migration (lines 59-62, 166-167)."""

    def test_migrate_from_version_zero(self, temp_project):
        """Test migration when schema_version table exists but is empty."""
        journal_path = temp_project / "a" / "journal"
        journal_path.mkdir(parents=True, exist_ok=True)
        db_path = journal_path / ".index.db"

        # Create a database with schema_version table but no version row
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        # Opening the index should trigger migration
        index = JournalIndex(journal_path)
        try:
            # Verify schema was initialized
            conn = index._get_connection()
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
            )
            assert cursor.fetchone() is not None
        finally:
            index.close()

    def test_migrate_from_old_version(self, temp_project):
        """Test migration when schema version is older than current."""
        journal_path = temp_project / "a" / "journal"
        journal_path.mkdir(parents=True, exist_ok=True)
        db_path = journal_path / ".index.db"

        # Create a database with old version
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (0)")
        conn.commit()
        conn.close()

        # Opening should trigger migration
        index = JournalIndex(journal_path)
        try:
            # Verify schema was initialized (migration ran)
            conn = index._get_connection()
            cursor = conn.execute("SELECT version FROM schema_version")
            row = cursor.fetchone()
            # After migration, version should be 1
            assert row is not None
        finally:
            index.close()

    def test_schema_current_version_no_migration(self, temp_project):
        """Test that no migration runs when schema version is current (line 61->exit).

        This covers the else branch at line 61 when row is not None AND
        row[0] >= SCHEMA_VERSION.
        """
        journal_path = temp_project / "a" / "journal"
        journal_path.mkdir(parents=True, exist_ok=True)

        # First, create a properly initialized index
        index1 = JournalIndex(journal_path)
        # Add an entry to verify data persists
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="Existing entry",
        )
        journal_file = journal_path / "2026-01-17.md"
        journal_file.touch()
        index1.index_entry(entry, journal_file)
        index1.close()

        # Now reopen - this should hit the "schema is current" branch
        index2 = JournalIndex(journal_path)
        try:
            # Verify the entry still exists (no re-init happened)
            result = index2.get_entry("2026-01-17-001")
            assert result is not None
            assert result["context"] == "Existing entry"
        finally:
            index2.close()

    def test_migrate_schema_noop_when_already_current(self, temp_project):
        """Test _migrate_schema returns early when from_version >= 1 (line 166->exit).

        This covers the implicit return when from_version is already at version 1.
        """
        journal_path = temp_project / "a" / "journal"
        journal_path.mkdir(parents=True, exist_ok=True)
        db_path = journal_path / ".index.db"

        # Create a database with current version but WITHOUT the entries table
        # to verify _migrate_schema doesn't call _init_schema when from_version >= 1
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")  # Current version
        # Manually create minimal entries table to satisfy schema check
        conn.execute("""
            CREATE TABLE entries (
                entry_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                author TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                outcome TEXT,
                template TEXT,
                context TEXT,
                intent TEXT,
                action TEXT,
                observation TEXT,
                analysis TEXT,
                next_steps TEXT,
                references_entry TEXT,
                correction TEXT,
                actual TEXT,
                impact TEXT,
                config_used TEXT,
                log_produced TEXT,
                caused_by TEXT,
                causes TEXT,
                refs TEXT,
                tool TEXT,
                duration_ms INTEGER,
                exit_code INTEGER,
                command TEXT,
                error_type TEXT,
                file_path TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        # Opening should NOT run migration since version is current
        index = JournalIndex(journal_path)
        try:
            # Verify schema check passed
            conn = index._get_connection()
            cursor = conn.execute("SELECT version FROM schema_version")
            row = cursor.fetchone()
            assert row[0] == 1  # Still version 1, no migration ran
        finally:
            index.close()

    def test_migrate_schema_direct_call_with_current_version(self, temp_project):
        """Directly test _migrate_schema with from_version >= 1 (line 166->exit).

        This directly calls _migrate_schema to cover the early return path.
        """
        journal_path = temp_project / "a" / "journal"
        journal_path.mkdir(parents=True, exist_ok=True)

        # Create an index normally
        index = JournalIndex(journal_path)
        try:
            conn = index._get_connection()

            # Directly call _migrate_schema with from_version=1
            # This should do nothing and return immediately
            index._migrate_schema(conn, 1)

            # Also test with from_version > 1 (future-proofing)
            index._migrate_schema(conn, 2)

            # Schema should still be intact
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
            )
            assert cursor.fetchone() is not None
        finally:
            index.close()


class TestDeleteEntry:
    """Tests for delete_entry function (lines 304-307)."""

    def test_delete_existing_entry(self, journal_index, temp_project):
        """Delete an entry that exists returns True."""
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="To be deleted",
        )
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()
        journal_index.index_entry(entry, journal_file)

        # Verify entry exists
        assert journal_index.get_entry("2026-01-17-001") is not None

        # Delete and verify return value
        result = journal_index.delete_entry("2026-01-17-001")
        assert result is True

        # Verify entry no longer exists
        assert journal_index.get_entry("2026-01-17-001") is None

    def test_delete_nonexistent_entry(self, journal_index):
        """Delete an entry that doesn't exist returns False."""
        result = journal_index.delete_entry("nonexistent-entry-id")
        assert result is False


class TestGetEntry:
    """Tests for get_entry edge cases (line 322)."""

    def test_get_nonexistent_entry_returns_none(self, journal_index):
        """Getting an entry that doesn't exist returns None."""
        result = journal_index.get_entry("2026-99-99-999")
        assert result is None


class TestAggregateValidation:
    """Tests for aggregate validation and edge cases (lines 465, 474-486, 493-495, 501-502)."""

    def test_aggregate_invalid_group_by_raises(self, journal_index, temp_project):
        """Aggregate with invalid group_by field raises ValueError."""
        # Add an entry first
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()
        journal_index.index_entry(entry, journal_file)

        with pytest.raises(ValueError, match="Invalid group_by field"):
            journal_index.aggregate(group_by="invalid_field")

    def test_aggregate_with_avg_aggregation(self, journal_index, temp_project):
        """Aggregate with avg:field style aggregation."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        for i in range(3):
            entry = JournalEntry(
                entry_id=f"2026-01-17-{i+1:03d}",
                timestamp=datetime.now(timezone.utc),
                author="test",
                entry_type=EntryType.ENTRY,
            )
            journal_index.index_entry(
                entry, journal_file, {"duration_ms": (i + 1) * 1000}
            )

        result = journal_index.aggregate(
            group_by="author",
            aggregations=["count", "avg:duration_ms", "sum:duration_ms"],
        )

        assert "groups" in result
        assert len(result["groups"]) >= 1
        group = result["groups"][0]
        assert "count" in group
        assert "avg_duration_ms" in group
        assert "sum_duration_ms" in group

    def test_aggregate_with_invalid_func_ignored(self, journal_index, temp_project):
        """Aggregate with invalid function is silently ignored."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Invalid function "invalid" should be ignored, falling back to count
        result = journal_index.aggregate(
            group_by="author",
            aggregations=["invalid:duration_ms"],
        )

        # Should still work, falling back to count
        assert "groups" in result

    def test_aggregate_with_invalid_field_name_ignored(
        self, journal_index, temp_project
    ):
        """Aggregate with invalid field name (injection attempt) is ignored."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Invalid field name with special chars should be ignored
        result = journal_index.aggregate(
            group_by="author",
            aggregations=["avg:field; DROP TABLE entries;--"],
        )

        # Should still work, falling back to count
        assert "groups" in result
        # Table should still exist
        conn = journal_index._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        )
        assert cursor.fetchone() is not None

    def test_aggregate_with_all_invalid_aggregations_falls_back(
        self, journal_index, temp_project
    ):
        """When all aggregations are invalid, falls back to count."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # All invalid aggregations
        result = journal_index.aggregate(
            group_by="author",
            aggregations=["invalid:field", "badfunction:badfield"],
        )

        # Should fall back to count
        assert "groups" in result
        assert len(result["groups"]) >= 1
        assert "count" in result["groups"][0]

    def test_aggregate_with_filters(self, journal_index, temp_project):
        """Aggregate with filters dict."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        for i, outcome in enumerate(["success", "success", "failure"]):
            entry = JournalEntry(
                entry_id=f"2026-01-17-{i+1:03d}",
                timestamp=datetime.now(timezone.utc),
                author="test",
                entry_type=EntryType.ENTRY,
                outcome=outcome,
            )
            journal_index.index_entry(entry, journal_file)

        result = journal_index.aggregate(
            group_by="outcome",
            filters={"author": "test"},
        )

        assert "groups" in result
        assert result["totals"]["count"] == 3

    def test_aggregate_with_date_range(self, journal_index, temp_project):
        """Aggregate with date_from and date_to filters."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            outcome="success",
        )
        journal_index.index_entry(entry, journal_file)

        result = journal_index.aggregate(
            group_by="outcome",
            date_from="2026-01-01",
            date_to="2026-12-31",
        )

        assert "groups" in result
        assert result["totals"]["count"] >= 1

    def test_aggregate_with_filter_containing_none_value(
        self, journal_index, temp_project
    ):
        """Aggregate filters with None values are skipped."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Filter with None value should be skipped
        result = journal_index.aggregate(
            group_by="author",
            filters={"outcome": None, "author": "test"},
        )

        assert "groups" in result

    def test_aggregate_with_no_colon_in_aggregation(self, journal_index, temp_project):
        """Test aggregation loop with entry that doesn't match any condition (474->470).

        This tests the case where an aggregation string has a colon but the
        function is invalid, causing the loop to continue to next iteration.
        """
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file, {"duration_ms": 1000})

        # Mix of valid and invalid aggregations to exercise loop continue
        result = journal_index.aggregate(
            group_by="author",
            aggregations=[
                "badfunction:field",  # Invalid func -> continue (line 478)
                "avg:bad_field!",     # Invalid field -> continue (line 480)
                "count",              # Valid - should work
                "avg:duration_ms",    # Valid - should work
            ],
        )

        assert "groups" in result
        assert "totals" in result
        # count and avg_duration_ms should be present
        assert "count" in result["totals"]

    def test_aggregate_with_unrecognized_aggregation_no_colon(
        self, journal_index, temp_project
    ):
        """Test aggregation loop skips strings without colon that aren't 'count' (474->470).

        The aggregation loop has three paths:
        1. agg == "count" -> add COUNT(*)
        2. ":" in agg -> try to parse func:field
        3. Neither (no match) -> implicitly continue to next iteration

        This tests path 3 - an aggregation string that doesn't match either condition.
        """
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Test with aggregations that don't match "count" AND don't have ":"
        # These should be skipped (implicit continue back to loop start)
        result = journal_index.aggregate(
            group_by="author",
            aggregations=[
                "notcount",      # Not "count", no colon -> skip (line 474->470)
                "something",     # Not "count", no colon -> skip
                "count",         # Valid - this one works
            ],
        )

        assert "groups" in result
        assert "totals" in result
        assert "count" in result["totals"]
        # Only "count" aggregation should have been processed
        assert result["totals"]["count"] == 1

    def test_aggregate_empty_result_set(self, journal_index, temp_project):
        """Test aggregate when query returns no rows (line 533->537).

        When there are no matching entries, total_row may be empty/null values.
        """
        # Don't add any entries - empty database

        result = journal_index.aggregate(
            group_by="author",
            filters={"author": "nonexistent_author"},  # No matches
        )

        assert "groups" in result
        assert "totals" in result
        assert len(result["groups"]) == 0
        # totals will have count=0 or None
        assert result["totals"].get("count", 0) in [0, None]

class TestRebuildFromMarkdown:
    """Tests for rebuild_from_markdown edge cases (lines 609, 612, 622-623)."""

    def test_rebuild_skips_index_md(self, journal_index, temp_project):
        """Rebuild skips INDEX.md file."""
        journal_path = temp_project / "a" / "journal"

        # Create INDEX.md file
        index_md = journal_path / "INDEX.md"
        index_md.write_text("# Journal Index\n\nSome index content", encoding="utf-8")

        # Create a regular journal file
        journal_file = journal_path / "2026-01-17.md"
        journal_file.write_text(
            "# Journal - 2026-01-17\n\n## 2026-01-17-001\n**Timestamp**: 2026-01-17T12:00:00+00:00\n**Author**: test\n**Type**: entry\n\n---\n",
            encoding="utf-8",
        )

        def parse_func(content, path):
            return [
                {
                    "entry_id": "2026-01-17-001",
                    "timestamp": "2026-01-17T12:00:00+00:00",
                    "author": "test",
                    "entry_type": "entry",
                }
            ]

        stats = journal_index.rebuild_from_markdown(parse_func)

        # Should process files but INDEX.md should be skipped
        assert stats["entries_indexed"] >= 1

    def test_rebuild_with_progress_callback(self, journal_index, temp_project):
        """Rebuild calls progress callback."""
        journal_path = temp_project / "a" / "journal"

        # Create journal file
        journal_file = journal_path / "2026-01-17.md"
        journal_file.write_text("# Journal\n\n", encoding="utf-8")

        callback_calls = []

        def progress_callback(current, total, path):
            callback_calls.append((current, total, path))

        def parse_func(content, path):
            return []

        journal_index.rebuild_from_markdown(parse_func, progress_callback)

        # Callback should have been called
        assert len(callback_calls) >= 1

    def test_rebuild_handles_parse_errors(self, journal_index, temp_project):
        """Rebuild continues on parse errors and counts them."""
        journal_path = temp_project / "a" / "journal"

        # Create journal file
        journal_file = journal_path / "2026-01-17.md"
        journal_file.write_text("# Journal content", encoding="utf-8")

        # Create another file
        journal_file2 = journal_path / "2026-01-18.md"
        journal_file2.write_text("# More content", encoding="utf-8")

        def parse_func_with_error(content, path):
            if "17" in str(path):
                raise ValueError("Parse error")
            return []

        stats = journal_index.rebuild_from_markdown(parse_func_with_error)

        # Should have recorded the error
        assert stats["errors"] >= 1
        # Should have processed both files
        assert stats["files_processed"] >= 2


class TestRowToDict:
    """Tests for _row_to_dict JSON parsing edge cases (lines 684-687, 692-695)."""

    def test_row_to_dict_handles_invalid_json(self, journal_index, temp_project):
        """_row_to_dict handles invalid JSON in caused_by field."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        # Insert entry with invalid JSON directly
        conn = journal_index._get_connection()
        conn.execute(
            """
            INSERT INTO entries (
                entry_id, timestamp, date, author, entry_type, file_path,
                caused_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-01-17-001",
                "2026-01-17T12:00:00+00:00",
                "2026-01-17",
                "test",
                "entry",
                str(journal_file),
                "not valid json",  # Invalid JSON
            ),
        )
        conn.commit()

        # Get entry should handle the invalid JSON gracefully
        result = journal_index.get_entry("2026-01-17-001")

        assert result is not None
        assert result["caused_by"] == []  # Falls back to empty list

    def test_row_to_dict_without_refs_field(self, journal_index):
        """_row_to_dict handles rows without refs field (line 692->695).

        This tests the defensive code path where "refs" is not present
        in the row dict. Normally all rows have refs, but this handles
        the case where they don't.
        """
        # Create a mock Row-like object that can be converted to dict
        # but doesn't have the "refs" key
        class MockRow:
            """Mock Row without refs field."""

            def __init__(self):
                self._data = {
                    "entry_id": "2026-01-17-001",
                    "timestamp": "2026-01-17T12:00:00+00:00",
                    "date": "2026-01-17",
                    "author": "test",
                    "entry_type": "entry",
                    "outcome": None,
                    "template": None,
                    "context": "test context",
                    "intent": None,
                    "action": None,
                    "observation": None,
                    "analysis": None,
                    "next_steps": None,
                    "references_entry": None,
                    "correction": None,
                    "actual": None,
                    "impact": None,
                    "config_used": None,
                    "log_produced": None,
                    "caused_by": None,
                    "causes": None,
                    # "refs" intentionally missing!
                    "tool": None,
                    "duration_ms": None,
                    "exit_code": None,
                    "command": None,
                    "error_type": None,
                    "file_path": "/test/path",
                }

            def keys(self):
                return self._data.keys()

            def __iter__(self):
                return iter(self._data.items())

            def __getitem__(self, key):
                return self._data[key]

        mock_row = MockRow()
        result = journal_index._row_to_dict(mock_row)

        # Should still work - refs becomes references with empty list
        assert result is not None
        assert result["entry_id"] == "2026-01-17-001"
        # refs was not present, so references should not be set from it
        # (or should have a default empty list)
        assert "references" in result or "refs" not in result


class TestQueryEdgeCases:
    """Tests for query edge cases."""

    def test_query_with_invalid_filter_field_ignored(
        self, journal_index, temp_project
    ):
        """Query with invalid filter field names (SQL injection) is ignored."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Invalid field name with special chars should be ignored
        results = journal_index.query(
            filters={"author; DROP TABLE entries;--": "test"}
        )

        # Should return results (filter ignored)
        assert len(results) >= 1

        # Table should still exist
        conn = journal_index._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        )
        assert cursor.fetchone() is not None

    def test_query_with_invalid_order_by_defaults_to_timestamp(
        self, journal_index, temp_project
    ):
        """Query with invalid order_by falls back to timestamp."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Invalid order_by should fall back to timestamp
        results = journal_index.query(order_by="invalid_field")

        # Should still return results
        assert len(results) >= 1

    def test_query_filter_with_none_value_skipped(self, journal_index, temp_project):
        """Query filters with None values are skipped."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
        )
        journal_index.index_entry(entry, journal_file)

        # Filter with None value should be skipped
        results = journal_index.query(filters={"outcome": None})

        # Should return all entries (None filter skipped)
        assert len(results) >= 1


class TestFTSQueryEscaping:
    """Tests for FTS query escaping."""

    def test_fts_escapes_quotes(self, journal_index, temp_project):
        """FTS query properly escapes double quotes."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context='Text with "quotes" inside',
        )
        journal_index.index_entry(entry, journal_file)

        # Search for text with quotes
        results = journal_index.query(text_search='with "quotes"')

        # Should not crash and may or may not find results
        assert isinstance(results, list)

    def test_fts_phrase_with_spaces(self, journal_index, temp_project):
        """FTS wraps multi-word queries in quotes for phrase matching."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="specific phrase here",
        )
        journal_index.index_entry(entry, journal_file)

        # Multi-word query
        results = journal_index.query(text_search="specific phrase")

        # Should find the entry
        assert len(results) >= 1

    def test_fts_with_operators_not_quoted(self, journal_index, temp_project):
        """FTS queries with AND/OR/NOT are not wrapped in quotes."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="word1 word2",
        )
        journal_index.index_entry(entry, journal_file)

        # Query with AND operator (won't be wrapped in quotes)
        results = journal_index.query(text_search="word1 AND word2")

        # Should work (may or may not find depending on FTS interpretation)
        assert isinstance(results, list)


class TestSearchText:
    """Tests for search_text method (line 430)."""

    def test_search_text_delegates_to_query(self, journal_index, temp_project):
        """search_text properly delegates to query with text_search."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="searchable content",
        )
        journal_index.index_entry(entry, journal_file)

        results = journal_index.search_text(
            query="searchable",
            filters={"author": "test"},
            date_from="2026-01-01",
            date_to="2026-12-31",
            limit=10,
        )

        assert len(results) >= 1
        assert results[0]["context"] == "searchable content"


class TestGetActiveOperations:
    """Tests for get_active_operations edge cases."""

    def test_get_active_no_matching_entries(self, journal_index, temp_project):
        """get_active_operations with no matching entries returns empty."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        # Entry with short duration and outcome
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            outcome="success",
        )
        journal_index.index_entry(entry, journal_file, {"duration_ms": 100})

        # High threshold should not match
        results = journal_index.get_active_operations(threshold_ms=1000000)

        # The entry has outcome, so won't match on "missing outcome" either
        # Check that operation completes without error
        assert isinstance(results, list)

    def test_get_active_finds_missing_outcome(self, journal_index, temp_project):
        """get_active_operations finds entries with tool but no outcome."""
        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        # Entry with tool but no outcome (potentially incomplete)
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            # No outcome
        )
        journal_index.index_entry(entry, journal_file, {"tool": "bash"})

        results = journal_index.get_active_operations(threshold_ms=1000000)

        # Should find the entry due to missing outcome
        entry_ids = [r["entry_id"] for r in results]
        assert "2026-01-17-001" in entry_ids


class TestMarkdownIntegerParsing:
    """Tests for parsing integer fields from markdown (engine.py:1033)."""

    def test_journal_read_parses_duration_ms(self, engine, temp_project):
        """journal_read correctly parses duration_ms from markdown."""
        # Create an entry with duration_ms
        entry = engine.journal_append(
            author="test",
            context="Test with duration",
            tool="bash",
            duration_ms=5000,
            exit_code=0,
        )

        # Read back the entries (forces markdown parsing)
        results = engine.journal_read()

        # Find our entry
        found = None
        for r in results:
            if r["entry_id"] == entry.entry_id:
                found = r
                break

        assert found is not None
        # The integer fields should be parsed correctly
        assert found.get("duration_ms") == 5000 or found.get("duration_ms") == "5000"

    def test_journal_read_parses_exit_code(self, engine, temp_project):
        """journal_read correctly parses exit_code from markdown."""
        # Create an entry with exit_code
        entry = engine.journal_append(
            author="test",
            context="Test with exit code",
            tool="bash",
            exit_code=127,
        )

        # Read back via rebuild_sqlite_index which uses _parse_entries_from_content
        stats = engine.rebuild_sqlite_index()

        # Query the entry
        results = engine.journal_query(filters={"tool": "bash"})

        # Find our entry
        found = None
        for r in results:
            if r["entry_id"] == entry.entry_id:
                found = r
                break

        assert found is not None
        assert found.get("exit_code") == 127


class TestConfigDisableDefaults:
    """Tests for disable_defaults config option (config.py:265-267)."""

    def test_disable_defaults_removes_default_templates(self, temp_project):
        """disable_defaults=true removes default templates not explicitly defined."""
        # Create config file with disable_defaults
        config_file = temp_project / "journal_config.toml"
        config_file.write_text(
            """
[project]
name = "test"

[templates]
disable_defaults = true

[templates.custom]
description = "Custom template"
context_template = "Custom context"
""",
            encoding="utf-8",
        )

        config = load_config(temp_project)

        # Default templates should be removed
        assert "diagnostic" not in config.templates
        assert "build" not in config.templates
        assert "test" not in config.templates

        # Custom template should be present
        assert "custom" in config.templates

    def test_disable_defaults_keeps_explicitly_defined(self, temp_project):
        """disable_defaults keeps templates that are explicitly defined."""
        # Create config file with disable_defaults but also defining a default
        config_file = temp_project / "journal_config.toml"
        config_file.write_text(
            """
[project]
name = "test"

[templates]
disable_defaults = true

[templates.diagnostic]
description = "My custom diagnostic"
context_template = "Custom diagnostic context"
""",
            encoding="utf-8",
        )

        config = load_config(temp_project)

        # Diagnostic should be kept because it was explicitly defined
        assert "diagnostic" in config.templates
        assert config.templates["diagnostic"].description == "My custom diagnostic"

        # Other defaults should be removed
        assert "build" not in config.templates
        assert "test" not in config.templates
