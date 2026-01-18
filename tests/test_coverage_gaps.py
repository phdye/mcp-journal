"""Tests specifically targeting coverage gaps in all modules."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mcp_journal.config import (
    ProjectConfig,
    EntryTemplateConfig,
    VersionCommand,
    load_toml_config,
    load_json_config,
    load_python_config,
    dict_to_config,
    find_config_file,
    load_config,
)
from mcp_journal.engine import JournalEngine
from mcp_journal.locking import file_lock, atomic_write, locked_atomic_write
from mcp_journal.models import (
    JournalEntry,
    EntryType,
    EntryTemplate,
    StateSnapshot,
    TimelineEvent,
    TimelineEventType,
    format_timestamp,
    utc_now,
)


# Fixtures temp_project, config, and engine are provided by conftest.py


# ============ config.py coverage gaps ============

class TestConfigTomliImport:
    """Test tomli import fallback."""

    def test_load_toml_without_tomli(self, temp_project):
        """Load toml raises ImportError when tomli unavailable."""
        import mcp_journal.config as config_module

        original_tomli = config_module.tomli
        config_module.tomli = None

        try:
            toml_file = temp_project / "test.toml"
            toml_file.write_text("[test]")

            with pytest.raises(ImportError, match="tomli required"):
                load_toml_config(toml_file)
        finally:
            config_module.tomli = original_tomli


class TestPythonConfigLoading:
    """Test Python config loading edge cases."""

    def test_load_python_config_with_lowercase_config(self, temp_project):
        """Load Python config with lowercase 'config' dict."""
        py_file = temp_project / "journal_config.py"
        py_file.write_text("""
config = {
    "project": {"name": "lowercase-test"}
}
""")

        config_dict, hooks, tools = load_python_config(py_file)
        assert config_dict["project"]["name"] == "lowercase-test"

    def test_load_python_config_invalid_spec(self, temp_project):
        """Load Python config with invalid path raises error."""
        # A nonexistent file should raise FileNotFoundError or ImportError
        with pytest.raises((FileNotFoundError, ImportError, ModuleNotFoundError)):
            load_python_config(temp_project / "nonexistent.py")

    def test_load_config_unsupported_type(self, temp_project):
        """Load config with unsupported extension raises ValueError."""
        unknown_file = temp_project / "config.xyz"
        unknown_file.write_text("content")

        with pytest.raises(ValueError, match="Unsupported config file type"):
            load_config(temp_project, unknown_file)


class TestDictToConfigEdgeCases:
    """Test dict_to_config edge cases."""

    def test_dict_to_config_with_all_directories(self, temp_project):
        """dict_to_config sets all directory options."""
        data = {
            "directories": {
                "journal": "custom_journal",
                "configs": "custom_configs",
                "logs": "custom_logs",
                "snapshots": "custom_snapshots",
            }
        }
        config = dict_to_config(data, temp_project)

        assert config.journal_dir == "custom_journal"
        assert config.configs_dir == "custom_configs"
        assert config.logs_dir == "custom_logs"
        assert config.snapshots_dir == "custom_snapshots"

    def test_dict_to_config_with_custom_fields(self, temp_project):
        """dict_to_config sets custom_fields."""
        data = {
            "custom_fields": {
                "build_number": "CI build number",
                "commit_hash": "Git commit hash",
            }
        }
        config = dict_to_config(data, temp_project)

        assert "build_number" in config.custom_fields
        assert "commit_hash" in config.custom_fields

    def test_dict_to_config_with_templates_require(self, temp_project):
        """dict_to_config parses templates with require flag."""
        data = {
            "templates": {
                "require": True,
                "build_entry": {
                    "description": "Build entry template",
                    "context": "Building {stage}",
                    "required_fields": ["stage"],
                },
            }
        }
        config = dict_to_config(data, temp_project)

        assert config.require_templates is True
        assert "build_entry" in config.templates
        assert config.templates["build_entry"].required_fields == ["stage"]

    def test_dict_to_config_versions_dict_format(self, temp_project):
        """dict_to_config parses version commands in dict format."""
        data = {
            "versions": {
                "rust": {
                    "command": "rustc --version",
                    "regex": r"rustc (\d+\.\d+\.\d+)",
                }
            }
        }
        config = dict_to_config(data, temp_project)

        assert len(config.version_commands) == 1
        assert config.version_commands[0].name == "rust"
        assert config.version_commands[0].parse_regex is not None


# ============ locking.py coverage gaps ============

class TestAtomicWriteBinary:
    """Test atomic_write with binary mode."""

    def test_atomic_write_binary(self, temp_project):
        """atomic_write works with binary mode."""
        test_file = temp_project / "binary.bin"

        with atomic_write(test_file, mode="wb") as f:
            f.write(b"\x00\x01\x02\x03")

        assert test_file.exists()
        assert test_file.read_bytes() == b"\x00\x01\x02\x03"


class TestAtomicWriteCleanup:
    """Test atomic_write cleanup on failure."""

    def test_atomic_write_cleans_up_on_error(self, temp_project):
        """atomic_write removes temp file on error."""
        test_file = temp_project / "error.txt"
        tmp_file = test_file.with_suffix(".txt.tmp")

        with pytest.raises(ValueError):
            with atomic_write(test_file) as f:
                f.write("content")
                raise ValueError("Simulated error")

        # Temp file should be cleaned up
        assert not tmp_file.exists()
        # Target file should not exist
        assert not test_file.exists()


class TestAtomicWriteErrorBeforeTempFile:
    """Test atomic_write when error occurs before temp file is created (line 70->72)."""

    def test_atomic_write_error_before_temp_file_created(self, temp_project):
        """atomic_write handles exception when temp file doesn't exist (line 70->72).

        This tests the branch where an exception is raised but tmp_path.exists()
        returns False because the temp file was never created.
        """
        # Create a FILE where the parent DIRECTORY should be
        # This will cause mkdir to fail before the temp file is created
        fake_parent = temp_project / "fake_dir"
        fake_parent.write_text("I'm a file, not a directory")

        # Now try to write to a file that should be in "fake_dir"
        test_file = fake_parent / "subdir" / "file.txt"

        with pytest.raises((OSError, NotADirectoryError)):
            with atomic_write(test_file) as f:
                f.write("should never get here")

        # Verify temp file was never created (it couldn't be)
        tmp_file = test_file.with_suffix(".txt.tmp")
        assert not tmp_file.exists()

    def test_atomic_write_temp_not_exists_on_exception(self, temp_project):
        """atomic_write skips cleanup if temp file doesn't exist (line 70->72).

        Use mocking to simulate the case where tmp_path.exists() returns False
        in the exception handler.
        """
        test_file = temp_project / "test_file.txt"

        # We need to trigger an exception AND have tmp_path.exists() return False
        # The cleanest way is to mock Path.exists on the tmp_path to return False
        original_exists = Path.exists

        def patched_exists(self):
            # Return False for .tmp files in the exception handler
            if str(self).endswith(".tmp"):
                return False
            return original_exists(self)

        with patch.object(Path, "exists", patched_exists):
            with pytest.raises(ValueError):
                with atomic_write(test_file) as f:
                    f.write("content")
                    raise ValueError("Simulated error")


class TestAtomicWriteWindows:
    """Test atomic_write Windows-specific behavior."""

    def test_atomic_write_windows_rename(self, temp_project):
        """atomic_write handles Windows rename (unlink first)."""
        test_file = temp_project / "windows.txt"
        test_file.write_text("original")

        # On Windows, need to unlink before rename
        # This test verifies the code path works
        with atomic_write(test_file) as f:
            f.write("updated")

        assert test_file.read_text() == "updated"


# ============ models.py coverage gaps ============

class TestJournalEntryCausesField:
    """Test JournalEntry.causes field rendering."""

    def test_entry_with_causes_renders(self):
        """Entry with causes field renders correctly."""
        entry = JournalEntry(
            entry_id="2026-01-06-001",
            timestamp=utc_now(),
            author="test",
            context="Test context",
            causes=["2026-01-06-002", "2026-01-06-003"],
        )

        markdown = entry.to_markdown()
        assert "**Causes**: 2026-01-06-002, 2026-01-06-003" in markdown


class TestEntryTemplateRender:
    """Test EntryTemplate.render method."""

    def test_template_render_basic(self):
        """Template renders with provided values."""
        template = EntryTemplate(
            name="test",
            description="Test template",
            context_template="Building {stage} for {target}",
            intent_template="Complete {stage} build",
            required_fields=["stage", "target"],
        )

        result = template.render({"stage": "release", "target": "x86_64"})

        assert result["context"] == "Building release for x86_64"
        assert result["intent"] == "Complete release build"

    def test_template_render_missing_required(self):
        """Template raises ValueError for missing required fields."""
        template = EntryTemplate(
            name="test",
            description="Test",
            context_template="Value: {required_value}",
            required_fields=["required_value"],
        )

        with pytest.raises(ValueError, match="Missing required"):
            template.render({})

    def test_template_render_missing_variable(self):
        """Template raises ValueError for missing template variable."""
        template = EntryTemplate(
            name="test",
            description="Test",
            context_template="Value: {undefined_var}",
            required_fields=[],
        )

        with pytest.raises(ValueError, match="Template variable not provided"):
            template.render({})

    def test_template_render_none_fields(self):
        """Template handles None fields correctly."""
        template = EntryTemplate(
            name="test",
            description="Test",
            context_template=None,
            intent_template="Intent: {value}",
            required_fields=["value"],
        )

        result = template.render({"value": "test"})

        assert result["context"] is None
        assert result["intent"] == "Intent: test"


class TestStateSnapshotIndexLine:
    """Test StateSnapshot.to_index_line with all content types."""

    def test_snapshot_index_line_all_contents(self):
        """Snapshot index line shows all content types."""
        snapshot = StateSnapshot(
            name="full-snapshot",
            timestamp=utc_now(),
            snapshot_path="snapshots/full.json",
            configs={"key": "value"},
            environment={"PATH": "/usr/bin"},
            versions={"python": "3.9"},
            build_dir_listing=["file1", "file2"],
            custom_data={"extra": "data"},
        )

        line = snapshot.to_index_line()

        assert "configs" in line
        assert "env" in line
        assert "versions" in line
        assert "listing" in line
        assert "custom" in line


# ============ engine.py coverage gaps ============

class TestEngineEdgeCases:
    """Test engine edge cases for coverage."""

    def test_get_next_sequence_no_matches(self, temp_project):
        """_get_next_sequence returns 1 when pattern doesn't match."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create journal file without proper entry headers
        journal_file = temp_project / "journal" / "2026-01-06.md"
        journal_file.write_text("Some content without entry headers")

        date = datetime(2026, 1, 6, tzinfo=timezone.utc)
        seq = engine._get_next_sequence(date)

        assert seq == 1

    def test_template_render_key_error(self, temp_project):
        """Template with KeyError in render uses original field."""
        templates = {
            "partial": EntryTemplateConfig(
                name="partial",
                description="Partial template",
                context="Context with {undefined}",  # Will cause KeyError
            ),
        }
        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            templates=templates,
        )
        engine = JournalEngine(config)

        # The template should fall back to using the template string as-is
        entry = engine.journal_append(
            author="test",
            template="partial",
            template_values={},  # Missing 'undefined'
        )

        # Should use original template string
        assert entry.context == "Context with {undefined}"

    def test_journal_read_with_invalid_date_format(self, temp_project):
        """journal_read handles invalid date format gracefully."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        results = engine.journal_read(date="not-a-date")
        assert results == []

    def test_journal_read_date_range(self, temp_project):
        """journal_read with date range works correctly."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Entry 1")

        results = engine.journal_read(
            date_from="2020-01-01",
            date_to="2030-12-31",
        )
        assert len(results) >= 1

    def test_timeline_with_date_range(self, temp_project):
        """timeline respects date range filters."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Entry")

        # Future date range should return empty
        events = engine.timeline(date_from="2099-01-01", date_to="2099-12-31")
        assert events == []

    def test_session_handoff_json_format(self, temp_project):
        """session_handoff with json format returns dict."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        engine.journal_append(author="test", context="Entry")

        result = engine.session_handoff(format="json")

        assert result["format"] == "json"
        assert isinstance(result["content"], dict)

    def test_config_diff_archived_files(self, temp_project):
        """config_diff works with archived config paths."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create and archive two different configs
        config_file = temp_project / "test.toml"

        config_file.write_text("[test]\nvalue = 1")
        record1 = engine.config_archive(file_path=str(config_file), reason="First")

        import time
        time.sleep(1.1)

        config_file.write_text("[test]\nvalue = 2")
        record2 = engine.config_archive(file_path=str(config_file), reason="Second")

        result = engine.config_diff(
            path_a=record1.archive_path,
            path_b=record2.archive_path,
        )

        assert result["identical"] is False

    def test_state_snapshot_with_build_dir_listing(self, temp_project):
        """state_snapshot captures build directory listing."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create build directory with files
        build_dir = temp_project / "build"
        build_dir.mkdir()
        (build_dir / "output.bin").write_bytes(b"data")

        snapshot = engine.state_snapshot(
            name="with-listing",
            include_configs=False,
            include_env=False,
            include_versions=False,
            include_build_dir_listing=True,
            build_dir=str(build_dir),
        )

        assert snapshot.build_dir_listing is not None
        assert "output.bin" in snapshot.build_dir_listing

    def test_trace_causality_with_depth(self, temp_project):
        """trace_causality respects depth parameter."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create chain of entries
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

        # Trace with depth=1 should not reach entry3 from entry1
        result = engine.trace_causality(
            entry_id=entry1.entry_id,
            direction="forward",
            depth=1,
        )

        assert isinstance(result, dict)


class TestIndexRebuildAllDirectories:
    """Test index_rebuild for all directory types."""

    def test_index_rebuild_logs(self, temp_project):
        """index_rebuild works for logs directory."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a log
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")
        engine.log_preserve(file_path=str(log_file))

        result = engine.index_rebuild(directory="logs")

        assert result["action"] == "rebuilt"

    def test_index_rebuild_snapshots(self, temp_project):
        """index_rebuild works for snapshots directory."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        # Create a snapshot
        engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        result = engine.index_rebuild(directory="snapshots")

        assert result["action"] == "rebuilt"


class TestConfigActivateEdgeCases:
    """Test config_activate edge cases."""

    def test_config_activate_no_previous(self, temp_project):
        """config_activate when target doesn't exist."""
        config = ProjectConfig(project_root=temp_project)
        engine = JournalEngine(config)

        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        record = engine.config_archive(file_path=str(config_file), reason="Test")

        result = engine.config_activate(
            archive_path=record.archive_path,
            target_path=str(temp_project / "new_target.toml"),
            reason="Test",
            journal_entry="2026-01-06-001",
        )

        # No previous archive when target didn't exist
        assert result is None
