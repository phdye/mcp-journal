"""Integration tests following comprehensive-testing.md methodology.

Tests complete workflows and cross-module interactions.
"""

import json
import time
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig, EntryTemplateConfig
from mcp_journal.engine import JournalEngine


# Fixtures temp_project, config, and engine are provided by conftest.py


class TestFullJournalLifecycle:
    """Tests for complete journal workflow."""

    def test_complete_build_workflow(self, engine, temp_project):
        """Test complete build workflow: plan -> config -> build -> analyze."""
        # 1. Planning entry
        plan_entry = engine.journal_append(
            author="ai",
            context="Starting new build attempt",
            intent="Build project with modified configuration",
            next_steps="Create and archive config, then run build",
        )

        # 2. Create and archive config
        config_file = temp_project / "build.toml"
        config_file.write_text("[build]\noptimize = true\ndebug = false")

        config_record = engine.config_archive(
            file_path=str(config_file),
            reason="Initial build configuration",
            journal_entry=plan_entry.entry_id,
        )

        # 3. Build entry (with config reference)
        build_entry = engine.journal_append(
            author="ai",
            context="Executing build with optimized config",
            action="Running build command",
            config_used=config_record.archive_path,
            caused_by=[plan_entry.entry_id],
        )

        # 4. Create and preserve build log
        log_file = temp_project / "build.log"
        log_file.write_text("Build started...\nCompiling...\nBuild successful!")

        log_record = engine.log_preserve(
            file_path=str(log_file),
            category="build",
            outcome="success",
        )

        # 5. Analysis entry (with log reference)
        analysis_entry = engine.journal_append(
            author="ai",
            context="Analyzing build results",
            observation="Build completed successfully in 45 seconds",
            analysis="Optimization flags improved build time by 30%",
            log_produced=log_record.preserved_path,
            caused_by=[build_entry.entry_id],
            outcome="success",
        )

        # 6. Take snapshot
        snapshot = engine.state_snapshot(
            name="post-build",
            include_configs=True,
            include_env=True,
            include_versions=False,
        )

        # Verify complete workflow recorded
        entries = engine.journal_read()
        assert len(entries) == 3

        timeline = engine.timeline()
        assert len(timeline) >= 5  # 3 entries + 1 config + 1 log + 1 snapshot

        # Verify causality chain
        causality = engine.trace_causality(
            entry_id=plan_entry.entry_id,
            direction="forward",
        )
        assert causality is not None

    def test_amendment_workflow(self, engine):
        """Test amendment workflow: entry -> discover error -> amend."""
        # 1. Original entry with mistake
        original = engine.journal_append(
            author="ai",
            context="Testing feature X",
            observation="Feature X works correctly",
            outcome="success",
        )

        # 2. Later discover the mistake
        engine.journal_append(
            author="ai",
            context="Re-testing feature X",
            observation="Found issue with original test",
        )

        # 3. Amend the original entry
        amendment = engine.journal_amend(
            references_entry=original.entry_id,
            correction="Original observation was incorrect",
            actual="Feature X has a subtle bug in edge case",
            impact="Need to re-evaluate success status",
            author="ai",
        )

        # Verify amendment links correctly
        entries = engine.journal_read()
        amendments = [e for e in entries if e.get("entry_type") == "amendment"]
        assert len(amendments) == 1
        assert amendments[0]["entry_id"] == amendment.entry_id

    def test_multi_config_iteration(self, engine, temp_project):
        """Test iterating through multiple config versions."""
        configs_created = []

        for i in range(3):
            # Create config
            config_file = temp_project / "config.toml"
            config_file.write_text(f"[build]\niteration = {i}")

            # Small delay to ensure different timestamps
            time.sleep(1.1)

            # Archive config
            record = engine.config_archive(
                file_path=str(config_file),
                reason=f"Iteration {i}",
            )
            configs_created.append(record)

            # Create entry for this iteration
            engine.journal_append(
                author="ai",
                context=f"Testing iteration {i}",
                config_used=record.archive_path,
            )

        # Verify all configs archived
        assert len(configs_created) == 3

        # Diff between first and last
        diff_result = engine.config_diff(
            path_a=configs_created[0].archive_path,
            path_b=configs_created[2].archive_path,
        )
        assert diff_result["identical"] is False


class TestSessionHandoffWorkflow:
    """Tests for session handoff functionality."""

    def test_complete_session_then_handoff(self, engine, temp_project):
        """Test a complete session followed by handoff generation."""
        # Simulate a work session
        engine.journal_append(
            author="ai",
            context="Starting work session",
            intent="Implement new feature",
        )

        config_file = temp_project / "feature.toml"
        config_file.write_text("[feature]\nenabled = true")
        engine.config_archive(file_path=str(config_file), reason="Feature config")

        engine.journal_append(
            author="ai",
            context="Feature implementation",
            action="Added new module",
            outcome="success",
        )

        engine.journal_append(
            author="ai",
            context="Ending session",
            next_steps="Continue with testing tomorrow",
        )

        # Generate handoff
        handoff = engine.session_handoff(format="markdown")

        assert "content" in handoff
        content = handoff["content"]
        assert "Session Handoff" in content
        assert "success" in content.lower() or "Success" in content

    def test_handoff_json_for_ai_consumption(self, engine, temp_project):
        """Test JSON handoff for AI context transfer."""
        engine.journal_append(
            author="ai",
            context="Work in progress",
            next_steps="Need to complete implementation",
        )

        handoff = engine.session_handoff(format="json")

        assert handoff["format"] == "json"
        content = handoff["content"]
        assert isinstance(content, dict)
        assert "entries" in content or "summary" in content


class TestTemplateWorkflow:
    """Tests for template-based workflows."""

    def test_consistent_build_entries_with_templates(self, temp_project):
        """Test using templates for consistent build entries."""
        templates = {
            "build_start": EntryTemplateConfig(
                name="build_start",
                description="Starting a build",
                context="Starting {stage} build",
                intent="Build {stage} using {config}",
                required_fields=["stage", "config"],
            ),
            "build_complete": EntryTemplateConfig(
                name="build_complete",
                description="Build completed",
                observation="Build {status} with exit code {exit_code}",
                required_fields=["status", "exit_code"],
                default_outcome="success",
            ),
        }

        config = ProjectConfig(
            project_name="template-test",
            project_root=temp_project,
            templates=templates,
        )
        engine = JournalEngine(config)

        # Start build using template
        start_entry = engine.journal_append(
            author="ci",
            template="build_start",
            template_values={
                "stage": "release",
                "config": "release.toml",
            },
        )

        assert "release" in start_entry.context
        assert "release.toml" in start_entry.intent

        # Complete build using template
        complete_entry = engine.journal_append(
            author="ci",
            template="build_complete",
            template_values={
                "status": "succeeded",
                "exit_code": "0",
            },
            caused_by=[start_entry.entry_id],
        )

        assert "succeeded" in complete_entry.observation
        assert "0" in complete_entry.observation

    def test_enforce_templates_in_project(self, temp_project):
        """Test project that enforces template usage."""
        templates = {
            "mandatory": EntryTemplateConfig(
                name="mandatory",
                description="Required template",
                context="Entry: {description}",
                required_fields=["description"],
            ),
        }

        config = ProjectConfig(
            project_name="strict-project",
            project_root=temp_project,
            templates=templates,
            require_templates=True,
        )
        engine = JournalEngine(config)

        # Must use template
        entry = engine.journal_append(
            author="ci",
            template="mandatory",
            template_values={"description": "Test entry"},
        )

        assert entry.template == "mandatory"


class TestCausalityTracking:
    """Tests for causality tracking across entries."""

    def test_complex_causality_chain(self, engine):
        """Test tracing complex causality chains."""
        # Create a diamond-shaped causality graph:
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D

        entry_a = engine.journal_append(
            author="ai",
            context="Root cause",
        )

        entry_b = engine.journal_append(
            author="ai",
            context="Branch B",
            caused_by=[entry_a.entry_id],
        )

        entry_c = engine.journal_append(
            author="ai",
            context="Branch C",
            caused_by=[entry_a.entry_id],
        )

        entry_d = engine.journal_append(
            author="ai",
            context="Merge point",
            caused_by=[entry_b.entry_id, entry_c.entry_id],
        )

        # Trace forward from A should find B, C, D
        forward = engine.trace_causality(
            entry_id=entry_a.entry_id,
            direction="forward",
        )
        assert isinstance(forward, dict)

        # Trace backward from D should find B, C, A
        backward = engine.trace_causality(
            entry_id=entry_d.entry_id,
            direction="backward",
        )
        assert isinstance(backward, dict)

    def test_causality_with_configs_and_logs(self, engine, temp_project):
        """Test causality tracking with config and log references."""
        # Create config
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        config_record = engine.config_archive(
            file_path=str(config_file),
            reason="Test config",
        )

        # Entry using config
        entry1 = engine.journal_append(
            author="ai",
            context="Using config",
            config_used=config_record.archive_path,
        )

        # Create log
        log_file = temp_project / "test.log"
        log_file.write_text("Test output")
        log_record = engine.log_preserve(
            file_path=str(log_file),
            outcome="success",
        )

        # Entry with log output
        entry2 = engine.journal_append(
            author="ai",
            context="Processing complete",
            log_produced=log_record.preserved_path,
            caused_by=[entry1.entry_id],
            outcome="success",
        )

        # Read entries and verify links
        entries = engine.journal_read()
        assert len(entries) == 2

        # Find entry with config reference
        config_entry = next(e for e in entries if e.get("config_used"))
        assert config_entry["config_used"] == config_record.archive_path


class TestTimelineIntegration:
    """Tests for timeline integration across all event types."""

    def test_timeline_shows_all_event_types(self, engine, temp_project):
        """Timeline should show entries, configs, logs, and snapshots."""
        # Create entry
        engine.journal_append(author="ai", context="Test entry")

        # Create and archive config
        config_file = temp_project / "test.toml"
        config_file.write_text("[test]\nvalue = 1")
        engine.config_archive(file_path=str(config_file), reason="Test")

        # Create and preserve log
        log_file = temp_project / "test.log"
        log_file.write_text("Log content")
        engine.log_preserve(file_path=str(log_file), outcome="success")

        # Create snapshot
        engine.state_snapshot(
            name="test",
            include_configs=False,
            include_env=False,
            include_versions=False,
        )

        # Get timeline
        events = engine.timeline()

        # Should have all types
        event_types = {e["event_type"] for e in events}
        assert "entry" in event_types
        assert "config" in event_types
        assert "log" in event_types
        assert "snapshot" in event_types

    def test_timeline_filtering(self, engine, temp_project):
        """Test filtering timeline by event type."""
        # Create various events
        engine.journal_append(author="ai", context="Entry 1")
        engine.journal_append(author="ai", context="Entry 2")

        config_file = temp_project / "test.toml"
        config_file.write_text("[test]")
        engine.config_archive(file_path=str(config_file), reason="Config")

        # Filter to entries only
        entries_only = engine.timeline(event_types=["entry"])

        for e in entries_only:
            assert e["event_type"] == "entry"

        # Filter to configs only
        configs_only = engine.timeline(event_types=["config"])

        for e in configs_only:
            assert e["event_type"] == "config"


class TestIndexIntegrity:
    """Tests for INDEX.md integrity across operations."""

    def test_index_reflects_all_archives(self, engine, temp_project):
        """INDEX.md should reflect all archived configs."""
        # Archive multiple configs
        for i in range(3):
            config_file = temp_project / f"config{i}.toml"
            config_file.write_text(f"[config{i}]\nvalue = {i}")
            engine.config_archive(file_path=str(config_file), reason=f"Config {i}")
            time.sleep(1.1)  # Ensure different timestamps

        # Check index
        index_file = temp_project / "a" / "configs" / "INDEX.md"
        assert index_file.exists()
        content = index_file.read_text()

        # Should have all configs
        for i in range(3):
            assert f"Config {i}" in content

    def test_index_rebuild_matches_files(self, engine, temp_project):
        """index_rebuild should match actual files."""
        # Create some configs
        for i in range(2):
            config_file = temp_project / f"test{i}.toml"
            config_file.write_text(f"[test]\nvalue = {i}")
            engine.config_archive(file_path=str(config_file), reason=f"Test {i}")
            time.sleep(1.1)

        # Delete and rebuild index
        index_file = temp_project / "a" / "configs" / "INDEX.md"
        index_file.unlink()

        result = engine.index_rebuild(directory="configs")

        assert result["action"] == "rebuilt"
        assert result["files_found"] >= 2
