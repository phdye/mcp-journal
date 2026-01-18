"""Tests for the query and stats MCP tools."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig
from mcp_journal.engine import JournalEngine
from mcp_journal.tools import execute_tool, make_tools


# Fixtures temp_project, config, and engine are provided by conftest.py


class TestJournalQueryTool:
    """Tests for the journal_query MCP tool."""

    @pytest.mark.asyncio
    async def test_query_returns_results(self, engine):
        """journal_query tool returns results."""
        engine.journal_append(author="test", context="First entry")
        engine.journal_append(author="test", context="Second entry")

        result = await execute_tool(engine, "journal_query", {})

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_query_with_filters(self, engine):
        """journal_query tool accepts filters."""
        engine.journal_append(author="alice", context="Alice's entry", outcome="success")
        engine.journal_append(author="bob", context="Bob's entry", outcome="failure")

        result = await execute_tool(engine, "journal_query", {
            "filters": {"author": "alice"},
        })

        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["author"] == "alice"

    @pytest.mark.asyncio
    async def test_query_with_text_search(self, engine):
        """journal_query tool supports text search."""
        engine.journal_append(author="test", context="Working on feature X")
        engine.journal_append(author="test", context="Debugging issue Y")

        result = await execute_tool(engine, "journal_query", {
            "text_search": "feature X",
        })

        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_query_with_date_range(self, engine):
        """journal_query tool supports date range."""
        engine.journal_append(author="test", context="Today's entry")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = await execute_tool(engine, "journal_query", {
            "date_from": today,
            "date_to": today,
        })

        assert result["success"] is True
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_query_with_pagination(self, engine):
        """journal_query tool supports pagination."""
        for i in range(10):
            engine.journal_append(author="test", context=f"Entry {i}")

        result = await execute_tool(engine, "journal_query", {
            "limit": 5,
            "offset": 0,
        })

        assert result["success"] is True
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_query_with_ordering(self, engine):
        """journal_query tool supports ordering."""
        engine.journal_append(author="test", context="First")
        engine.journal_append(author="test", context="Second")

        result_desc = await execute_tool(engine, "journal_query", {
            "order_by": "timestamp",
            "order_desc": True,
        })
        result_asc = await execute_tool(engine, "journal_query", {
            "order_by": "timestamp",
            "order_desc": False,
        })

        assert result_desc["success"] is True
        assert result_asc["success"] is True

        # Timestamps should be in opposite order
        desc_timestamps = [r["timestamp"] for r in result_desc["results"]]
        asc_timestamps = [r["timestamp"] for r in result_asc["results"]]
        assert desc_timestamps == list(reversed(asc_timestamps))


class TestJournalStatsTool:
    """Tests for the journal_stats MCP tool."""

    @pytest.mark.asyncio
    async def test_stats_overall(self, engine):
        """journal_stats tool returns overall stats."""
        engine.journal_append(author="test", context="Entry")

        result = await execute_tool(engine, "journal_stats", {})

        assert result["success"] is True
        assert "total_entries" in result

    @pytest.mark.asyncio
    async def test_stats_group_by_outcome(self, engine):
        """journal_stats tool groups by outcome."""
        engine.journal_append(author="test", context="1", outcome="success")
        engine.journal_append(author="test", context="2", outcome="success")
        engine.journal_append(author="test", context="3", outcome="failure")

        result = await execute_tool(engine, "journal_stats", {
            "group_by": "outcome",
        })

        assert result["success"] is True
        assert "groups" in result
        assert "totals" in result

    @pytest.mark.asyncio
    async def test_stats_group_by_author(self, engine):
        """journal_stats tool groups by author."""
        engine.journal_append(author="alice", context="1")
        engine.journal_append(author="bob", context="2")

        result = await execute_tool(engine, "journal_stats", {
            "group_by": "author",
        })

        assert result["success"] is True
        authors = {g["author"] for g in result["groups"]}
        assert "alice" in authors
        assert "bob" in authors

    @pytest.mark.asyncio
    async def test_stats_group_by_tool(self, engine):
        """journal_stats tool groups by tool."""
        engine.journal_append(author="test", context="1", tool="bash")
        engine.journal_append(author="test", context="2", tool="read_file")

        result = await execute_tool(engine, "journal_stats", {
            "group_by": "tool",
        })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_stats_with_date_filter(self, engine):
        """journal_stats tool respects date filters."""
        engine.journal_append(author="test", context="Entry")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = await execute_tool(engine, "journal_stats", {
            "group_by": "outcome",
            "date_from": today,
        })

        assert result["success"] is True


class TestJournalActiveTool:
    """Tests for the journal_active MCP tool."""

    @pytest.mark.asyncio
    async def test_active_finds_long_running(self, engine):
        """journal_active tool finds long-running operations."""
        engine.journal_append(
            author="test",
            context="Slow operation",
            tool="bash",
            duration_ms=60000,
        )

        result = await execute_tool(engine, "journal_active", {
            "threshold_ms": 30000,
        })

        assert result["success"] is True
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_active_filter_by_tool(self, engine):
        """journal_active tool can filter by tool."""
        engine.journal_append(
            author="test",
            context="Slow bash",
            tool="bash",
            duration_ms=60000,
            outcome="success",  # Include outcome to prevent "missing outcome" match
        )
        engine.journal_append(
            author="test",
            context="Slow file",
            tool="read_file",
            duration_ms=60000,
            outcome="success",
        )

        result = await execute_tool(engine, "journal_active", {
            "threshold_ms": 30000,
            "tool_filter": "bash",
        })

        assert result["success"] is True
        # Filter results to bash only and verify
        bash_results = [r for r in result["results"] if r.get("tool") == "bash"]
        assert len(bash_results) >= 1


class TestRebuildSqliteIndexTool:
    """Tests for the rebuild_sqlite_index MCP tool."""

    @pytest.mark.asyncio
    async def test_rebuild_returns_stats(self, engine):
        """rebuild_sqlite_index tool returns statistics."""
        engine.journal_append(author="test", context="Entry")

        result = await execute_tool(engine, "rebuild_sqlite_index", {})

        assert result["success"] is True
        assert "message" in result
        assert "files_processed" in result
        assert "entries_indexed" in result


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_make_tools_includes_new_tools(self, engine):
        """make_tools includes the new query tools."""
        tools = make_tools(engine)

        assert "journal_query" in tools
        assert "journal_stats" in tools
        assert "journal_active" in tools
        assert "rebuild_sqlite_index" in tools

    def test_journal_query_schema(self, engine):
        """journal_query has correct schema."""
        tools = make_tools(engine)
        schema = tools["journal_query"]["inputSchema"]

        assert "filters" in schema["properties"]
        assert "text_search" in schema["properties"]
        assert "date_from" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "offset" in schema["properties"]
        assert "order_by" in schema["properties"]

    def test_journal_stats_schema(self, engine):
        """journal_stats has correct schema."""
        tools = make_tools(engine)
        schema = tools["journal_stats"]["inputSchema"]

        assert "group_by" in schema["properties"]
        assert "aggregations" in schema["properties"]
        assert "filters" in schema["properties"]

    def test_journal_active_schema(self, engine):
        """journal_active has correct schema."""
        tools = make_tools(engine)
        schema = tools["journal_active"]["inputSchema"]

        assert "threshold_ms" in schema["properties"]
        assert "tool_filter" in schema["properties"]


class TestDiagnosticFieldsInAppend:
    """Tests for diagnostic fields in journal_append."""

    @pytest.mark.asyncio
    async def test_append_with_diagnostic_fields(self, engine):
        """journal_append accepts diagnostic fields."""
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Running command",
            "tool": "bash",
            "duration_ms": 5000,
            "exit_code": 0,
            "command": "echo hello",
        })

        assert result["success"] is True

        # Verify fields were stored
        query_result = await execute_tool(engine, "journal_query", {
            "filters": {"tool": "bash"},
        })

        assert query_result["success"] is True
        assert query_result["count"] == 1
        entry = query_result["results"][0]
        assert entry["tool"] == "bash"
        assert entry["duration_ms"] == 5000
        assert entry["exit_code"] == 0
        assert entry["command"] == "echo hello"

    @pytest.mark.asyncio
    async def test_append_with_error_type(self, engine):
        """journal_append accepts error_type field."""
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Failed command",
            "tool": "bash",
            "outcome": "failure",
            "exit_code": 1,
            "error_type": "timeout",
        })

        assert result["success"] is True

        query_result = await execute_tool(engine, "journal_query", {
            "filters": {"outcome": "failure"},
        })

        assert query_result["results"][0]["error_type"] == "timeout"


class TestDefaultTemplates:
    """Tests for default templates."""

    def test_diagnostic_template_available(self, config):
        """Diagnostic template is available by default."""
        assert "diagnostic" in config.templates

    def test_build_template_available(self, config):
        """Build template is available by default."""
        assert "build" in config.templates

    def test_test_template_available(self, config):
        """Test template is available by default."""
        assert "test" in config.templates
