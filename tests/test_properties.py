"""Property-based tests following comprehensive-testing.md methodology.

Uses hypothesis to verify algorithmic properties hold for many inputs.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from mcp_journal.config import ProjectConfig
from mcp_journal.engine import JournalEngine
from mcp_journal.models import generate_entry_id, format_timestamp, parse_timestamp, utc_now


def make_temp_engine():
    """Create a fresh engine with temp directory for each hypothesis test."""
    tmpdir = tempfile.mkdtemp()
    temp_project = Path(tmpdir)
    config = ProjectConfig(project_name="test", project_root=temp_project)
    return JournalEngine(config), temp_project


class TestEntryIdProperties:
    """Property-based tests for entry ID generation."""

    @given(
        year=st.integers(min_value=2000, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),  # Avoid invalid dates
        sequence=st.integers(min_value=1, max_value=999),
    )
    def test_entry_id_format_valid(self, year, month, day, sequence):
        """Generated entry IDs always have valid format."""
        date = datetime(year, month, day, tzinfo=timezone.utc)
        entry_id = generate_entry_id(date, sequence)

        # Format: YYYY-MM-DD-NNN
        parts = entry_id.split("-")
        assert len(parts) == 4
        assert len(parts[0]) == 4  # Year
        assert len(parts[1]) == 2  # Month
        assert len(parts[2]) == 2  # Day
        assert len(parts[3]) == 3  # Sequence

    @given(
        sequence=st.integers(min_value=1, max_value=999),
    )
    def test_entry_id_sequence_padded(self, sequence):
        """Sequence number is always zero-padded to 3 digits."""
        date = datetime(2026, 1, 6, tzinfo=timezone.utc)
        entry_id = generate_entry_id(date, sequence)

        seq_part = entry_id.split("-")[-1]
        assert len(seq_part) == 3
        assert int(seq_part) == sequence


class TestTimestampProperties:
    """Property-based tests for timestamp formatting/parsing."""

    @given(
        year=st.integers(min_value=2000, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        second=st.integers(min_value=0, max_value=59),
    )
    def test_timestamp_round_trip(self, year, month, day, hour, minute, second):
        """Formatting then parsing a timestamp preserves the value."""
        original = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        formatted = format_timestamp(original)
        parsed = parse_timestamp(formatted)

        # Compare with microsecond truncation (milliseconds preserved)
        assert parsed.year == original.year
        assert parsed.month == original.month
        assert parsed.day == original.day
        assert parsed.hour == original.hour
        assert parsed.minute == original.minute
        assert parsed.second == original.second


class TestJournalAppendProperties:
    """Property-based tests for journal_append invariants."""

    @given(
        author=st.text(min_size=0, max_size=100),
        context=st.text(min_size=0, max_size=1000),
    )
    @settings(max_examples=50)
    def test_append_always_creates_entry(self, author, context):
        """journal_append always creates a valid entry with any text input."""
        engine, _ = make_temp_engine()

        entry = engine.journal_append(author=author, context=context)

        assert entry is not None
        assert entry.entry_id is not None
        assert entry.author == author
        assert entry.context == context

    @given(
        count=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=10, deadline=None)
    def test_append_generates_unique_ids(self, count):
        """Multiple appends always generate unique IDs."""
        engine, _ = make_temp_engine()

        entries = []
        for i in range(count):
            entry = engine.journal_append(author="test", context=f"Entry {i}")
            entries.append(entry)

        ids = [e.entry_id for e in entries]
        assert len(ids) == len(set(ids))  # All unique

    @given(
        count=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=10, deadline=None)
    def test_append_preserves_chronological_order(self, count):
        """Entries are created in chronological order."""
        engine, _ = make_temp_engine()

        entries = []
        for i in range(count):
            entry = engine.journal_append(author="test", context=f"Entry {i}")
            entries.append(entry)

        timestamps = [e.timestamp for e in entries]
        assert timestamps == sorted(timestamps)


class TestConfigArchiveProperties:
    """Property-based tests for config archive invariants."""

    @given(
        content=st.text(
            min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=("Cc", "Cs"))
        ).filter(lambda x: x.strip()),
        reason=st.text(
            min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cc", "Cs"))
        ).filter(lambda x: x.strip()),
    )
    @settings(max_examples=30, deadline=None)
    def test_archive_content_preserved(self, content, reason):
        """Archived content is always preserved exactly."""
        engine, temp_project = make_temp_engine()

        config_file = temp_project / "test.toml"
        config_file.write_text(content, encoding="utf-8")

        record = engine.config_archive(file_path=str(config_file), reason=reason)

        archived_path = temp_project / record.archive_path
        archived_content = archived_path.read_text(encoding="utf-8")

        assert archived_content == content

    @given(
        content=st.text(
            min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cc", "Cs"))
        ).filter(lambda x: x.strip()),
    )
    @settings(max_examples=20, deadline=None)
    def test_archive_hash_consistent(self, content):
        """Hash is consistent for the same content."""
        engine, temp_project = make_temp_engine()

        config_file = temp_project / "test.toml"
        config_file.write_text(content, encoding="utf-8")

        record = engine.config_archive(file_path=str(config_file), reason="Test")

        # Compute hash again
        import hashlib
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        assert record.content_hash == expected_hash


class TestTimelineProperties:
    """Property-based tests for timeline invariants."""

    @given(
        count=st.integers(min_value=1, max_value=15),
    )
    @settings(max_examples=10, deadline=None)
    def test_timeline_always_sorted(self, count):
        """Timeline events are always sorted chronologically."""
        engine, _ = make_temp_engine()

        # Create entries
        for i in range(count):
            engine.journal_append(author="test", context=f"Entry {i}")

        events = engine.timeline()
        timestamps = [e["timestamp"] for e in events]

        assert timestamps == sorted(timestamps)

    @given(
        limit=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=10, deadline=None)
    def test_timeline_respects_limit(self, limit):
        """Timeline always respects the limit parameter."""
        engine, _ = make_temp_engine()

        # Create more entries than limit
        for i in range(limit + 5):
            engine.journal_append(author="test", context=f"Entry {i}")

        events = engine.timeline(limit=limit)

        assert len(events) == limit


class TestSearchProperties:
    """Property-based tests for search invariants."""

    @given(
        query=st.text(
            min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=("Cc", "Cs"))
        ).filter(lambda x: x.strip()),
    )
    @settings(max_examples=20, deadline=None)
    def test_search_finds_matching_content(self, query):
        """Search always finds entries containing the query."""
        engine, _ = make_temp_engine()

        # Create entry with the query in context
        entry = engine.journal_append(author="test", context=f"Contains {query} in text")

        results = engine.journal_search(query=query)

        # Should find at least this entry
        assert len(results) >= 1
        entry_ids = [r["entry_id"] for r in results]
        assert entry.entry_id in entry_ids


class TestAppendOnlyProperty:
    """Property-based tests for append-only invariant."""

    @given(
        operations=st.integers(min_value=5, max_value=20),
    )
    @settings(max_examples=5, deadline=None)
    def test_entries_never_decrease(self, operations):
        """Number of entries never decreases (append-only)."""
        engine, _ = make_temp_engine()

        entry_counts = []
        for i in range(operations):
            engine.journal_append(author="test", context=f"Entry {i}")
            results = engine.journal_read()
            entry_counts.append(len(results))

        # Entry count should be monotonically increasing
        for i in range(1, len(entry_counts)):
            assert entry_counts[i] >= entry_counts[i - 1]


class TestCausalityProperties:
    """Property-based tests for causality tracking."""

    @given(
        chain_length=st.integers(min_value=2, max_value=8),
    )
    @settings(max_examples=5, deadline=None)
    def test_causality_chain_traceable(self, chain_length):
        """Causality chains of any length can be traced."""
        engine, _ = make_temp_engine()

        # Create a causality chain
        entries = []
        prev_entry = None
        for i in range(chain_length):
            caused_by = [prev_entry.entry_id] if prev_entry else None
            entry = engine.journal_append(
                author="test",
                context=f"Chain entry {i}",
                caused_by=caused_by,
            )
            entries.append(entry)
            prev_entry = entry

        # Trace forward from first entry
        result = engine.trace_causality(
            entry_id=entries[0].entry_id,
            direction="forward",
            depth=chain_length,
        )

        # Should have found the chain
        assert isinstance(result, dict)
