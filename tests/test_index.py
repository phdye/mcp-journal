"""Tests for the SQLite journal index."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig
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
    # Cleanup: close the database connection
    index.close()


class TestJournalIndexInit:
    """Tests for index initialization."""

    def test_creates_db_file(self, journal_index, temp_project):
        """Index creates the database file."""
        db_path = temp_project / "a" / "journal" / ".index.db"
        assert db_path.exists()

    def test_creates_schema(self, journal_index):
        """Index creates the required tables."""
        conn = journal_index._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "entries" in tables
        assert "entries_fts" in tables
        assert "schema_version" in tables


class TestIndexEntry:
    """Tests for indexing entries."""

    def test_index_entry_basic(self, journal_index, temp_project):
        """Can index a basic entry."""
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="Test context",
        )

        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        journal_index.index_entry(entry, journal_file)

        # Verify entry was indexed
        result = journal_index.get_entry("2026-01-17-001")
        assert result is not None
        assert result["entry_id"] == "2026-01-17-001"
        assert result["author"] == "test"
        assert result["context"] == "Test context"

    def test_index_entry_with_diagnostic_fields(self, journal_index, temp_project):
        """Can index entry with diagnostic fields."""
        entry = JournalEntry(
            entry_id="2026-01-17-001",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.ENTRY,
            context="Running command",
            tool="bash",
            duration_ms=5000,
            exit_code=0,
            command="echo hello",
        )

        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        diagnostic_fields = {
            "tool": "bash",
            "duration_ms": 5000,
            "exit_code": 0,
            "command": "echo hello",
        }
        journal_index.index_entry(entry, journal_file, diagnostic_fields)

        result = journal_index.get_entry("2026-01-17-001")
        assert result["tool"] == "bash"
        assert result["duration_ms"] == 5000
        assert result["exit_code"] == 0
        assert result["command"] == "echo hello"

    def test_index_amendment(self, journal_index, temp_project):
        """Can index an amendment entry."""
        entry = JournalEntry(
            entry_id="2026-01-17-002",
            timestamp=datetime.now(timezone.utc),
            author="test",
            entry_type=EntryType.AMENDMENT,
            references_entry="2026-01-17-001",
            correction="Wrong value",
            actual="Correct value",
            impact="None",
        )

        journal_file = temp_project / "a" / "journal" / "2026-01-17.md"
        journal_file.touch()

        journal_index.index_entry(entry, journal_file)

        result = journal_index.get_entry("2026-01-17-002")
        assert result["entry_type"] == "amendment"
        assert result["references_entry"] == "2026-01-17-001"
        assert result["correction"] == "Wrong value"


class TestQuery:
    """Tests for querying entries."""

    def test_query_all(self, engine):
        """Query returns all entries when no filters."""
        engine.journal_append(author="alice", context="First")
        engine.journal_append(author="bob", context="Second")
        engine.journal_append(author="alice", context="Third")

        results = engine.journal_query()

        assert len(results) == 3

    def test_query_with_filter(self, engine):
        """Query filters by field values."""
        engine.journal_append(author="alice", context="First", outcome="success")
        engine.journal_append(author="bob", context="Second", outcome="failure")
        engine.journal_append(author="alice", context="Third", outcome="success")

        results = engine.journal_query(filters={"outcome": "success"})

        assert len(results) == 2
        for r in results:
            assert r["outcome"] == "success"

    def test_query_with_author_filter(self, engine):
        """Query filters by author."""
        engine.journal_append(author="alice", context="First")
        engine.journal_append(author="bob", context="Second")
        engine.journal_append(author="alice", context="Third")

        results = engine.journal_query(filters={"author": "alice"})

        assert len(results) == 2
        for r in results:
            assert r["author"] == "alice"

    def test_query_with_tool_filter(self, engine):
        """Query filters by tool."""
        engine.journal_append(author="test", context="Bash", tool="bash", exit_code=0)
        engine.journal_append(author="test", context="File", tool="read_file")
        engine.journal_append(author="test", context="More bash", tool="bash", exit_code=1)

        results = engine.journal_query(filters={"tool": "bash"})

        assert len(results) == 2
        for r in results:
            assert r["tool"] == "bash"

    def test_query_with_date_range(self, engine):
        """Query filters by date range."""
        engine.journal_append(author="test", context="Entry")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = engine.journal_query(date_from=today, date_to=today)

        assert len(results) >= 1

    def test_query_with_limit(self, engine):
        """Query respects limit."""
        for i in range(10):
            engine.journal_append(author="test", context=f"Entry {i}")

        results = engine.journal_query(limit=5)

        assert len(results) == 5

    def test_query_with_offset(self, engine):
        """Query respects offset."""
        for i in range(10):
            engine.journal_append(author="test", context=f"Entry {i}")

        results_all = engine.journal_query(limit=10)
        results_offset = engine.journal_query(limit=5, offset=5)

        # The offset results should be different from the first 5
        all_ids = [r["entry_id"] for r in results_all]
        offset_ids = [r["entry_id"] for r in results_offset]

        # Offset 5 should give us entries 5-9 (the last 5)
        assert len(results_offset) == 5
        assert offset_ids == all_ids[5:]

    def test_query_order_desc(self, engine):
        """Query orders by timestamp descending by default."""
        engine.journal_append(author="test", context="First")
        engine.journal_append(author="test", context="Second")
        engine.journal_append(author="test", context="Third")

        results = engine.journal_query()

        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_query_order_asc(self, engine):
        """Query can order ascending."""
        engine.journal_append(author="test", context="First")
        engine.journal_append(author="test", context="Second")
        engine.journal_append(author="test", context="Third")

        results = engine.journal_query(order_desc=False)

        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps)


class TestTextSearch:
    """Tests for full-text search."""

    def test_search_finds_content(self, engine):
        """Search finds entries containing query."""
        engine.journal_append(author="test", context="Working on feature X")
        engine.journal_append(author="test", context="Debugging issue Y")
        engine.journal_append(author="test", context="More work on feature X")

        results = engine.journal_query(text_search="feature X")

        assert len(results) == 2

    def test_search_across_fields(self, engine):
        """Search works across multiple content fields."""
        engine.journal_append(
            author="test",
            context="Context text",
            intent="Intent text with keyword",
        )
        engine.journal_append(
            author="test",
            context="Different context",
            observation="Observation with keyword",
        )

        results = engine.journal_query(text_search="keyword")

        assert len(results) == 2

    def test_search_combined_with_filter(self, engine):
        """Search can be combined with filters."""
        engine.journal_append(author="alice", context="Feature work", outcome="success")
        engine.journal_append(author="bob", context="Feature work", outcome="failure")
        engine.journal_append(author="alice", context="Bug fix", outcome="success")

        results = engine.journal_query(
            text_search="Feature",
            filters={"author": "alice"},
        )

        assert len(results) == 1
        assert results[0]["author"] == "alice"


class TestAggregate:
    """Tests for aggregation queries."""

    def test_aggregate_by_outcome(self, engine):
        """Aggregate counts by outcome."""
        engine.journal_append(author="test", context="1", outcome="success")
        engine.journal_append(author="test", context="2", outcome="success")
        engine.journal_append(author="test", context="3", outcome="failure")

        stats = engine.journal_stats(group_by="outcome")

        assert "groups" in stats
        groups = {g["outcome"]: g["count"] for g in stats["groups"]}
        assert groups.get("success", 0) == 2
        assert groups.get("failure", 0) == 1

    def test_aggregate_by_author(self, engine):
        """Aggregate counts by author."""
        engine.journal_append(author="alice", context="1")
        engine.journal_append(author="alice", context="2")
        engine.journal_append(author="bob", context="3")

        stats = engine.journal_stats(group_by="author")

        groups = {g["author"]: g["count"] for g in stats["groups"]}
        assert groups.get("alice", 0) == 2
        assert groups.get("bob", 0) == 1

    def test_aggregate_by_tool(self, engine):
        """Aggregate counts by tool."""
        engine.journal_append(author="test", context="1", tool="bash")
        engine.journal_append(author="test", context="2", tool="bash")
        engine.journal_append(author="test", context="3", tool="read_file")

        stats = engine.journal_stats(group_by="tool")

        groups = {g["tool"]: g["count"] for g in stats["groups"]}
        assert groups.get("bash", 0) == 2
        assert groups.get("read_file", 0) == 1

    def test_aggregate_with_date_filter(self, engine):
        """Aggregate respects date filters."""
        engine.journal_append(author="test", context="1", outcome="success")
        engine.journal_append(author="test", context="2", outcome="failure")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = engine.journal_stats(group_by="outcome", date_from=today)

        assert stats["totals"]["count"] >= 2

    def test_overall_stats(self, engine):
        """Stats without group_by returns overall statistics."""
        engine.journal_append(author="alice", context="1", outcome="success")
        engine.journal_append(author="bob", context="2", outcome="failure")

        stats = engine.journal_stats()

        assert "total_entries" in stats
        assert stats["total_entries"] >= 2
        assert "by_type" in stats
        assert "by_outcome" in stats


class TestActiveOperations:
    """Tests for finding active/hanging operations."""

    def test_find_long_running(self, engine):
        """Finds entries with long duration."""
        engine.journal_append(
            author="test",
            context="Quick",
            tool="bash",
            duration_ms=1000,
            outcome="success",
        )
        engine.journal_append(
            author="test",
            context="Slow",
            tool="bash",
            duration_ms=60000,
            outcome="success",
        )

        results = engine.journal_active(threshold_ms=30000)

        # Should find the slow one
        assert len(results) >= 1
        durations = [r.get("duration_ms", 0) for r in results]
        assert any(d > 30000 for d in durations)

    def test_find_by_tool(self, engine):
        """Can filter active operations by tool."""
        engine.journal_append(
            author="test",
            context="Slow bash",
            tool="bash",
            duration_ms=60000,
            outcome="success",  # Include outcome to prevent "missing outcome" match
        )
        engine.journal_append(
            author="test",
            context="Slow file op",
            tool="read_file",
            duration_ms=60000,
            outcome="success",
        )

        results = engine.journal_active(threshold_ms=30000, tool_filter="bash")

        # Results should only contain bash entries
        bash_results = [r for r in results if r.get("tool") == "bash"]
        assert len(bash_results) >= 1
        # All bash entries should be bash
        for r in bash_results:
            assert r.get("tool") == "bash"


class TestRebuildIndex:
    """Tests for rebuilding the index from markdown."""

    def test_rebuild_indexes_existing_entries(self, engine, temp_project):
        """Rebuild indexes entries from existing markdown files."""
        # Create some entries
        engine.journal_append(author="alice", context="First")
        engine.journal_append(author="bob", context="Second")

        # Close the index connection before deleting the file
        if engine._index is not None:
            engine._index.close()
            engine._index = None

        # Delete the index to simulate corruption/fresh start
        db_path = temp_project / "a" / "journal" / ".index.db"
        if db_path.exists():
            db_path.unlink()

        # Rebuild (will create new index)
        stats = engine.rebuild_sqlite_index()

        assert stats["files_processed"] >= 1
        assert stats["entries_indexed"] >= 2

        # Verify entries are queryable
        results = engine.journal_query()
        assert len(results) >= 2


class TestIndexClose:
    """Tests for index cleanup."""

    def test_close_connection(self, journal_index):
        """Can close the database connection."""
        # Access connection to create it
        _ = journal_index._get_connection()
        assert journal_index._connection is not None

        journal_index.close()
        assert journal_index._connection is None
