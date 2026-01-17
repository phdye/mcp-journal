"""Tests for MCP tool definitions and execution."""

import tempfile
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig, EntryTemplateConfig
from mcp_journal.engine import JournalEngine
from mcp_journal.tools import make_tools, execute_tool


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_project):
    """Create a test configuration."""
    return ProjectConfig(
        project_name="test-project",
        project_root=temp_project,
    )


@pytest.fixture
def engine(config):
    """Create a test engine."""
    return JournalEngine(config)


class TestMakeTools:
    """Tests for make_tools function."""

    def test_make_tools_returns_all_tools(self, engine):
        """make_tools returns all expected tool definitions."""
        tools = make_tools(engine)

        expected_tools = [
            "journal_append",
            "journal_amend",
            "config_archive",
            "config_activate",
            "log_preserve",
            "state_snapshot",
            "journal_search",
            "index_rebuild",
            "journal_read",
            "timeline",
            "config_diff",
            "session_handoff",
            "trace_causality",
            "list_templates",
            "get_template",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools
            assert "name" in tools[tool_name]
            assert "description" in tools[tool_name]
            assert "inputSchema" in tools[tool_name]

    def test_tool_schema_structure(self, engine):
        """Tool schemas have proper structure."""
        tools = make_tools(engine)

        for tool_name, tool_def in tools.items():
            assert tool_def["name"] == tool_name
            assert isinstance(tool_def["description"], str)
            assert tool_def["inputSchema"]["type"] == "object"


class TestExecuteTool:
    """Tests for execute_tool function."""

    @pytest.mark.asyncio
    async def test_journal_append_tool(self, engine):
        """Test journal_append tool execution."""
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Test context",
        })

        assert result["success"] is True
        assert "entry_id" in result
        assert "timestamp" in result
        assert "message" in result

    @pytest.mark.asyncio
    async def test_journal_amend_tool(self, engine):
        """Test journal_amend tool execution."""
        # First create an entry to amend
        entry_result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Original entry",
        })
        entry_id = entry_result["entry_id"]

        result = await execute_tool(engine, "journal_amend", {
            "references_entry": entry_id,
            "correction": "Wrong info",
            "actual": "Correct info",
            "impact": "Minor",
            "author": "test",
        })

        assert result["success"] is True
        assert "entry_id" in result
        assert result["amends"] == entry_id

    @pytest.mark.asyncio
    async def test_config_archive_tool(self, engine, temp_project):
        """Test config_archive tool execution."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        result = await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "Test archive",
        })

        assert result["success"] is True
        assert "archive_path" in result
        assert "content_hash" in result

    @pytest.mark.asyncio
    async def test_config_archive_duplicate_error(self, engine, temp_project):
        """Test config_archive returns error for duplicates."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        # First archive succeeds
        await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "First",
        })

        # Second archive returns error
        result = await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "Second",
        })

        assert result["success"] is False
        assert result["error_type"] == "duplicate_content"

    @pytest.mark.asyncio
    async def test_config_activate_tool(self, engine, temp_project):
        """Test config_activate tool execution."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        # First archive
        archive_result = await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "Test",
        })

        # Create entry for activation
        entry_result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Activating config",
        })

        # Activate
        result = await execute_tool(engine, "config_activate", {
            "archive_path": archive_result["archive_path"],
            "target_path": str(temp_project / "active.toml"),
            "reason": "Testing",
            "journal_entry": entry_result["entry_id"],
        })

        assert result["success"] is True
        assert "target_path" in result

    @pytest.mark.asyncio
    async def test_log_preserve_tool(self, engine, temp_project):
        """Test log_preserve tool execution."""
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")

        result = await execute_tool(engine, "log_preserve", {
            "file_path": str(log_file),
            "category": "test",
            "outcome": "success",
        })

        assert result["success"] is True
        assert "preserved_path" in result

    @pytest.mark.asyncio
    async def test_state_snapshot_tool(self, engine):
        """Test state_snapshot tool execution."""
        result = await execute_tool(engine, "state_snapshot", {
            "name": "test-snapshot",
            "include_configs": False,
            "include_env": False,
            "include_versions": False,
        })

        assert result["success"] is True
        assert "snapshot_path" in result

    @pytest.mark.asyncio
    async def test_journal_search_tool(self, engine):
        """Test journal_search tool execution."""
        # Create entry to search
        await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Searchable content",
        })

        result = await execute_tool(engine, "journal_search", {
            "query": "Searchable",
        })

        assert result["success"] is True
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_index_rebuild_tool(self, engine):
        """Test index_rebuild tool execution."""
        result = await execute_tool(engine, "index_rebuild", {
            "directory": "configs",
            "dry_run": True,
        })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_journal_read_tool(self, engine):
        """Test journal_read tool execution."""
        # Create entry
        entry_result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Read test",
        })

        result = await execute_tool(engine, "journal_read", {
            "entry_id": entry_result["entry_id"],
        })

        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_timeline_tool(self, engine):
        """Test timeline tool execution."""
        await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Timeline test",
        })

        result = await execute_tool(engine, "timeline", {})

        assert result["success"] is True
        assert "events" in result

    @pytest.mark.asyncio
    async def test_config_diff_tool(self, engine, temp_project):
        """Test config_diff tool execution."""
        file1 = temp_project / "config1.toml"
        file2 = temp_project / "config2.toml"
        file1.write_text("[test]\nvalue = 1")
        file2.write_text("[test]\nvalue = 2")

        result = await execute_tool(engine, "config_diff", {
            "path_a": f"current:{file1}",
            "path_b": f"current:{file2}",
        })

        assert result["success"] is True
        assert "identical" in result
        assert result["identical"] is False

    @pytest.mark.asyncio
    async def test_session_handoff_tool(self, engine):
        """Test session_handoff tool execution."""
        await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Handoff test",
        })

        result = await execute_tool(engine, "session_handoff", {
            "format": "markdown",
        })

        assert result["success"] is True
        assert "content" in result
        assert result["format"] == "markdown"

    @pytest.mark.asyncio
    async def test_trace_causality_tool(self, engine):
        """Test trace_causality tool execution."""
        # Create entry
        entry_result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Causality test",
        })

        result = await execute_tool(engine, "trace_causality", {
            "entry_id": entry_result["entry_id"],
        })

        assert result["success"] is True
        assert result["entry_id"] == entry_result["entry_id"]

    @pytest.mark.asyncio
    async def test_trace_causality_invalid_entry(self, engine):
        """Test trace_causality with invalid entry returns error."""
        result = await execute_tool(engine, "trace_causality", {
            "entry_id": "1999-01-01-001",
        })

        assert result["success"] is False
        assert result["error_type"] == "invalid_reference"

    @pytest.mark.asyncio
    async def test_list_templates_tool(self, engine):
        """Test list_templates tool execution."""
        result = await execute_tool(engine, "list_templates", {})

        assert result["success"] is True
        assert "templates" in result

    @pytest.mark.asyncio
    async def test_get_template_tool(self, temp_project):
        """Test get_template tool execution."""
        templates = {
            "test_tmpl": EntryTemplateConfig(
                name="test_tmpl",
                description="Test template",
            ),
        }
        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            templates=templates,
        )
        engine = JournalEngine(config)

        result = await execute_tool(engine, "get_template", {"name": "test_tmpl"})

        assert result["success"] is True
        assert "template" in result

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, engine):
        """Test get_template with nonexistent template."""
        result = await execute_tool(engine, "get_template", {"name": "nonexistent"})

        assert result["success"] is False
        assert result["error_type"] == "template_not_found"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, engine):
        """Test unknown tool returns error."""
        result = await execute_tool(engine, "unknown_tool", {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_reference_error(self, engine):
        """Test InvalidReferenceError handling."""
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "references": ["invalid-ref-xyz"],
        })

        assert result["success"] is False
        assert result["error_type"] == "invalid_reference"

    @pytest.mark.asyncio
    async def test_template_required_error(self, temp_project):
        """Test TemplateRequiredError handling."""
        templates = {
            "required": EntryTemplateConfig(
                name="required",
                description="Required template",
            ),
        }
        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            templates=templates,
            require_templates=True,
        )
        engine = JournalEngine(config)

        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "No template",
        })

        assert result["success"] is False
        assert result["error_type"] == "template_required"

    @pytest.mark.asyncio
    async def test_template_not_found_error(self, engine):
        """Test TemplateNotFoundError handling."""
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "template": "nonexistent",
        })

        assert result["success"] is False
        assert result["error_type"] == "template_not_found"

    @pytest.mark.asyncio
    async def test_file_not_found_error(self, engine):
        """Test FileNotFoundError handling."""
        result = await execute_tool(engine, "config_archive", {
            "file_path": "/nonexistent/path/file.toml",
            "reason": "Test",
        })

        assert result["success"] is False
        assert result["error_type"] == "file_not_found"

    @pytest.mark.asyncio
    async def test_journal_append_with_all_causality_fields(self, engine, temp_project):
        """Test journal_append with all causality fields."""
        # Create config archive
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        archive_result = await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "Test",
        })

        # Create log
        log_file = temp_project / "test.log"
        log_file.write_text("Log")
        log_result = await execute_tool(engine, "log_preserve", {
            "file_path": str(log_file),
        })

        # Create entry with all causality fields
        result = await execute_tool(engine, "journal_append", {
            "author": "test",
            "context": "Full causality test",
            "config_used": archive_result["archive_path"],
            "log_produced": log_result["preserved_path"],
            "outcome": "success",
        })

        assert result["success"] is True
        assert result["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_config_activate_with_previous(self, engine, temp_project):
        """Test config_activate when target already exists."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        # First archive
        archive_result = await execute_tool(engine, "config_archive", {
            "file_path": str(config_file),
            "reason": "First",
        })

        # Create target file
        target_path = temp_project / "active.toml"
        target_path.write_text("[test]\nvalue = old")

        # Create journal entry
        entry_result = await execute_tool(engine, "journal_append", {
            "author": "test",
        })

        # Activate (should archive existing target first)
        result = await execute_tool(engine, "config_activate", {
            "archive_path": archive_result["archive_path"],
            "target_path": str(target_path),
            "reason": "Activate",
            "journal_entry": entry_result["entry_id"],
        })

        assert result["success"] is True
        assert "previous_archive" in result
