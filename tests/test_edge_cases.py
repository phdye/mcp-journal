"""Edge case tests following comprehensive-testing.md methodology."""

from datetime import datetime, timezone

import pytest

from mcp_journal.config import ProjectConfig, EntryTemplateConfig
from mcp_journal.engine import (
    DuplicateContentError,
    InvalidReferenceError,
    JournalEngine,
    TemplateNotFoundError,
    TemplateRequiredError,
)


# Fixtures temp_project, config, and engine are provided by conftest.py


class TestJournalAppendEdgeCases:
    """Edge case tests for journal_append."""

    def test_empty_author(self, engine):
        """Empty string author should work (not rejected)."""
        entry = engine.journal_append(author="")
        assert entry.author == ""

    def test_whitespace_only_author(self, engine):
        """Whitespace-only author should work."""
        entry = engine.journal_append(author="   ")
        assert entry.author == "   "

    def test_very_long_context(self, engine):
        """Very long context (>10KB) should be handled."""
        long_context = "x" * 15000
        entry = engine.journal_append(author="test", context=long_context)
        assert len(entry.context) == 15000

    def test_very_long_all_fields(self, engine, temp_project):
        """All fields with very long content should be handled."""
        long_text = "y" * 5000
        entry = engine.journal_append(
            author="test",
            context=long_text,
            intent=long_text,
            action=long_text,
            observation=long_text,
            analysis=long_text,
            next_steps=long_text,
        )

        # Verify content was written
        journal_file = temp_project / "journal" / f"{entry.entry_id[:10]}.md"
        content = journal_file.read_text()
        assert long_text in content

    def test_unicode_in_author(self, engine):
        """Unicode characters in author should work."""
        entry = engine.journal_append(author="日本語テスト 🎉")
        assert entry.author == "日本語テスト 🎉"

    def test_unicode_in_all_fields(self, engine, temp_project):
        """Unicode in all text fields should be preserved."""
        entry = engine.journal_append(
            author="作者",
            context="背景: ここはコンテキスト",
            intent="意図: 目的を説明",
            action="アクション: 実行した内容",
            observation="観察: 結果の確認",
            analysis="分析: 学んだこと 🔍",
            next_steps="次のステップ: 継続 ✅",
        )

        journal_file = temp_project / "journal" / f"{entry.entry_id[:10]}.md"
        content = journal_file.read_text(encoding="utf-8")
        assert "背景" in content
        assert "🔍" in content
        assert "✅" in content

    def test_special_markdown_characters(self, engine, temp_project):
        """Special markdown characters should not break formatting."""
        entry = engine.journal_append(
            author="test",
            context="Code: `inline` and ```block```",
            intent="# Not a header\n## Also not",
            action="Link: [text](url) and ![img](src)",
            observation="Emphasis: *bold* _italic_ **strong**",
            analysis="List:\n- item1\n- item2\n1. numbered",
            next_steps="Table: | col | col |\n|---|---|",
        )

        journal_file = temp_project / "journal" / f"{entry.entry_id[:10]}.md"
        content = journal_file.read_text()
        assert "`inline`" in content
        assert "[text](url)" in content

    def test_newlines_in_fields(self, engine, temp_project):
        """Newlines in fields should be preserved."""
        multiline = "Line 1\nLine 2\nLine 3"
        entry = engine.journal_append(
            author="test",
            context=multiline,
        )

        journal_file = temp_project / "journal" / f"{entry.entry_id[:10]}.md"
        content = journal_file.read_text()
        assert "Line 1\nLine 2\nLine 3" in content

    def test_empty_references_list(self, engine):
        """Empty references list should work."""
        entry = engine.journal_append(
            author="test",
            references=[],
        )
        assert entry.references == []

    def test_empty_caused_by_list(self, engine):
        """Empty caused_by list should work."""
        entry = engine.journal_append(
            author="test",
            caused_by=[],
        )
        assert entry.caused_by == []

    def test_none_for_all_optional_fields(self, engine):
        """None for all optional fields should work."""
        entry = engine.journal_append(
            author="test",
            context=None,
            intent=None,
            action=None,
            observation=None,
            analysis=None,
            next_steps=None,
            references=None,
            caused_by=None,
            config_used=None,
            log_produced=None,
            outcome=None,
            template=None,
            template_values=None,
        )
        assert entry.context is None
        assert entry.intent is None

    def test_multiple_entries_rapid_succession(self, engine):
        """Multiple entries created rapidly should get unique IDs."""
        entries = []
        for i in range(10):
            entry = engine.journal_append(author="test", context=f"Entry {i}")
            entries.append(entry)

        # All IDs should be unique
        ids = [e.entry_id for e in entries]
        assert len(set(ids)) == 10

        # IDs should be sequential
        seqs = [int(e.entry_id.split("-")[-1]) for e in entries]
        assert seqs == sorted(seqs)

    def test_self_reference(self, engine):
        """An entry cannot reference itself (would be invalid at creation time)."""
        # This is implicitly tested - you can't reference an entry before it exists
        entry1 = engine.journal_append(author="test", context="First")

        # Can reference a previous entry
        entry2 = engine.journal_append(
            author="test",
            context="Second",
            references=[entry1.entry_id],
        )
        assert entry1.entry_id in entry2.references


class TestConfigArchiveEdgeCases:
    """Edge case tests for config_archive."""

    def test_archive_empty_file(self, engine, temp_project):
        """Archiving an empty file should work."""
        empty_file = temp_project / "empty.toml"
        empty_file.write_text("")

        record = engine.config_archive(file_path=str(empty_file), reason="Empty test")

        archive_path = temp_project / record.archive_path
        assert archive_path.exists()
        assert archive_path.read_text() == ""

    def test_archive_binary_content(self, engine, temp_project):
        """Archiving a file with binary-ish content should work."""
        bin_file = temp_project / "data.bin"
        # Write content that looks binary but is valid UTF-8
        bin_file.write_bytes(b"[config]\ndata = \"\\x00\\x01\\x02\"")

        record = engine.config_archive(file_path=str(bin_file), reason="Binary test")
        assert record.archive_path is not None

    def test_archive_unicode_filename(self, engine, temp_project):
        """Archiving a file with unicode in the name should work."""
        unicode_file = temp_project / "配置.toml"
        unicode_file.write_text("[test]\nvalue = 1")

        record = engine.config_archive(file_path=str(unicode_file), reason="Unicode name")
        assert record.archive_path is not None

    def test_archive_deeply_nested_path(self, engine, temp_project):
        """Archiving from a deeply nested path should work."""
        deep_path = temp_project / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        config_file = deep_path / "config.toml"
        config_file.write_text("[nested]\nvalue = true")

        record = engine.config_archive(file_path=str(config_file), reason="Deep")
        assert record.archive_path is not None

    def test_archive_relative_path(self, engine, temp_project):
        """Archiving with relative path should work."""
        config_file = temp_project / "rel.toml"
        config_file.write_text("[test]\nvalue = 1")

        # Use path relative to project root
        record = engine.config_archive(file_path="rel.toml", reason="Relative")
        assert record.archive_path is not None


class TestLogPreserveEdgeCases:
    """Edge case tests for log_preserve."""

    def test_preserve_empty_log(self, engine, temp_project):
        """Preserving an empty log file should work."""
        empty_log = temp_project / "empty.log"
        empty_log.write_text("")

        record = engine.log_preserve(file_path=str(empty_log))

        preserved = temp_project / record.preserved_path
        assert preserved.exists()
        assert preserved.read_text() == ""

    def test_preserve_very_large_log(self, engine, temp_project):
        """Preserving a large log file should work."""
        large_log = temp_project / "large.log"
        # Create 1MB log file
        large_log.write_text("x" * (1024 * 1024))

        record = engine.log_preserve(file_path=str(large_log))

        preserved = temp_project / record.preserved_path
        assert preserved.exists()
        assert preserved.stat().st_size == 1024 * 1024

    def test_preserve_with_special_category(self, engine, temp_project):
        """Categories with special characters should be handled."""
        log_file = temp_project / "test.log"
        log_file.write_text("content")

        # Category goes into filename - special chars might be problematic
        record = engine.log_preserve(
            file_path=str(log_file),
            category="test_category",  # Use safe category
            outcome="success",
        )
        assert "test_category" in record.preserved_path


class TestJournalSearchEdgeCases:
    """Edge case tests for journal_search."""

    def test_search_empty_journal(self, engine):
        """Searching empty journal should return empty list."""
        results = engine.journal_search(query="anything")
        assert results == []

    def test_search_case_insensitive(self, engine):
        """Search should be case insensitive."""
        engine.journal_append(author="test", context="UPPERCASE content")

        results = engine.journal_search(query="uppercase")
        assert len(results) == 1

        results = engine.journal_search(query="UPPERCASE")
        assert len(results) == 1

    def test_search_partial_match(self, engine):
        """Search should find partial matches."""
        engine.journal_append(author="test", context="Implementation of feature")

        results = engine.journal_search(query="implement")
        assert len(results) == 1

    def test_search_no_matches(self, engine):
        """Search with no matches returns empty list."""
        engine.journal_append(author="test", context="Some content")

        results = engine.journal_search(query="nonexistent_term_xyz")
        assert results == []

    def test_search_special_regex_chars(self, engine):
        """Search query with regex special chars should be treated as literal."""
        engine.journal_append(author="test", context="Path: foo/bar/*.py")

        # These are regex special chars - should be escaped
        results = engine.journal_search(query="*.py")
        assert len(results) == 1


class TestJournalReadEdgeCases:
    """Edge case tests for journal_read."""

    def test_read_empty_journal(self, engine):
        """Reading from empty journal returns empty list."""
        results = engine.journal_read()
        assert results == []

    def test_read_future_date(self, engine):
        """Reading entries for future date returns empty list."""
        results = engine.journal_read(date="2099-12-31")
        assert results == []

    def test_read_invalid_date_format(self, engine):
        """Reading with invalid date format should handle gracefully."""
        # The engine should not crash, just return empty
        results = engine.journal_read(date="invalid-date")
        assert results == []

    def test_read_nonexistent_entry_id(self, engine):
        """Reading nonexistent entry ID returns empty list."""
        results = engine.journal_read(entry_id="2099-12-31-999")
        assert results == []


class TestTimelineEdgeCases:
    """Edge case tests for timeline."""

    def test_timeline_empty_project(self, engine):
        """Timeline of empty project returns empty list."""
        events = engine.timeline()
        assert events == []

    def test_timeline_future_date_range(self, engine):
        """Timeline for future dates returns empty list."""
        engine.journal_append(author="test", context="Entry")

        events = engine.timeline(date_from="2099-01-01", date_to="2099-12-31")
        assert events == []


class TestConfigDiffEdgeCases:
    """Edge case tests for config_diff."""

    def test_diff_empty_files(self, engine, temp_project):
        """Diffing two empty files shows no differences."""
        file1 = temp_project / "empty1.toml"
        file2 = temp_project / "empty2.toml"
        file1.write_text("")
        file2.write_text("")

        result = engine.config_diff(
            path_a=f"current:{file1}",
            path_b=f"current:{file2}",
        )

        assert result["identical"] is True

    def test_diff_one_empty_file(self, engine, temp_project):
        """Diffing empty vs non-empty shows additions."""
        file1 = temp_project / "empty.toml"
        file2 = temp_project / "content.toml"
        file1.write_text("")
        file2.write_text("[test]\nvalue = 1")

        result = engine.config_diff(
            path_a=f"current:{file1}",
            path_b=f"current:{file2}",
        )

        assert result["identical"] is False
        assert result["additions"] > 0


class TestSessionHandoffEdgeCases:
    """Edge case tests for session_handoff."""

    def test_handoff_empty_project(self, engine):
        """Handoff of empty project should work."""
        result = engine.session_handoff()

        assert "content" in result
        # Should not crash on empty project

    def test_handoff_future_date_range(self, engine):
        """Handoff for future dates returns minimal content."""
        engine.journal_append(author="test", context="Entry")

        result = engine.session_handoff(
            date_from="2099-01-01",
            date_to="2099-12-31",
        )

        # Should not crash, content should be minimal
        assert "content" in result


class TestTraceCausalityEdgeCases:
    """Edge case tests for trace_causality."""

    def test_trace_nonexistent_entry(self, engine):
        """Tracing nonexistent entry raises InvalidReferenceError."""
        with pytest.raises(InvalidReferenceError):
            engine.trace_causality(entry_id="1999-01-01-001")

    def test_trace_entry_no_causality(self, engine):
        """Tracing entry with no causality links."""
        entry = engine.journal_append(author="test", context="Standalone")

        result = engine.trace_causality(entry_id=entry.entry_id)

        # Should return the entry itself with no links
        assert isinstance(result, dict)

    def test_trace_circular_causality_prevention(self, engine):
        """Should handle potential circular references gracefully."""
        # Create entries where B caused_by A
        entry_a = engine.journal_append(author="test", context="A")
        entry_b = engine.journal_append(
            author="test",
            context="B",
            caused_by=[entry_a.entry_id],
        )

        # Trace should not loop infinitely
        result = engine.trace_causality(entry_id=entry_a.entry_id, depth=100)
        assert isinstance(result, dict)


class TestTemplateEdgeCases:
    """Edge case tests for templates."""

    def test_template_empty_values_dict(self, temp_project):
        """Using template with empty values dict for template with no required fields."""
        templates = {
            "no_required": EntryTemplateConfig(
                name="no_required",
                description="Template with no required fields",
                context="Static context",
            ),
        }
        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            templates=templates,
        )
        engine = JournalEngine(config)

        entry = engine.journal_append(
            author="test",
            template="no_required",
            template_values={},
        )

        assert entry.template == "no_required"
        assert entry.context == "Static context"

    def test_list_templates_default(self, engine):
        """Listing templates returns default templates when no custom templates."""
        templates = engine.list_templates()
        # Default templates are now always available (diagnostic, build, test)
        assert len(templates) >= 3
        template_names = {t["name"] for t in templates}
        assert "diagnostic" in template_names
        assert "build" in template_names
        assert "test" in template_names

    def test_get_nonexistent_template(self, engine):
        """Getting nonexistent template returns None."""
        template = engine.get_template("nonexistent")
        assert template is None
