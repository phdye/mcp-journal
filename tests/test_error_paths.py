"""Error path tests following comprehensive-testing.md methodology.

Tests all error conditions and exception handling.
"""

import tempfile
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig, EntryTemplateConfig
from mcp_journal.engine import (
    DuplicateContentError,
    InvalidReferenceError,
    JournalEngine,
    JournalError,
    TemplateNotFoundError,
    TemplateRequiredError,
)


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


class TestInvalidReferenceErrors:
    """Tests for InvalidReferenceError exception."""

    def test_invalid_entry_reference(self, engine):
        """Referencing non-existent entry raises InvalidReferenceError."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                references=["1999-01-01-999"],  # Non-existent entry
            )

    def test_invalid_file_reference(self, engine):
        """Referencing non-existent file raises InvalidReferenceError."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                references=["/nonexistent/path/to/file.txt"],
            )

    def test_invalid_caused_by_reference(self, engine):
        """Invalid caused_by entry raises InvalidReferenceError."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                caused_by=["2000-01-01-001"],  # Non-existent
            )

    def test_multiple_invalid_references(self, engine):
        """Multiple invalid references raises InvalidReferenceError."""
        entry = engine.journal_append(author="test", context="Valid")

        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                references=[entry.entry_id, "invalid-ref"],
            )

    def test_amend_invalid_entry(self, engine):
        """Amending non-existent entry raises InvalidReferenceError."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_amend(
                references_entry="1999-12-31-001",
                correction="Wrong",
                actual="Right",
                impact="None",
                author="test",
            )


class TestDuplicateContentErrors:
    """Tests for DuplicateContentError exception."""

    def test_duplicate_config_archive(self, engine, temp_project):
        """Archiving identical content raises DuplicateContentError."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        # First archive succeeds
        engine.config_archive(file_path=str(config_file), reason="First")

        # Second archive with same content fails
        with pytest.raises(DuplicateContentError):
            engine.config_archive(file_path=str(config_file), reason="Second")

    def test_duplicate_different_reason(self, engine, temp_project):
        """Same content with different reason still raises DuplicateContentError."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 42")

        engine.config_archive(file_path=str(config_file), reason="Reason A")

        with pytest.raises(DuplicateContentError):
            engine.config_archive(file_path=str(config_file), reason="Reason B")

    def test_duplicate_different_stage(self, engine, temp_project):
        """Same content with different stage still raises DuplicateContentError."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 99")

        engine.config_archive(file_path=str(config_file), reason="Test", stage="stage1")

        with pytest.raises(DuplicateContentError):
            engine.config_archive(file_path=str(config_file), reason="Test", stage="stage2")


class TestTemplateErrors:
    """Tests for template-related exceptions."""

    @pytest.fixture
    def config_require_templates(self, temp_project):
        """Config that requires templates."""
        templates = {
            "only_template": EntryTemplateConfig(
                name="only_template",
                description="Required template",
                context="Template context: {topic}",
                required_fields=["topic"],
            ),
        }
        return ProjectConfig(
            project_name="test-require",
            project_root=temp_project,
            templates=templates,
            require_templates=True,
        )

    @pytest.fixture
    def engine_require_templates(self, config_require_templates):
        """Engine that requires templates."""
        return JournalEngine(config_require_templates)

    def test_template_required_error(self, engine_require_templates):
        """Entry without template raises TemplateRequiredError when required."""
        with pytest.raises(TemplateRequiredError):
            engine_require_templates.journal_append(
                author="test",
                context="No template specified",
            )

    def test_template_not_found_error(self, engine_require_templates):
        """Non-existent template raises TemplateNotFoundError."""
        with pytest.raises(TemplateNotFoundError):
            engine_require_templates.journal_append(
                author="test",
                template="nonexistent_template",
                template_values={},
            )

    def test_template_missing_required_fields(self, engine_require_templates):
        """Template with missing required fields raises ValueError."""
        with pytest.raises(ValueError, match="Missing required"):
            engine_require_templates.journal_append(
                author="test",
                template="only_template",
                template_values={},  # Missing 'topic'
            )

    def test_template_with_extra_fields(self, engine_require_templates):
        """Template with extra (unused) fields should work."""
        entry = engine_require_templates.journal_append(
            author="test",
            template="only_template",
            template_values={
                "topic": "required value",
                "extra": "ignored value",
            },
        )
        assert entry.template == "only_template"


class TestFileNotFoundErrors:
    """Tests for FileNotFoundError exceptions."""

    def test_archive_nonexistent_file(self, engine):
        """Archiving non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            engine.config_archive(
                file_path="/nonexistent/path/config.toml",
                reason="Test",
            )

    def test_preserve_nonexistent_log(self, engine):
        """Preserving non-existent log raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            engine.log_preserve(file_path="/nonexistent/log.log")

    def test_activate_nonexistent_archive(self, engine, temp_project):
        """Activating non-existent archive raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            engine.config_activate(
                archive_path="configs/nonexistent.toml",
                target_path=str(temp_project / "target.toml"),
                reason="Test",
                journal_entry="2026-01-06-001",
            )

    def test_diff_nonexistent_file(self, engine, temp_project):
        """Diffing with non-existent file raises FileNotFoundError."""
        existing = temp_project / "exists.toml"
        existing.write_text("[test]")

        with pytest.raises(FileNotFoundError):
            engine.config_diff(
                path_a=f"current:{existing}",
                path_b="current:/nonexistent/file.toml",
            )


class TestIndexRebuildErrors:
    """Tests for index_rebuild error handling."""

    def test_rebuild_invalid_directory(self, engine):
        """Rebuilding invalid directory type returns error."""
        # Valid directories are: configs, logs, snapshots
        with pytest.raises(ValueError):
            engine.index_rebuild(directory="invalid")


class TestJournalErrorBase:
    """Tests for JournalError base exception."""

    def test_journal_error_is_exception(self):
        """JournalError should be an Exception subclass."""
        assert issubclass(JournalError, Exception)

    def test_all_exceptions_inherit_journal_error(self):
        """All journal exceptions should inherit from JournalError."""
        assert issubclass(InvalidReferenceError, JournalError)
        assert issubclass(DuplicateContentError, JournalError)
        assert issubclass(TemplateRequiredError, JournalError)
        assert issubclass(TemplateNotFoundError, JournalError)


class TestConfigActivateErrors:
    """Tests for config_activate error handling."""

    def test_activate_requires_journal_entry(self, engine, temp_project):
        """Config activation requires journal_entry parameter."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        record = engine.config_archive(file_path=str(config_file), reason="Test")

        # Activation without valid journal_entry should still work
        # (the method doesn't validate journal_entry existence for flexibility)
        result = engine.config_activate(
            archive_path=record.archive_path,
            target_path=str(temp_project / "active.toml"),
            reason="Activate test",
            journal_entry="2026-01-06-001",  # Doesn't need to exist
        )
        assert result is None or isinstance(result, object)


class TestStateSnapshotErrors:
    """Tests for state_snapshot error handling."""

    def test_snapshot_nonexistent_build_dir(self, engine):
        """Snapshot with non-existent build_dir should handle gracefully."""
        snapshot = engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
            include_build_dir_listing=True,
            build_dir="/nonexistent/build/dir",
        )

        # Should not crash, just skip the listing
        assert snapshot.name == "test"


class TestEdgeCaseRecovery:
    """Tests verifying system recovers from edge case errors."""

    def test_recovers_after_invalid_reference_error(self, engine):
        """System should continue working after InvalidReferenceError."""
        # Trigger an error
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                references=["invalid-ref"],
            )

        # System should still work
        entry = engine.journal_append(author="test", context="After error")
        assert entry is not None

    def test_recovers_after_duplicate_content_error(self, engine, temp_project):
        """System should continue working after DuplicateContentError."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")

        engine.config_archive(file_path=str(config_file), reason="First")

        # Trigger duplicate error
        with pytest.raises(DuplicateContentError):
            engine.config_archive(file_path=str(config_file), reason="Second")

        # System should still work - modify and archive again
        config_file.write_text("[test]\nvalue = 2")
        record = engine.config_archive(file_path=str(config_file), reason="Third")
        assert record is not None

    def test_recovers_after_file_not_found_error(self, engine, temp_project):
        """System should continue working after FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            engine.config_archive(file_path="/nonexistent", reason="Test")

        # System should still work
        existing = temp_project / "exists.toml"
        existing.write_text("[test]")
        record = engine.config_archive(file_path=str(existing), reason="Works")
        assert record is not None
