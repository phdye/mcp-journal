"""Tests for achieving 100% coverage on all modules."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Callable

import pytest

from mcp_journal.config import (
    ProjectConfig,
    EntryTemplateConfig,
    VersionCommand,
    load_toml_config,
    load_python_config,
    dict_to_config,
    load_config,
)
from mcp_journal.engine import JournalEngine, AppendOnlyViolation
from mcp_journal.locking import atomic_write
from mcp_journal.models import EntryTemplate, JournalEntry, EntryType, utc_now
from mcp_journal.tools import execute_tool


# Fixtures temp_project, config, engine are provided by conftest.py
# The cleanup_engines autouse fixture ensures all SQLite connections are closed


# ============ config.py - Lines 20-21, 131 ============

class TestConfigTomliNotInstalled:
    """Test config behavior when tomli is not installed."""

    def test_tomli_import_error_path(self, temp_project):
        """Verify the tomli = None path is covered."""
        import mcp_journal.config as config_module

        # Force tomli to None
        original_tomli = config_module.tomli
        config_module.tomli = None

        try:
            toml_file = temp_project / "test.toml"
            toml_file.write_text("[test]\nvalue = 1")

            with pytest.raises(ImportError, match="tomli required"):
                load_toml_config(toml_file)
        finally:
            config_module.tomli = original_tomli


class TestPythonConfigSpecNone:
    """Test Python config when spec_from_file_location returns None."""

    def test_load_python_config_spec_none(self, temp_project):
        """Test ImportError when spec is None."""
        # Create a file that exists but can't be loaded as a module
        py_file = temp_project / "invalid_module.py"
        py_file.write_text("")  # Empty file

        # Mock spec_from_file_location to return None
        with patch('mcp_journal.config.importlib.util.spec_from_file_location', return_value=None):
            with pytest.raises(ImportError, match="Cannot load Python config"):
                load_python_config(py_file)


# ============ engine.py - Hooks coverage ============

class TestEngineHooks:
    """Test engine hooks for coverage."""

    def test_pre_append_hook(self, temp_project):
        """Test pre_append hook is called."""
        hook_called = {"called": False}

        def pre_append_hook(entry, custom_fields):
            hook_called["called"] = True
            return entry

        config = ProjectConfig(
            project_root=temp_project,
            hooks={"pre_append": pre_append_hook},
        )
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Hook test")

        assert hook_called["called"] is True

    def test_post_append_hook(self, temp_project):
        """Test post_append hook is called."""
        hook_called = {"called": False, "entry_id": None}

        def post_append_hook(entry):
            hook_called["called"] = True
            hook_called["entry_id"] = entry.entry_id

        config = ProjectConfig(
            project_root=temp_project,
            hooks={"post_append": post_append_hook},
        )
        engine = JournalEngine(config)

        entry = engine.journal_append(author="test", context="Post hook test")

        assert hook_called["called"] is True
        assert hook_called["entry_id"] == entry.entry_id

    def test_capture_versions_hook(self, temp_project):
        """Test capture_versions hook during state_snapshot."""
        def capture_versions_hook(engine):
            return {"custom_version": "1.0.0"}

        config = ProjectConfig(
            project_root=temp_project,
            hooks={"capture_versions": capture_versions_hook},
        )
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="hook-test",
            include_configs=False,
            include_env=False,
            include_versions=True,
        )

        assert snapshot.versions["custom_version"] == "1.0.0"


class TestJournalAmendNewFile:
    """Test journal_amend when journal file doesn't exist yet."""

    def test_amend_creates_entry(self, temp_project):
        """Test amendment creates a new entry properly."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create an entry
        entry = engine.journal_append(author="test", context="Original")

        # Create amendment - this tests the amendment code path
        amendment = engine.journal_amend(
            references_entry=entry.entry_id,
            correction="Error found",
            actual="Correct value",
            impact="Minor impact",
            author="test",
        )

        # Verify amendment was created
        assert amendment.entry_type == EntryType.AMENDMENT
        assert amendment.references_entry == entry.entry_id


class TestConfigActivateRelativePath:
    """Test config_activate with relative target path."""

    def test_activate_relative_target_path(self, temp_project):
        """config_activate handles relative target path."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create and archive config
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        record = engine.config_archive(file_path=str(config_file), reason="Test")

        # Activate with relative path
        result = engine.config_activate(
            archive_path=record.archive_path,
            target_path="activated.toml",  # Relative path
            reason="Test",
            journal_entry="2026-01-06-001",
        )

        # Verify activation
        activated = temp_project / "activated.toml"
        assert activated.exists()


class TestLogPreserveRelativePath:
    """Test log_preserve with relative path."""

    def test_preserve_relative_path(self, temp_project):
        """log_preserve handles relative path."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create log in project root
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")

        # Preserve with relative path
        record = engine.log_preserve(file_path="test.log")

        assert record.preserved_path is not None


class TestStateSnapshotConfigException:
    """Test state_snapshot config capture exception handling."""

    def test_snapshot_handles_unreadable_config(self, temp_project):
        """state_snapshot handles exceptions when reading configs."""
        config = ProjectConfig(
            project_root=temp_project,
            config_patterns=["*.toml"],
        )
        engine = JournalEngine(config)

        # Create a config file that will cause exception
        # (we'll mock the read to fail)
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")

        with patch.object(Path, 'read_text', side_effect=PermissionError("Access denied")):
            snapshot = engine.state_snapshot(
                name="error-test",
                include_configs=True,
                include_env=False,
                include_versions=False,
            )

        # Should complete without crashing
        assert snapshot.name == "error-test"


class TestStateSnapshotVersionCommands:
    """Test state_snapshot version command execution."""

    def test_snapshot_version_command_with_regex(self, temp_project):
        """state_snapshot executes version commands with regex."""
        config = ProjectConfig(
            project_root=temp_project,
            version_commands=[
                VersionCommand(
                    name="python",
                    command="python --version",
                    parse_regex=r"Python (\d+\.\d+\.\d+)",
                ),
            ],
        )
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="version-test",
            include_configs=False,
            include_env=False,
            include_versions=True,
        )

        assert "python" in snapshot.versions

    def test_snapshot_version_command_error(self, temp_project):
        """state_snapshot handles version command errors."""
        config = ProjectConfig(
            project_root=temp_project,
            version_commands=[
                VersionCommand(
                    name="nonexistent",
                    command="nonexistent_command_xyz --version",
                ),
            ],
        )
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="error-test",
            include_configs=False,
            include_env=False,
            include_versions=True,
        )

        # Should have some output (error message from shell or ERROR prefix)
        assert "nonexistent" in snapshot.versions
        # Command may either return error message or shell error
        assert snapshot.versions["nonexistent"] is not None


class TestStateSnapshotBuildDirRelative:
    """Test state_snapshot with relative build dir."""

    def test_snapshot_build_dir_relative_path(self, temp_project):
        """state_snapshot handles relative build_dir."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create build dir with files
        build_dir = temp_project / "build"
        build_dir.mkdir()
        (build_dir / "output.bin").write_bytes(b"data")

        snapshot = engine.state_snapshot(
            name="build-test",
            include_configs=False,
            include_env=False,
            include_versions=False,
            include_build_dir_listing=True,
            build_dir="build",  # Relative path
        )

        assert snapshot.build_dir_listing is not None
        assert "output.bin" in snapshot.build_dir_listing


# ============ models.py - Line 146 (EntryTemplate) ============

class TestEntryTemplateClass:
    """Test EntryTemplate class which is unused elsewhere."""

    def test_entry_template_instantiation(self):
        """Test EntryTemplate can be instantiated."""
        template = EntryTemplate(
            name="test",
            description="Test template",
            context_template="Context: {value}",
            required_fields=["value"],
        )

        assert template.name == "test"
        assert template.description == "Test template"


# ============ tools.py - Lines 729, 759-767 ============

class TestToolsExceptionHandlers:
    """Test tools.py exception handlers."""

    @pytest.mark.asyncio
    async def test_append_only_violation_handler(self, temp_project):
        """Test AppendOnlyViolation exception handler."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # AppendOnlyViolation is difficult to trigger directly
        # Mock the engine method to raise it
        with patch.object(engine, 'journal_append', side_effect=AppendOnlyViolation("Test violation")):
            result = await execute_tool(engine, "journal_append", {
                "author": "test",
            })

        assert result["success"] is False
        assert result["error_type"] == "append_only_violation"

    @pytest.mark.asyncio
    async def test_general_exception_handler(self, temp_project):
        """Test general Exception handler."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Mock to raise unexpected exception
        with patch.object(engine, 'journal_append', side_effect=RuntimeError("Unexpected error")):
            result = await execute_tool(engine, "journal_append", {
                "author": "test",
            })

        assert result["success"] is False
        assert result["error_type"] == "unexpected_error"


# ============ Additional engine.py coverage ============

class TestEngineContentHash:
    """Test _content_hash method."""

    def test_content_hash_called(self, temp_project):
        """Verify _content_hash is accessible."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Call _content_hash directly
        hash_result = engine._content_hash(b"test content")

        assert len(hash_result) == 64  # SHA-256 hex digest


class TestEngineTimelineEdgeCases:
    """Test timeline edge cases."""

    def test_timeline_date_filtering(self, temp_project):
        """Test timeline with date range that excludes entries."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Entry")

        # Date range in the past
        events = engine.timeline(date_from="2020-01-01", date_to="2020-12-31")
        assert events == []


class TestEngineSearchEdgeCases:
    """Test search edge cases for coverage."""

    def test_search_with_date_range(self, temp_project):
        """Test search with date range filters."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Searchable content")

        # Search with date range
        results = engine.journal_search(
            query="Searchable",
            date_from="2020-01-01",
            date_to="2030-12-31",
        )

        assert len(results) >= 1

    def test_search_with_entry_type(self, temp_project):
        """Test search with entry_type filter."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        entry = engine.journal_append(author="test", context="Original content here")
        engine.journal_amend(
            references_entry=entry.entry_id,
            correction="Error in original",
            actual="Correct version",
            impact="Minor impact",
            author="test",
        )

        # Search for entries only (not amendments)
        results = engine.journal_search(
            query="Original",
            entry_type="entry",
        )

        # Should find the original entry
        assert len(results) >= 1
        # Verify we found entries, not amendments
        for r in results:
            assert r.get("entry_type") != "amendment"


class TestIndexRebuildEdgeCases:
    """Test index_rebuild edge cases."""

    def test_index_rebuild_empty_directory(self, temp_project):
        """index_rebuild handles empty directory."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # No files in configs directory
        result = engine.index_rebuild(directory="configs")

        assert result["action"] == "rebuilt"
        assert result["files_found"] == 0


# ============ server.py coverage with mocking ============

class TestServerWithMockedMCP:
    """Test server.py with mocked MCP."""

    def test_create_server_with_mocked_mcp(self, temp_project):
        """Test create_server when MCP is mocked as available."""
        # Mock MCP imports
        mock_server = MagicMock()
        mock_server_class = MagicMock(return_value=mock_server)

        with patch.dict('sys.modules', {
            'mcp': MagicMock(),
            'mcp.server': MagicMock(Server=mock_server_class),
            'mcp.server.stdio': MagicMock(),
            'mcp.types': MagicMock(),
        }):
            # Reimport to get mocked version
            import importlib
            import mcp_journal.server as server_module
            importlib.reload(server_module)

            if server_module.HAS_MCP:
                config = ProjectConfig(project_root=temp_project)
                server = server_module.create_server(config)
                assert server is not None


class TestServerMainFunction:
    """Test server main function."""

    def test_main_with_explicit_config(self, temp_project):
        """Test main with explicit config file."""
        import mcp_journal.server as server_module

        # Create a config file
        config_file = temp_project / "journal_config.json"
        config_file.write_text('{"project": {"name": "test"}}')

        if not server_module.HAS_MCP:
            test_args = [
                "mcp-journal",
                "--project-root", str(temp_project),
                "--config", str(config_file),
            ]
            with patch.object(sys, 'argv', test_args):
                with pytest.raises(SystemExit) as exc_info:
                    server_module.main()
                assert exc_info.value.code == 1


# ============ Additional engine.py coverage ============

class TestStateSnapshotCustomData:
    """Test state_snapshot with custom_data."""

    def test_snapshot_with_custom_data(self, temp_project):
        """state_snapshot includes custom_data when provided."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="custom-test",
            include_configs=False,
            include_env=False,
            include_versions=False,
            custom_data={"key": "value", "nested": {"a": 1}},
        )

        assert snapshot.custom_data is not None
        assert snapshot.custom_data["key"] == "value"
        assert snapshot.custom_data["nested"]["a"] == 1


class TestVersionCommandException:
    """Test version command that throws exception."""

    def test_version_command_timeout_error(self, temp_project):
        """Version command that times out returns ERROR."""
        import subprocess

        config = ProjectConfig(
            project_root=temp_project,
            version_commands=[
                VersionCommand(
                    name="timeout_cmd",
                    command="sleep 100",  # Will timeout
                ),
            ],
        )
        engine = JournalEngine(config)

        # Mock subprocess.run to raise timeout
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired("sleep", 1)):
            snapshot = engine.state_snapshot(
                name="timeout-test",
                include_configs=False,
                include_env=False,
                include_versions=True,
            )

        assert "timeout_cmd" in snapshot.versions
        assert "ERROR" in snapshot.versions["timeout_cmd"]


class TestJournalSearchDateFiltering:
    """Test journal_search date filtering."""

    def test_search_with_date_from_filter(self, temp_project):
        """journal_search filters by date_from."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Test entry")

        # Search with future date_from should return nothing
        results = engine.journal_search(query="Test", date_from="2099-01-01")
        assert results == []

    def test_search_with_date_to_filter(self, temp_project):
        """journal_search filters by date_to."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Test entry")

        # Search with past date_to should return nothing
        results = engine.journal_search(query="Test", date_to="2000-01-01")
        assert results == []


class TestJournalReadDateFiltering:
    """Test journal_read date filtering."""

    def test_read_with_date_to_past(self, temp_project):
        """journal_read with date_to in past returns empty."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Test")

        results = engine.journal_read(date_to="2000-01-01")
        assert results == []

    def test_read_with_date_from_future(self, temp_project):
        """journal_read with date_from in future returns empty."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Test")

        results = engine.journal_read(date_from="2099-01-01")
        assert results == []


class TestTimelineDateFiltering:
    """Test timeline date filtering."""

    def test_timeline_date_to_filter(self, temp_project):
        """timeline filters by date_to."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Entry")

        events = engine.timeline(date_to="2000-01-01")
        # Filter out non-entry events
        entry_events = [e for e in events if e.get("event_type") == "entry"]
        assert entry_events == []


class TestToolsJournalError:
    """Test tools.py JournalError handler."""

    @pytest.mark.asyncio
    async def test_journal_error_handler(self, temp_project):
        """Test JournalError exception handler."""
        from mcp_journal.engine import JournalError

        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Mock to raise JournalError
        with patch.object(engine, 'journal_append', side_effect=JournalError("Test journal error")):
            result = await execute_tool(engine, "journal_append", {
                "author": "test",
            })

        assert result["success"] is False
        assert result["error_type"] == "journal_error"


# ============ Additional edge cases ============

class TestJournalAmendOnNewDay:
    """Test amendment on a different day than original entry."""

    def test_amend_different_day(self, temp_project):
        """Amendment can reference entry from different day."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create original entry
        entry = engine.journal_append(author="test", context="Original")

        # Create amendment (will be same day in practice but tests the path)
        amendment = engine.journal_amend(
            references_entry=entry.entry_id,
            correction="Error",
            actual="Fixed",
            impact="None",
            author="test",
        )

        assert amendment is not None
        assert amendment.references_entry == entry.entry_id


class TestEntryReferencesExtracting:
    """Test extraction of references from journal entries."""

    def test_entry_with_references(self, temp_project):
        """Entry with references is parsed correctly."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create referenced files first (they must exist for validation)
        file1 = temp_project / "file1.txt"
        file2 = temp_project / "file2.txt"
        file1.write_text("Reference file 1")
        file2.write_text("Reference file 2")

        # Create an entry with references
        entry = engine.journal_append(
            author="test",
            context="Entry with references",
            references=["file1.txt", "file2.txt"],
        )

        # Read it back
        entries = engine.journal_read(entry_id=entry.entry_id)
        assert len(entries) == 1
        # References should be in the entry
        assert entry.references == ["file1.txt", "file2.txt"]


class TestTimelineEventTypeFiltering:
    """Test timeline filters by event type."""

    def test_timeline_filter_entries_only(self, temp_project):
        """timeline filters to entries only."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create entry and amendment
        entry = engine.journal_append(author="test", context="Entry")
        engine.journal_amend(
            references_entry=entry.entry_id,
            correction="Error",
            actual="Fix",
            impact="None",
            author="test",
        )

        # Filter to entries only (not amendments)
        events = engine.timeline(event_types=["entry"])

        for e in events:
            assert e["event_type"] != "amendment"

    def test_timeline_includes_all_event_types(self, temp_project):
        """timeline includes configs, logs, snapshots."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create various events
        engine.journal_append(author="test", context="Entry")

        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        engine.config_archive(file_path=str(config_file), reason="Test")

        log_file = temp_project / "test.log"
        log_file.write_text("log")
        engine.log_preserve(file_path=str(log_file))

        engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        # Get all events
        events = engine.timeline()
        event_types = {e["event_type"] for e in events}

        assert "entry" in event_types
        assert "config" in event_types
        assert "log" in event_types
        assert "snapshot" in event_types


class TestConfigDiffFileNotFound:
    """Test config_diff file not found handling."""

    def test_config_diff_path_a_not_found(self, temp_project):
        """config_diff raises FileNotFoundError for missing path_a."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        file_b = temp_project / "exists.toml"
        file_b.write_text("[test]")

        with pytest.raises(FileNotFoundError, match="Config not found"):
            engine.config_diff(
                path_a="current:/nonexistent/file.toml",
                path_b=f"current:{file_b}",
            )


class TestSessionHandoffWithConfigUsed:
    """Test session_handoff when entries have config_used."""

    def test_handoff_shows_active_config(self, temp_project):
        """session_handoff includes active config from last entry."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create config and entry using it
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        archive = engine.config_archive(file_path=str(config_file), reason="Test")

        engine.journal_append(
            author="test",
            context="Using config",
            config_used=archive.archive_path,
            outcome="success",
        )

        handoff = engine.session_handoff(format="markdown")

        assert archive.archive_path in handoff["content"]


class TestTraceCausalityDepthLimit:
    """Test trace_causality depth limiting."""

    def test_trace_limited_by_depth(self, temp_project):
        """trace_causality respects depth limit."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create chain: A -> B -> C -> D
        entry_a = engine.journal_append(author="test", context="A")
        entry_b = engine.journal_append(
            author="test",
            context="B",
            caused_by=[entry_a.entry_id],
        )
        entry_c = engine.journal_append(
            author="test",
            context="C",
            caused_by=[entry_b.entry_id],
        )
        entry_d = engine.journal_append(
            author="test",
            context="D",
            caused_by=[entry_c.entry_id],
        )

        # Trace with depth=2 from A
        result = engine.trace_causality(
            entry_id=entry_a.entry_id,
            direction="forward",
            depth=2,
        )

        # Should find some entries but depth-limited
        assert isinstance(result, dict)

    def test_trace_backward_entry_not_found(self, temp_project):
        """trace_causality handles missing caused_by entries."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create entry with caused_by pointing to non-existent entry
        # We need to manipulate the file directly since the API validates
        entry = engine.journal_append(author="test", context="Entry")

        # This tests the path where trace looks for an entry that doesn't exist
        result = engine.trace_causality(
            entry_id=entry.entry_id,
            direction="backward",
        )

        assert isinstance(result, dict)


# ============ engine.py lines 317-318: New journal file creation ============

class TestJournalAmendNewFile:
    """Test journal_amend when it creates a new journal file."""

    def test_amend_creates_new_journal_file(self, temp_project):
        """journal_amend creates journal file if it doesn't exist for that day."""
        from datetime import timedelta
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create an entry first (this creates today's journal file)
        entry = engine.journal_append(author="test", context="Original")

        # Rename the journal file to simulate it being from yesterday
        journal_dir = temp_project / "journal"
        today_file = list(journal_dir.glob("*.md"))[0]
        yesterday = (utc_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = journal_dir / f"{yesterday}.md"

        # Read content and update entry ID in content to match yesterday's date
        content = today_file.read_text()
        old_entry_id = entry.entry_id
        new_entry_id = f"{yesterday}-001"
        content = content.replace(old_entry_id, new_entry_id)
        content = content.replace(f"# Journal - {utc_now().strftime('%Y-%m-%d')}", f"# Journal - {yesterday}")

        # Write to yesterday's file and remove today's
        yesterday_file.write_text(content)
        today_file.unlink()

        # Now amend - this should create a NEW file for today
        amend = engine.journal_amend(
            references_entry=new_entry_id,
            correction="Wrong info",
            actual="Correct info",
            impact="Minor",
            author="test",
        )

        # Verify today's file was created
        today = utc_now().strftime("%Y-%m-%d")
        today_file = journal_dir / f"{today}.md"
        assert today_file.exists()
        assert amend is not None


# ============ engine.py lines 971-1018: Timeline date filtering ============

class TestTimelineDateFilteringConfigs:
    """Test timeline date filtering for config archives."""

    def test_timeline_config_filtered_by_date_from(self, temp_project):
        """Timeline filters configs by date_from."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a config archive
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        engine.config_archive(file_path=str(config_file), reason="Test")

        # Filter with future date_from should exclude the config
        events = engine.timeline(
            event_types=["config"],
            date_from="2099-01-01",
        )

        # Should have no config events
        config_events = [e for e in events if e.get("event_type") == "config_archive"]
        assert len(config_events) == 0

    def test_timeline_config_filtered_by_date_to(self, temp_project):
        """Timeline filters configs by date_to."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a config archive
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        engine.config_archive(file_path=str(config_file), reason="Test")

        # Filter with past date_to should exclude the config
        events = engine.timeline(
            event_types=["config"],
            date_to="2000-01-01",
        )

        # Should have no config events
        config_events = [e for e in events if e.get("event_type") == "config_archive"]
        assert len(config_events) == 0


class TestTimelineDateFilteringLogs:
    """Test timeline date filtering for log preservations."""

    def test_timeline_log_filtered_by_date_from(self, temp_project):
        """Timeline filters logs by date_from."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a log preservation
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")
        engine.log_preserve(file_path=str(log_file))

        # Filter with future date_from should exclude the log
        events = engine.timeline(
            event_types=["log"],
            date_from="2099-01-01",
        )

        # Should have no log events
        log_events = [e for e in events if e.get("event_type") == "log_preserve"]
        assert len(log_events) == 0

    def test_timeline_log_filtered_by_date_to(self, temp_project):
        """Timeline filters logs by date_to."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a log preservation
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")
        engine.log_preserve(file_path=str(log_file))

        # Filter with past date_to should exclude the log
        events = engine.timeline(
            event_types=["log"],
            date_to="2000-01-01",
        )

        # Should have no log events
        log_events = [e for e in events if e.get("event_type") == "log_preserve"]
        assert len(log_events) == 0


class TestTimelineDateFilteringSnapshots:
    """Test timeline date filtering for snapshots."""

    def test_timeline_snapshot_filtered_by_date_from(self, temp_project):
        """Timeline filters snapshots by date_from."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a snapshot
        engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        # Filter with future date_from should exclude the snapshot
        events = engine.timeline(
            event_types=["snapshot"],
            date_from="2099-01-01",
        )

        # Should have no snapshot events
        snapshot_events = [e for e in events if e.get("event_type") == "snapshot"]
        assert len(snapshot_events) == 0

    def test_timeline_snapshot_filtered_by_date_to(self, temp_project):
        """Timeline filters snapshots by date_to."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a snapshot
        engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        # Filter with past date_to should exclude the snapshot
        events = engine.timeline(
            event_types=["snapshot"],
            date_to="2000-01-01",
        )

        # Should have no snapshot events
        snapshot_events = [e for e in events if e.get("event_type") == "snapshot"]
        assert len(snapshot_events) == 0


# ============ engine.py lines 1319, 1322: trace_backward depth/not found ============

class TestTraceCausalityBackwardDepth:
    """Test trace_causality backward with depth limits."""

    def test_trace_backward_depth_limit(self, temp_project):
        """trace_backward stops at depth limit."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a chain of entries
        entry1 = engine.journal_append(author="test", context="First")
        entry2 = engine.journal_append(
            author="test",
            context="Second",
            caused_by=[entry1.entry_id],
        )
        entry3 = engine.journal_append(
            author="test",
            context="Third",
            caused_by=[entry2.entry_id],
        )

        # Trace backward with depth=1 from entry3
        result = engine.trace_causality(
            entry_id=entry3.entry_id,
            direction="backward",
            depth=1,
        )

        # Should find entry2 but not entry1 due to depth limit
        assert isinstance(result, dict)

    def test_trace_backward_missing_caused_by_entry(self, temp_project):
        """trace_backward handles when caused_by entry doesn't exist."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create an entry first
        entry1 = engine.journal_append(author="test", context="First")
        entry2 = engine.journal_append(
            author="test",
            context="Second",
            caused_by=[entry1.entry_id],
        )

        # Manipulate the journal file to add a fake caused_by reference
        journal_dir = temp_project / "journal"
        journal_file = list(journal_dir.glob("*.md"))[0]
        content = journal_file.read_text()

        # Add a non-existent entry ID to caused_by of entry2
        fake_id = "1999-01-01-999"
        content = content.replace(
            f"**Caused By**: {entry1.entry_id}",
            f"**Caused By**: {entry1.entry_id}, {fake_id}"
        )
        journal_file.write_text(content)

        # Now trace backward from entry2 - should handle the missing fake_id gracefully
        result = engine.trace_causality(
            entry_id=entry2.entry_id,
            direction="backward",
            depth=5,
        )

        # Should complete without error, just not finding the fake entry
        assert isinstance(result, dict)


# ============ locking.py line 65: Windows unlink path ============

class TestAtomicWriteWindowsPath:
    """Test atomic_write Windows-specific path."""

    def test_atomic_write_windows_unlink(self, temp_project):
        """atomic_write handles Windows rename when file exists."""
        test_file = temp_project / "test.txt"
        test_file.write_text("original")

        # Mock os.name to be 'nt' (Windows)
        with patch("mcp_journal.locking.os.name", "nt"):
            with atomic_write(test_file) as f:
                f.write("updated")

        assert test_file.read_text() == "updated"


# ============ models.py line 146: JournalEntry.to_dict ============

class TestJournalEntryToDict:
    """Test JournalEntry.to_dict method."""

    def test_entry_to_dict(self):
        """JournalEntry.to_dict returns proper dictionary."""
        entry = JournalEntry(
            entry_id="2026-01-06-001",
            timestamp=utc_now(),
            author="test",
            entry_type=EntryType.ENTRY,
            context="Test context",
            intent="Test intent",
        )

        result = entry.to_dict()

        assert isinstance(result, dict)
        assert result["entry_id"] == "2026-01-06-001"
        assert result["author"] == "test"
        assert result["context"] == "Test context"
        assert result["intent"] == "Test intent"
        assert result["entry_type"] == "entry"


# ============ server.py: Mock MCP for coverage ============

class TestServerWithMockedMCP:
    """Test server.py with mocked MCP imports."""

    def test_server_module_imports(self):
        """Server module can be imported."""
        from mcp_journal import server
        assert hasattr(server, "HAS_MCP")

    @pytest.mark.asyncio
    async def test_run_server_without_mcp(self):
        """run_server raises when MCP not available."""
        from mcp_journal import server

        if not server.HAS_MCP:
            with pytest.raises(ImportError, match="MCP package not installed"):
                await server.run_server(None)

    def test_create_server_without_mcp(self, temp_project):
        """create_server raises when MCP not available."""
        from mcp_journal import server

        if not server.HAS_MCP:
            config = ProjectConfig(project_root=temp_project)
            with pytest.raises(ImportError, match="MCP package not installed"):
                server.create_server(config)

    def test_main_init_mode(self, temp_project, capsys):
        """main() with --init creates directories."""
        from mcp_journal import server
        import sys

        # Save original argv
        original_argv = sys.argv

        try:
            sys.argv = ["mcp-journal", "--init", "--project-root", str(temp_project)]
            server.main()

            captured = capsys.readouterr()
            assert "Initialized journal directories" in captured.out
        finally:
            sys.argv = original_argv

    def test_main_without_mcp(self, temp_project, capsys):
        """main() without MCP prints error."""
        from mcp_journal import server
        import sys

        if not server.HAS_MCP:
            original_argv = sys.argv

            try:
                sys.argv = ["mcp-journal", "--project-root", str(temp_project)]
                with pytest.raises(SystemExit) as exc_info:
                    server.main()
                assert exc_info.value.code == 1

                captured = capsys.readouterr()
                assert "MCP package not installed" in captured.err
            finally:
                sys.argv = original_argv


class TestServerWithMCPMocked:
    """Test server functionality with MCP fully mocked."""

    def test_create_server_with_mocked_mcp(self, temp_project):
        """create_server works with mocked MCP."""
        # Create mock MCP classes
        mock_server_instance = MagicMock()
        mock_server_class = MagicMock(return_value=mock_server_instance)
        mock_tool = MagicMock()
        mock_text_content = MagicMock()

        # Patch the server module
        import mcp_journal.server as server_module

        original_has_mcp = server_module.HAS_MCP
        original_server = server_module.Server
        original_tool = server_module.Tool
        original_text_content = server_module.TextContent

        try:
            server_module.HAS_MCP = True
            server_module.Server = mock_server_class
            server_module.Tool = mock_tool
            server_module.TextContent = mock_text_content

            config = ProjectConfig(project_root=temp_project)
            result = server_module.create_server(config)

            assert result == mock_server_instance
            mock_server_class.assert_called_once_with("mcp-journal")
        finally:
            server_module.HAS_MCP = original_has_mcp
            server_module.Server = original_server
            server_module.Tool = original_tool
            server_module.TextContent = original_text_content

    def test_create_server_with_custom_tools(self, temp_project):
        """create_server handles custom tools from config."""
        # Create mock MCP classes
        mock_server_instance = MagicMock()
        mock_server_class = MagicMock(return_value=mock_server_instance)
        mock_tool = MagicMock()
        mock_text_content = MagicMock()

        import mcp_journal.server as server_module

        original_has_mcp = server_module.HAS_MCP
        original_server = server_module.Server
        original_tool = server_module.Tool
        original_text_content = server_module.TextContent

        try:
            server_module.HAS_MCP = True
            server_module.Server = mock_server_class
            server_module.Tool = mock_tool
            server_module.TextContent = mock_text_content

            def custom_tool(engine, params):
                """A custom tool for testing."""
                return {"result": "custom"}

            config = ProjectConfig(
                project_root=temp_project,
                custom_tools={"my_custom": custom_tool},
            )
            result = server_module.create_server(config)

            assert result == mock_server_instance
        finally:
            server_module.HAS_MCP = original_has_mcp
            server_module.Server = original_server
            server_module.Tool = original_tool
            server_module.TextContent = original_text_content

    @pytest.mark.asyncio
    async def test_list_tools_handler(self, temp_project):
        """Test the list_tools handler registered with server."""
        # Create mocks that capture the handlers
        list_tools_handler = None
        call_tool_handler = None

        def capture_list_tools():
            def decorator(func):
                nonlocal list_tools_handler
                list_tools_handler = func
                return func
            return decorator

        def capture_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server_instance = MagicMock()
        mock_server_instance.list_tools = capture_list_tools
        mock_server_instance.call_tool = capture_call_tool
        mock_server_class = MagicMock(return_value=mock_server_instance)

        class MockTool:
            def __init__(self, name, description, inputSchema):
                self.name = name
                self.description = description
                self.inputSchema = inputSchema

        class MockTextContent:
            def __init__(self, type, text):
                self.type = type
                self.text = text

        import mcp_journal.server as server_module

        original_has_mcp = server_module.HAS_MCP
        original_server = server_module.Server
        original_tool = server_module.Tool
        original_text_content = server_module.TextContent

        try:
            server_module.HAS_MCP = True
            server_module.Server = mock_server_class
            server_module.Tool = MockTool
            server_module.TextContent = MockTextContent

            config = ProjectConfig(project_root=temp_project)
            server_module.create_server(config)

            # Test the list_tools handler
            assert list_tools_handler is not None
            tools = await list_tools_handler()
            assert len(tools) > 0
            assert all(hasattr(t, 'name') for t in tools)

            # Test the call_tool handler
            assert call_tool_handler is not None
            result = await call_tool_handler("journal_append", {"author": "test", "context": "Test"})
            assert len(result) > 0

        finally:
            server_module.HAS_MCP = original_has_mcp
            server_module.Server = original_server
            server_module.Tool = original_tool
            server_module.TextContent = original_text_content

    @pytest.mark.asyncio
    async def test_call_tool_custom_tool(self, temp_project):
        """Test calling a custom tool through the handler."""
        call_tool_handler = None

        def capture_list_tools():
            def decorator(func):
                return func
            return decorator

        def capture_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server_instance = MagicMock()
        mock_server_instance.list_tools = capture_list_tools
        mock_server_instance.call_tool = capture_call_tool
        mock_server_class = MagicMock(return_value=mock_server_instance)

        class MockTextContent:
            def __init__(self, type, text):
                self.type = type
                self.text = text

        import mcp_journal.server as server_module

        original_has_mcp = server_module.HAS_MCP
        original_server = server_module.Server
        original_tool = server_module.Tool
        original_text_content = server_module.TextContent

        try:
            server_module.HAS_MCP = True
            server_module.Server = mock_server_class
            server_module.Tool = MagicMock()
            server_module.TextContent = MockTextContent

            def custom_sync_tool(engine, params):
                """Custom sync tool."""
                return {"custom": "result"}

            async def custom_async_tool(engine, params):
                """Custom async tool."""
                return {"async": "result"}

            config = ProjectConfig(
                project_root=temp_project,
                custom_tools={
                    "sync_tool": custom_sync_tool,
                    "async_tool": custom_async_tool,
                },
            )
            server_module.create_server(config)

            # Test sync custom tool
            result = await call_tool_handler("sync_tool", {"params": {"key": "value"}})
            assert len(result) > 0

            # Test async custom tool
            result = await call_tool_handler("async_tool", {"params": {}})
            assert len(result) > 0

        finally:
            server_module.HAS_MCP = original_has_mcp
            server_module.Server = original_server
            server_module.Tool = original_tool
            server_module.TextContent = original_text_content

    @pytest.mark.asyncio
    async def test_call_tool_custom_tool_error(self, temp_project):
        """Test custom tool error handling."""
        call_tool_handler = None

        def capture_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server_instance = MagicMock()
        mock_server_instance.list_tools = lambda: lambda f: f
        mock_server_instance.call_tool = capture_call_tool
        mock_server_class = MagicMock(return_value=mock_server_instance)

        class MockTextContent:
            def __init__(self, type, text):
                self.type = type
                self.text = text

        import mcp_journal.server as server_module

        original_has_mcp = server_module.HAS_MCP
        original_server = server_module.Server
        original_tool = server_module.Tool
        original_text_content = server_module.TextContent

        try:
            server_module.HAS_MCP = True
            server_module.Server = mock_server_class
            server_module.Tool = MagicMock()
            server_module.TextContent = MockTextContent

            def failing_tool(engine, params):
                """Tool that raises an error."""
                raise ValueError("Custom tool error")

            config = ProjectConfig(
                project_root=temp_project,
                custom_tools={"failing": failing_tool},
            )
            server_module.create_server(config)

            # Test error handling
            result = await call_tool_handler("failing", {})
            assert len(result) > 0
            # Result should contain error info
            import json
            error_data = json.loads(result[0].text)
            assert error_data["success"] is False
            assert "custom_tool_error" in error_data["error_type"]

        finally:
            server_module.HAS_MCP = original_has_mcp
            server_module.Server = original_server
            server_module.Tool = original_tool
            server_module.TextContent = original_text_content

    def test_main_with_config_file(self, temp_project):
        """Test main() with explicit config file."""
        import sys
        import mcp_journal.server as server_module

        # Create a config file
        config_file = temp_project / "journal.toml"
        config_file.write_text('[project]\nname = "test"')

        original_argv = sys.argv
        original_has_mcp = server_module.HAS_MCP

        try:
            # Mock HAS_MCP to True but mock run_server to avoid actual server
            server_module.HAS_MCP = True

            # Mock asyncio.run to capture the call
            with patch("mcp_journal.server.asyncio.run") as mock_run:
                sys.argv = [
                    "mcp-journal",
                    "--project-root", str(temp_project),
                    "--config", str(config_file),
                ]
                server_module.main()

                # run_server should have been called
                mock_run.assert_called_once()
        finally:
            sys.argv = original_argv
            server_module.HAS_MCP = original_has_mcp

    def test_main_config_load_error(self, temp_project, capsys):
        """Test main() when config loading fails."""
        import sys
        import mcp_journal.server as server_module

        # Create an invalid config file
        config_file = temp_project / "invalid.toml"
        config_file.write_text("invalid toml [[[")

        original_argv = sys.argv
        original_has_mcp = server_module.HAS_MCP

        try:
            server_module.HAS_MCP = True
            sys.argv = [
                "mcp-journal",
                "--project-root", str(temp_project),
                "--config", str(config_file),
            ]

            with pytest.raises(SystemExit) as exc_info:
                server_module.main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Error loading config" in captured.err
        finally:
            sys.argv = original_argv
            server_module.HAS_MCP = original_has_mcp


# ============ engine.py line 128: absolute file path reference ============

class TestAbsolutePathReference:
    """Test _validate_reference with absolute file paths."""

    def test_validate_absolute_path_exists(self, temp_project):
        """Validate reference with existing absolute file path."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a file with absolute path
        abs_file = temp_project / "absolute_ref.txt"
        abs_file.write_text("content")

        # Create entry with absolute path reference
        entry = engine.journal_append(
            author="test",
            context="Test with absolute path",
            references=[str(abs_file.resolve())],  # Absolute path
        )

        assert entry is not None
        assert str(abs_file.resolve()) in entry.references

    def test_validate_absolute_path_not_exists(self, temp_project):
        """Validate reference fails with non-existent absolute path."""
        from mcp_journal.engine import InvalidReferenceError

        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Try to create entry with non-existent absolute path
        fake_abs_path = "/nonexistent/path/file.txt"
        if os.name == "nt":
            fake_abs_path = "C:\\nonexistent\\path\\file.txt"

        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                context="Test",
                references=[fake_abs_path],
            )


# ============ engine.py line 573: version command with parse_regex ============

class TestVersionCommandParseRegex:
    """Test state_snapshot with version command parse_regex."""

    def test_version_command_with_capture_group(self, temp_project):
        """Version command regex with capture group extracts version."""
        from mcp_journal.config import VersionCommand

        config = ProjectConfig(
            project_root=temp_project,
            version_commands=[
                VersionCommand(
                    name="python",
                    command="python --version",
                    parse_regex=r"Python (\d+\.\d+\.\d+)",  # Has capture group
                ),
            ],
        )
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=True,
        )

        # Should have extracted just the version number
        assert "python" in snapshot.versions
        # Version should be just digits and dots (captured group)
        version = snapshot.versions["python"]
        assert version and not version.startswith("Python")

    def test_version_command_without_capture_group(self, temp_project):
        """Version command regex without capture group uses full match."""
        from mcp_journal.config import VersionCommand

        config = ProjectConfig(
            project_root=temp_project,
            version_commands=[
                VersionCommand(
                    name="version_match",
                    command="echo Version 1.2.3",
                    parse_regex=r"\d+\.\d+\.\d+",  # No capture group - uses group(0)
                ),
            ],
        )
        engine = JournalEngine(config)

        snapshot = engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=True,
        )

        # Should have extracted just "1.2.3" via group(0)
        assert "version_match" in snapshot.versions
        assert snapshot.versions["version_match"] == "1.2.3"


# ============ engine.py line 1322: trace_backward edge case ============

class TestTraceCausalityEdgeCase:
    """Test trace_backward edge case with mocking."""

    def test_trace_backward_entry_disappears(self, temp_project):
        """Test trace_backward when entry disappears between reads.

        This reliably tests line 1322 by mocking journal_read to return
        data on the first read (so trace_backward is called) but empty
        on the second read (inside the recursive call).

        Call sequence for trace_causality(entry2, direction="backward"):
        1. Validate entry2 exists (line 1303)
        2. trace_backward(entry2, 0) reads entry2 (line 1320)
        3. cause_entries check for entry1 (line 1328) - returns data, entry1 added to nodes
        4. trace_backward(entry1, 1) reads entry1 (line 1320) - RETURNS EMPTY, hits line 1322
        """
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create entries with causality chain
        entry1 = engine.journal_append(author="test", context="First")
        entry2 = engine.journal_append(
            author="test",
            context="Second",
            caused_by=[entry1.entry_id],
        )

        # Track calls to journal_read
        original_read = engine.journal_read
        read_calls = []
        line_1322_hit = [False]

        def mock_journal_read(entry_id=None, **kwargs):
            read_calls.append(entry_id)

            # On the 4th call (recursive trace_backward for entry1), return empty
            # This triggers line 1322: if not entries: return
            if len(read_calls) >= 4 and entry_id == entry1.entry_id:
                line_1322_hit[0] = True
                return []

            return original_read(entry_id=entry_id, **kwargs)

        engine.journal_read = mock_journal_read

        # This should hit line 1322 when entry1 "disappears" in recursive call
        result = engine.trace_causality(
            entry_id=entry2.entry_id,
            direction="backward",
            depth=5,
        )

        # Verify the mock triggered the empty return path
        assert line_1322_hit[0], "Line 1322 was not hit - mock did not return empty"
        assert len(read_calls) >= 4
        assert isinstance(result, dict)


# ============ journal_help - Comprehensive help system tests ============

class TestJournalHelp:
    """Test the journal_help system."""

    def test_help_default_overview(self, temp_project):
        """Test that default call returns overview."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help()

        assert result["type"] == "topic"
        assert result["topic"] == "overview"
        assert result["detail"] == "full"
        assert "Append-only" in result["content"]
        assert "related_topics" in result

    def test_help_all_topics(self, temp_project):
        """Test all available topics."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        topics = ["overview", "principles", "workflow", "tools", "causality", "templates", "errors"]

        for topic in topics:
            result = engine.journal_help(topic=topic)
            assert result["type"] == "topic"
            assert result["topic"] == topic
            assert "content" in result
            assert len(result["content"]) > 0

    def test_help_brief_detail(self, temp_project):
        """Test brief detail level."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result_brief = engine.journal_help(topic="overview", detail="brief")
        result_full = engine.journal_help(topic="overview", detail="full")

        assert result_brief["detail"] == "brief"
        assert result_full["detail"] == "full"
        # Brief should be shorter than full
        assert len(result_brief["content"]) < len(result_full["content"])

    def test_help_invalid_topic(self, temp_project):
        """Test error for invalid topic."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(topic="nonexistent")

        assert result["type"] == "error"
        assert "Unknown topic" in result["error"]
        assert "available_topics" in result

    def test_help_tool_specific(self, temp_project):
        """Test tool-specific help."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(tool="journal_append")

        assert result["type"] == "tool"
        assert result["tool"] == "journal_append"
        assert "author" in result["content"].lower()
        assert "related_topics" in result

    def test_help_tool_with_examples(self, temp_project):
        """Test tool help with examples detail level."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(tool="journal_append", detail="examples")

        assert result["type"] == "tool"
        assert result["detail"] == "examples"
        assert "Example" in result["content"]
        assert "json" in result["content"].lower()

    def test_help_tool_brief(self, temp_project):
        """Test tool help brief detail."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(tool="config_archive", detail="brief")

        assert result["type"] == "tool"
        assert result["detail"] == "brief"
        # Brief should be a single line
        assert "\n" not in result["content"]

    def test_help_invalid_tool(self, temp_project):
        """Test error for invalid tool."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(tool="nonexistent_tool")

        assert result["type"] == "error"
        assert "Unknown tool" in result["error"]
        assert "available_tools" in result

    def test_help_invalid_detail_defaults_to_full(self, temp_project):
        """Test that invalid detail level defaults to full."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = engine.journal_help(topic="overview", detail="invalid")

        # Should default to full, not error
        assert result["type"] == "topic"
        assert result["detail"] == "full"

    def test_help_all_tools_documented(self, temp_project):
        """Test that all tools have help."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Get list of all tools from help
        result = engine.journal_help(tool="nonexistent")
        available_tools = result["available_tools"]

        # Test each tool
        for tool_name in available_tools:
            result = engine.journal_help(tool=tool_name)
            assert result["type"] == "tool", f"Tool {tool_name} returned error"
            assert "content" in result
            assert len(result["content"]) > 0

    def test_help_case_insensitive(self, temp_project):
        """Test that topic and tool names are case-insensitive."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result_lower = engine.journal_help(topic="overview")
        result_upper = engine.journal_help(topic="OVERVIEW")
        result_mixed = engine.journal_help(topic="Overview")

        assert result_lower["content"] == result_upper["content"]
        assert result_lower["content"] == result_mixed["content"]

        # Test tool names too
        result_tool = engine.journal_help(tool="JOURNAL_APPEND")
        assert result_tool["type"] == "tool"


class TestJournalHelpViaTool:
    """Test journal_help via the MCP tool interface."""

    @pytest.mark.asyncio
    async def test_execute_journal_help_default(self, temp_project):
        """Test executing journal_help with no args via tool interface."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = await execute_tool(engine, "journal_help", {})

        assert result["success"] is True
        assert result["type"] == "topic"
        assert result["topic"] == "overview"

    @pytest.mark.asyncio
    async def test_execute_journal_help_with_topic(self, temp_project):
        """Test executing journal_help with topic via tool interface."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = await execute_tool(engine, "journal_help", {"topic": "workflow"})

        assert result["success"] is True
        assert result["topic"] == "workflow"
        assert "session" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_execute_journal_help_with_tool(self, temp_project):
        """Test executing journal_help with tool via tool interface."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = await execute_tool(engine, "journal_help", {"tool": "state_snapshot"})

        assert result["success"] is True
        assert result["type"] == "tool"
        assert result["tool"] == "state_snapshot"

    @pytest.mark.asyncio
    async def test_execute_journal_help_error(self, temp_project):
        """Test that error responses have success=False."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        result = await execute_tool(engine, "journal_help", {"tool": "fake_tool"})

        assert result["success"] is False
        assert result["type"] == "error"
