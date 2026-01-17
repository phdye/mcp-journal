"""Tests for the journal engine."""

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcp_journal.config import EntryTemplateConfig, ProjectConfig
from mcp_journal.engine import (
    DuplicateContentError,
    InvalidReferenceError,
    JournalEngine,
    TemplateNotFoundError,
    TemplateRequiredError,
)
from mcp_journal.models import EntryType


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


class TestJournalAppend:
    """Tests for journal_append."""

    def test_creates_journal_file(self, engine, temp_project):
        """First entry creates the journal file."""
        entry = engine.journal_append(
            author="test",
            context="Testing the journal",
        )

        assert entry.entry_id is not None
        assert entry.author == "test"
        assert entry.context == "Testing the journal"
        assert entry.entry_type == EntryType.ENTRY

        # Check file was created
        journal_dir = temp_project / "journal"
        journal_files = list(journal_dir.glob("*.md"))
        assert len(journal_files) == 1

    def test_sequential_entries_get_sequential_ids(self, engine):
        """Multiple entries on same day get sequential IDs."""
        entry1 = engine.journal_append(author="test", context="First")
        entry2 = engine.journal_append(author="test", context="Second")
        entry3 = engine.journal_append(author="test", context="Third")

        # Extract sequence numbers
        seq1 = int(entry1.entry_id.split("-")[-1])
        seq2 = int(entry2.entry_id.split("-")[-1])
        seq3 = int(entry3.entry_id.split("-")[-1])

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_all_fields_recorded(self, engine, temp_project):
        """All entry fields are recorded in markdown."""
        entry = engine.journal_append(
            author="test",
            context="The context",
            intent="The intent",
            action="The action",
            observation="The observation",
            analysis="The analysis",
            next_steps="The next steps",
        )

        journal_file = temp_project / "journal" / f"{entry.entry_id[:10]}.md"
        content = journal_file.read_text()

        assert "The context" in content
        assert "The intent" in content
        assert "The action" in content
        assert "The observation" in content
        assert "The analysis" in content
        assert "The next steps" in content

    def test_invalid_reference_rejected(self, engine):
        """Invalid references are rejected."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                context="Testing",
                references=["nonexistent-entry-id"],
            )


class TestJournalAmend:
    """Tests for journal_amend."""

    def test_creates_amendment_entry(self, engine):
        """Amendment creates a new entry marked as amendment."""
        original = engine.journal_append(author="test", context="Original")

        amendment = engine.journal_amend(
            references_entry=original.entry_id,
            correction="What was wrong",
            actual="What is true",
            impact="How this affects things",
            author="test",
        )

        assert amendment.entry_type == EntryType.AMENDMENT
        assert amendment.references_entry == original.entry_id

    def test_amending_nonexistent_entry_rejected(self, engine):
        """Cannot amend an entry that doesn't exist."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_amend(
                references_entry="1999-01-01-001",
                correction="Wrong",
                actual="Right",
                impact="None",
                author="test",
            )


class TestConfigArchive:
    """Tests for config_archive."""

    def test_archives_config_file(self, engine, temp_project):
        """Config file is copied to archive."""
        # Create a config file
        config_file = temp_project / "test.toml"
        config_file.write_text("[settings]\nvalue = 1")

        record = engine.config_archive(
            file_path=str(config_file),
            reason="Testing archive",
        )

        # Check archive exists
        archive_path = temp_project / record.archive_path
        assert archive_path.exists()
        assert archive_path.read_text() == "[settings]\nvalue = 1"

    def test_duplicate_content_rejected(self, engine, temp_project):
        """Archiving identical content fails."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[settings]\nvalue = 1")

        # First archive succeeds
        engine.config_archive(file_path=str(config_file), reason="First")

        # Second archive with same content fails
        with pytest.raises(DuplicateContentError):
            engine.config_archive(file_path=str(config_file), reason="Second")

    def test_modified_content_allowed(self, engine, temp_project):
        """Archiving modified content succeeds."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[settings]\nvalue = 1")

        engine.config_archive(file_path=str(config_file), reason="First")

        # Modify and archive again
        config_file.write_text("[settings]\nvalue = 2")
        record = engine.config_archive(file_path=str(config_file), reason="Second")

        assert record.archive_path is not None

    def test_index_updated(self, engine, temp_project):
        """INDEX.md is updated with archive record."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[settings]\nvalue = 1")

        engine.config_archive(file_path=str(config_file), reason="Testing")

        index_file = temp_project / "configs" / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "Testing" in content


class TestLogPreserve:
    """Tests for log_preserve."""

    def test_preserves_log_file(self, engine, temp_project):
        """Log file is moved to logs directory."""
        log_file = temp_project / "build.log"
        log_file.write_text("Build output here")

        record = engine.log_preserve(
            file_path=str(log_file),
            category="build",
            outcome="success",
        )

        # Original should be gone
        assert not log_file.exists()

        # Preserved file should exist
        preserved = temp_project / record.preserved_path
        assert preserved.exists()
        assert preserved.read_text() == "Build output here"

    def test_index_updated(self, engine, temp_project):
        """INDEX.md is updated with preservation record."""
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")

        engine.log_preserve(file_path=str(log_file), outcome="failure")

        index_file = temp_project / "logs" / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "failure" in content


class TestStateSnapshot:
    """Tests for state_snapshot."""

    def test_creates_snapshot_file(self, engine, temp_project):
        """Snapshot creates a JSON file."""
        snapshot = engine.state_snapshot(
            name="test-snapshot",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        snapshot_file = temp_project / snapshot.snapshot_path
        assert snapshot_file.exists()

        data = json.loads(snapshot_file.read_text())
        assert data["name"] == "test-snapshot"

    def test_captures_environment(self, engine, temp_project):
        """Snapshot captures environment variables."""
        snapshot = engine.state_snapshot(
            name="env-test",
            include_configs=False,
            include_env=True,
            include_versions=False,
        )

        snapshot_file = temp_project / snapshot.snapshot_path
        data = json.loads(snapshot_file.read_text())

        assert data["environment"] is not None
        assert "PATH" in data["environment"]

    def test_index_updated(self, engine, temp_project):
        """INDEX.md is updated with snapshot record."""
        engine.state_snapshot(name="indexed", include_env=False, include_versions=False)

        index_file = temp_project / "snapshots" / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "indexed" in content


class TestJournalSearch:
    """Tests for journal_search."""

    def test_finds_matching_entries(self, engine):
        """Search finds entries containing query."""
        engine.journal_append(author="alice", context="Working on feature X")
        engine.journal_append(author="bob", context="Debugging issue Y")
        engine.journal_append(author="alice", context="More work on feature X")

        results = engine.journal_search(query="feature X")

        assert len(results) == 2

    def test_filters_by_author(self, engine):
        """Search can filter by author."""
        engine.journal_append(author="alice", context="Alice's entry")
        engine.journal_append(author="bob", context="Bob's entry")

        results = engine.journal_search(query="entry", author="alice")

        assert len(results) == 1
        assert results[0]["author"] == "alice"


class TestIndexRebuild:
    """Tests for index_rebuild."""

    def test_dry_run_no_write(self, engine, temp_project):
        """Dry run doesn't write to index."""
        # Create some config files manually
        configs_dir = temp_project / "configs"
        configs_dir.mkdir(exist_ok=True)
        (configs_dir / "test.2024-01-01.toml").write_text("content")

        result = engine.index_rebuild(directory="configs", dry_run=True)

        assert result["action"] == "dry_run"
        assert result["files_found"] == 1

        # INDEX.md should not exist (dry run)
        index = configs_dir / "INDEX.md"
        assert not index.exists()

    def test_rebuild_creates_index(self, engine, temp_project):
        """Rebuild creates INDEX.md from files."""
        configs_dir = temp_project / "configs"
        configs_dir.mkdir(exist_ok=True)
        (configs_dir / "a.2024-01-01.toml").write_text("a")
        (configs_dir / "b.2024-01-02.toml").write_text("b")

        result = engine.index_rebuild(directory="configs", dry_run=False)

        assert result["action"] == "rebuilt"

        index = configs_dir / "INDEX.md"
        assert index.exists()
        content = index.read_text()
        assert "a.2024-01-01.toml" in content
        assert "b.2024-01-02.toml" in content


class TestJournalRead:
    """Tests for journal_read."""

    def test_read_by_entry_id(self, engine):
        """Can read a specific entry by ID."""
        entry = engine.journal_append(author="test", context="Test context")

        results = engine.journal_read(entry_id=entry.entry_id)

        assert len(results) == 1
        assert results[0]["entry_id"] == entry.entry_id
        assert results[0]["context"] == "Test context"

    def test_read_by_date(self, engine):
        """Can read all entries for a specific date."""
        engine.journal_append(author="test", context="First")
        engine.journal_append(author="test", context="Second")
        engine.journal_append(author="test", context="Third")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = engine.journal_read(date=today)

        assert len(results) == 3

    def test_read_with_date_range(self, engine):
        """Can read entries within a date range."""
        engine.journal_append(author="test", context="Entry")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = engine.journal_read(date_from=today, date_to=today)

        assert len(results) >= 1

    def test_read_summary_only(self, engine):
        """Can read entry summaries without full content."""
        entry = engine.journal_append(
            author="test",
            context="Long context here",
            analysis="Detailed analysis",
        )

        results = engine.journal_read(entry_id=entry.entry_id, include_content=False)

        assert len(results) == 1
        assert results[0]["entry_id"] == entry.entry_id
        # Summary should not include full content fields
        assert "context" not in results[0] or results[0].get("context") is None

    def test_read_nonexistent_entry(self, engine):
        """Reading nonexistent entry returns empty list."""
        results = engine.journal_read(entry_id="1999-01-01-999")

        assert len(results) == 0


class TestTimeline:
    """Tests for timeline."""

    def test_timeline_includes_entries(self, engine):
        """Timeline includes journal entries."""
        engine.journal_append(author="test", context="Entry 1")
        engine.journal_append(author="test", context="Entry 2")

        events = engine.timeline()

        # Timeline returns list of dicts with event_type as string
        entry_events = [e for e in events if e["event_type"] == "entry"]
        assert len(entry_events) >= 2

    def test_timeline_includes_configs(self, engine, temp_project):
        """Timeline includes archived configs."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        engine.config_archive(file_path=str(config_file), reason="Test")

        events = engine.timeline()

        config_events = [e for e in events if e["event_type"] == "config"]
        assert len(config_events) >= 1

    def test_timeline_includes_logs(self, engine, temp_project):
        """Timeline includes preserved logs."""
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")
        engine.log_preserve(file_path=str(log_file), outcome="success")

        events = engine.timeline()

        log_events = [e for e in events if e["event_type"] == "log"]
        assert len(log_events) >= 1

    def test_timeline_sorted_chronologically(self, engine):
        """Timeline events are sorted by timestamp."""
        engine.journal_append(author="test", context="First")
        engine.journal_append(author="test", context="Second")
        engine.journal_append(author="test", context="Third")

        events = engine.timeline()

        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_timeline_filter_by_type(self, engine, temp_project):
        """Can filter timeline by event type."""
        engine.journal_append(author="test", context="Entry")
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        engine.config_archive(file_path=str(config_file), reason="Test")

        events = engine.timeline(event_types=["entry"])

        # Should only have entry events, not config events
        for e in events:
            assert e["event_type"] == "entry"

    def test_timeline_with_limit(self, engine):
        """Can limit number of timeline events."""
        for i in range(5):
            engine.journal_append(author="test", context=f"Entry {i}")

        events = engine.timeline(limit=3)

        assert len(events) == 3


class TestConfigDiff:
    """Tests for config_diff."""

    def test_diff_identical_files(self, engine, temp_project):
        """Diff of identical files is empty."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        record = engine.config_archive(file_path=str(config_file), reason="First")

        result = engine.config_diff(
            path_a=record.archive_path,
            path_b=record.archive_path,
        )

        # Returns dict with diff info
        assert result["identical"] is True
        assert result["additions"] == 0
        assert result["deletions"] == 0

    def test_diff_different_files(self, engine, temp_project):
        """Diff shows changes between files."""
        config_file = temp_project / "test.toml"

        config_file.write_text("[test]\nvalue = 1")
        record1 = engine.config_archive(file_path=str(config_file), reason="First")

        # Small delay to ensure different timestamp
        time.sleep(1.1)

        config_file.write_text("[test]\nvalue = 2")
        record2 = engine.config_archive(file_path=str(config_file), reason="Second")

        result = engine.config_diff(
            path_a=record1.archive_path,
            path_b=record2.archive_path,
        )

        # Returns dict with diff info
        assert result["identical"] is False
        diff = result["diff"]
        assert "value = 1" in diff or "-" in diff
        assert "value = 2" in diff or "+" in diff

    def test_diff_current_file(self, engine, temp_project):
        """Can diff against current (non-archived) file."""
        config_file = temp_project / "test.toml"

        config_file.write_text("[test]\nvalue = 1")
        record = engine.config_archive(file_path=str(config_file), reason="Archived")

        config_file.write_text("[test]\nvalue = 2")

        result = engine.config_diff(
            path_a=record.archive_path,
            path_b=f"current:{config_file}",
        )

        assert result is not None
        assert "diff" in result


class TestSessionHandoff:
    """Tests for session_handoff."""

    def test_handoff_includes_entries(self, engine):
        """Handoff summary includes journal entries."""
        engine.journal_append(
            author="test",
            context="Working on feature",
            next_steps="Continue tomorrow",
        )

        result = engine.session_handoff()

        # Returns dict with content key containing markdown or structured data
        assert "content" in result
        content = result["content"]
        assert "Working on feature" in content or "feature" in str(content).lower()

    def test_handoff_markdown_format(self, engine):
        """Handoff in markdown format includes headers."""
        engine.journal_append(author="test", context="Test entry")

        result = engine.session_handoff(format="markdown")

        assert result["format"] == "markdown"
        content = result["content"]
        assert "#" in content  # Markdown headers

    def test_handoff_json_format(self, engine):
        """Handoff in JSON format returns structured data."""
        engine.journal_append(author="test", context="Test entry")

        result = engine.session_handoff(format="json")

        assert result["format"] == "json"
        content = result["content"]
        # JSON format returns dict directly, not JSON string
        assert isinstance(content, dict)
        assert "entries" in content or "summary" in content

    def test_handoff_includes_config_changes(self, engine, temp_project):
        """Handoff includes config change summary."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        engine.config_archive(file_path=str(config_file), reason="Changed setting")

        result = engine.session_handoff(include_configs=True)

        content = str(result["content"])
        assert "config" in content.lower() or "test.toml" in content

    def test_handoff_includes_log_summary(self, engine, temp_project):
        """Handoff includes log outcome summary."""
        log_file = temp_project / "build.log"
        log_file.write_text("Build completed")
        engine.log_preserve(file_path=str(log_file), category="build", outcome="success")

        result = engine.session_handoff(include_logs=True)

        content = str(result["content"])
        assert "success" in content.lower() or "log" in content.lower()


class TestTraceCausality:
    """Tests for trace_causality."""

    def test_trace_forward_causality(self, engine):
        """Can trace what an entry caused."""
        entry1 = engine.journal_append(
            author="test",
            context="Root cause",
            outcome="failure",
        )

        entry2 = engine.journal_append(
            author="test",
            context="Consequence",
            caused_by=[entry1.entry_id],
        )

        graph = engine.trace_causality(entry_id=entry1.entry_id, direction="forward")

        assert entry2.entry_id in str(graph)

    def test_trace_backward_causality(self, engine):
        """Can trace what caused an entry."""
        entry1 = engine.journal_append(
            author="test",
            context="Root cause",
        )

        entry2 = engine.journal_append(
            author="test",
            context="Effect",
            caused_by=[entry1.entry_id],
        )

        graph = engine.trace_causality(entry_id=entry2.entry_id, direction="backward")

        assert entry1.entry_id in str(graph)

    def test_trace_both_directions(self, engine):
        """Can trace causality in both directions."""
        entry1 = engine.journal_append(author="test", context="First")
        entry2 = engine.journal_append(
            author="test",
            context="Middle",
            caused_by=[entry1.entry_id],
        )
        entry3 = engine.journal_append(
            author="test",
            context="Last",
            caused_by=[entry2.entry_id],
        )

        graph = engine.trace_causality(entry_id=entry2.entry_id, direction="both")

        # Should find both upstream and downstream
        graph_str = str(graph)
        assert entry1.entry_id in graph_str or "causes" in graph_str
        assert entry3.entry_id in graph_str or "caused_by" in graph_str


class TestTemplates:
    """Tests for template functionality."""

    @pytest.fixture
    def config_with_templates(self, temp_project):
        """Create config with templates."""
        templates = {
            "build_start": EntryTemplateConfig(
                name="build_start",
                description="Starting a build",
                context="Starting {stage} build",
                intent="Build {stage} with config {config}",
                required_fields=["stage", "config"],
            ),
            "build_complete": EntryTemplateConfig(
                name="build_complete",
                description="Build completed",
                observation="Build exit code: {exit_code}",
                required_fields=["exit_code"],
                default_outcome="success",
            ),
        }
        return ProjectConfig(
            project_name="test-with-templates",
            project_root=temp_project,
            templates=templates,
        )

    @pytest.fixture
    def engine_with_templates(self, config_with_templates):
        """Engine with template support."""
        return JournalEngine(config_with_templates)

    def test_list_templates(self, engine_with_templates):
        """Can list available templates."""
        templates = engine_with_templates.list_templates()

        assert len(templates) == 2
        names = [t["name"] for t in templates]
        assert "build_start" in names
        assert "build_complete" in names

    def test_get_template(self, engine_with_templates):
        """Can get template details."""
        template = engine_with_templates.get_template("build_start")

        assert template is not None
        assert template["name"] == "build_start"
        assert "stage" in template["required_fields"]
        assert "config" in template["required_fields"]

    def test_get_nonexistent_template(self, engine_with_templates):
        """Getting nonexistent template returns None."""
        template = engine_with_templates.get_template("nonexistent")

        assert template is None

    def test_append_with_template(self, engine_with_templates):
        """Can append entry using template."""
        entry = engine_with_templates.journal_append(
            author="test",
            template="build_start",
            template_values={"stage": "stage1", "config": "bootstrap.toml"},
        )

        assert entry.template == "build_start"
        assert "stage1" in entry.context
        assert "bootstrap.toml" in entry.intent

    def test_template_missing_required_fields(self, engine_with_templates):
        """Template with missing required fields raises error."""
        with pytest.raises(ValueError, match="Missing required"):
            engine_with_templates.journal_append(
                author="test",
                template="build_start",
                template_values={"stage": "stage1"},  # Missing 'config'
            )

    def test_template_not_found(self, engine_with_templates):
        """Using nonexistent template raises error."""
        with pytest.raises(TemplateNotFoundError):
            engine_with_templates.journal_append(
                author="test",
                template="nonexistent",
                template_values={},
            )

    @pytest.fixture
    def config_require_templates(self, temp_project):
        """Config that requires templates."""
        templates = {
            "required_template": EntryTemplateConfig(
                name="required_template",
                description="The only template",
                context="Template context",
            ),
        }
        return ProjectConfig(
            project_name="test-require-templates",
            project_root=temp_project,
            templates=templates,
            require_templates=True,
        )

    @pytest.fixture
    def engine_require_templates(self, config_require_templates):
        """Engine that requires templates."""
        return JournalEngine(config_require_templates)

    def test_require_templates_enforced(self, engine_require_templates):
        """When require_templates=True, entries without template are rejected."""
        with pytest.raises(TemplateRequiredError):
            engine_require_templates.journal_append(
                author="test",
                context="No template",
            )

    def test_require_templates_with_template_works(self, engine_require_templates):
        """When require_templates=True, entries with template are accepted."""
        entry = engine_require_templates.journal_append(
            author="test",
            template="required_template",
        )

        assert entry.template == "required_template"


class TestCausalityFields:
    """Tests for causality field recording."""

    def test_causality_fields_recorded(self, engine, temp_project):
        """Causality fields are recorded in entries."""
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        config_record = engine.config_archive(file_path=str(config_file), reason="Test")

        entry = engine.journal_append(
            author="test",
            context="Testing",
            config_used=config_record.archive_path,
            outcome="success",
        )

        assert entry.config_used == config_record.archive_path
        assert entry.outcome == "success"

    def test_caused_by_validated(self, engine):
        """caused_by entries must exist."""
        with pytest.raises(InvalidReferenceError):
            engine.journal_append(
                author="test",
                context="Testing",
                caused_by=["nonexistent-entry"],
            )

    def test_valid_caused_by_accepted(self, engine):
        """Valid caused_by references are accepted."""
        entry1 = engine.journal_append(author="test", context="First")

        entry2 = engine.journal_append(
            author="test",
            context="Second",
            caused_by=[entry1.entry_id],
        )

        assert entry1.entry_id in entry2.caused_by
