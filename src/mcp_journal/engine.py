"""Core journal engine - append-only operations with strict guarantees."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .config import ProjectConfig
from .index import JournalIndex
from .locking import file_lock, locked_atomic_write
from .models import (
    ConfigArchive,
    EntryType,
    JournalEntry,
    LogOutcome,
    LogPreservation,
    StateSnapshot,
    TimelineEvent,
    TimelineEventType,
    format_timestamp,
    generate_entry_id,
    parse_timestamp,
    utc_now,
)


class JournalError(Exception):
    """Base exception for journal operations."""
    pass


class AppendOnlyViolation(JournalError):
    """Raised when an operation would violate append-only semantics."""
    pass


class DuplicateContentError(JournalError):
    """Raised when trying to archive identical content."""
    pass


class InvalidReferenceError(JournalError):
    """Raised when a cross-reference is invalid."""
    pass


class TemplateRequiredError(JournalError):
    """Raised when template is required but not provided."""
    pass


class TemplateNotFoundError(JournalError):
    """Raised when specified template doesn't exist."""
    pass


class JournalEngine:
    """Core engine managing journal, configs, logs, and snapshots."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self._ensure_directories()
        # Initialize the SQLite index
        self._index: Optional[JournalIndex] = None

    @property
    def index(self) -> JournalIndex:
        """Lazily initialize and return the journal index."""
        if self._index is None:
            self._index = JournalIndex(self.config.get_journal_path())
        return self._index

    def _ensure_directories(self) -> None:
        """Create journal directory if it doesn't exist.

        Note: configs/, logs/, snapshots/ are created lazily when first used
        to avoid leaving empty directories in projects that don't use those features.
        """
        self.config.get_journal_path().mkdir(parents=True, exist_ok=True)

    def _get_journal_file(self, date: datetime) -> Path:
        """Get path to journal file for a given date."""
        return self.config.get_journal_path() / f"{date.strftime('%Y-%m-%d')}.md"

    def _get_next_sequence(self, date: datetime) -> int:
        """Get next sequence number for entries on a given date."""
        journal_file = self._get_journal_file(date)
        if not journal_file.exists():
            return 1

        # Count existing entries by looking for entry headers
        pattern = re.compile(rf"^## {date.strftime('%Y-%m-%d')}-(\d+)", re.MULTILINE)
        content = journal_file.read_text(encoding="utf-8")
        matches = pattern.findall(content)

        if not matches:
            return 1
        return max(int(m) for m in matches) + 1

    def _file_hash(self, path: Path) -> str:
        """Compute SHA-256 hash of file contents."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _content_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of bytes."""
        return hashlib.sha256(content).hexdigest()

    def _validate_reference(self, ref: str) -> bool:
        """Check if a reference (entry ID or file path) is valid."""
        # Check if it's an entry ID
        entry_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}$")
        if entry_pattern.match(ref):
            # Look for entry in journal files
            date_str = ref[:10]
            journal_file = self.config.get_journal_path() / f"{date_str}.md"
            if journal_file.exists():
                content = journal_file.read_text(encoding="utf-8")
                if f"## {ref}" in content:
                    return True
            return False

        # Check if it's a file path
        ref_path = Path(ref)
        if ref_path.is_absolute():
            return ref_path.exists()
        else:
            return (self.config.project_root / ref).exists()

    # ========== Journal Operations ==========

    def journal_append(
        self,
        author: str,
        context: Optional[str] = None,
        intent: Optional[str] = None,
        action: Optional[str] = None,
        observation: Optional[str] = None,
        analysis: Optional[str] = None,
        next_steps: Optional[str] = None,
        references: Optional[list[str]] = None,
        custom_fields: Optional[dict[str, str]] = None,
        # Causality fields
        caused_by: Optional[list[str]] = None,
        config_used: Optional[str] = None,
        log_produced: Optional[str] = None,
        outcome: Optional[str] = None,
        # Template support
        template: Optional[str] = None,
        template_values: Optional[dict[str, str]] = None,
        # Diagnostic fields (for tool call tracking)
        tool: Optional[str] = None,
        duration_ms: Optional[int] = None,
        exit_code: Optional[int] = None,
        command: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> JournalEntry:
        """Append a new entry to the journal.

        Returns:
            The created JournalEntry with assigned ID and timestamp.

        Raises:
            InvalidReferenceError: If any reference is invalid.
            TemplateRequiredError: If templates required but not provided.
            TemplateNotFoundError: If specified template doesn't exist.
        """
        # Check template requirements
        if self.config.require_templates and template is None:
            available = self.config.list_templates()
            raise TemplateRequiredError(
                f"This project requires templates. Available: {available}"
            )

        # Apply template if specified
        if template:
            tmpl = self.config.get_template(template)
            if tmpl is None:
                available = self.config.list_templates()
                raise TemplateNotFoundError(
                    f"Template '{template}' not found. Available: {available}"
                )

            values = template_values or {}
            # Check required fields
            missing = [f for f in tmpl.required_fields if f not in values]
            if missing:
                raise ValueError(f"Missing required template fields: {missing}")

            # Render template fields
            def render(t: Optional[str]) -> Optional[str]:
                if t is None:
                    return None
                try:
                    return t.format(**values)
                except KeyError:
                    return t

            context = render(tmpl.context) or context
            intent = render(tmpl.intent) or intent
            action = render(tmpl.action) or action
            observation = render(tmpl.observation) or observation
            analysis = render(tmpl.analysis) or analysis
            next_steps = render(tmpl.next_steps) or next_steps
            outcome = outcome or tmpl.default_outcome

        now = utc_now()
        refs = references or []
        caused_by_list = caused_by or []

        # Validate references
        for ref in refs:
            if not self._validate_reference(ref):
                raise InvalidReferenceError(f"Invalid reference: {ref}")

        # Validate causality references
        for ref in caused_by_list:
            if not self._validate_reference(ref):
                raise InvalidReferenceError(f"Invalid caused_by reference: {ref}")

        journal_file = self._get_journal_file(now)

        with file_lock(journal_file):
            sequence = self._get_next_sequence(now)
            entry_id = generate_entry_id(now, sequence)

            entry = JournalEntry(
                entry_id=entry_id,
                timestamp=now,
                author=author,
                entry_type=EntryType.ENTRY,
                context=context,
                intent=intent,
                action=action,
                observation=observation,
                analysis=analysis,
                next_steps=next_steps,
                references=refs,
                caused_by=caused_by_list,
                config_used=config_used,
                log_produced=log_produced,
                outcome=outcome,
                template=template,
                tool=tool,
                duration_ms=duration_ms,
                exit_code=exit_code,
                command=command,
                error_type=error_type,
            )

            # Call hook if defined
            if "pre_append" in self.config.hooks:
                entry = self.config.hooks["pre_append"](entry, custom_fields)

            markdown = entry.to_markdown()

            # Create or append to journal file
            if not journal_file.exists():
                header = f"# Journal - {now.strftime('%Y-%m-%d')}\n\n"
                journal_file.write_text(header + markdown, encoding="utf-8")
            else:
                with open(journal_file, "a", encoding="utf-8") as f:
                    f.write(markdown)

            # Update causality: add this entry to the "causes" field of referenced entries
            if caused_by_list:
                self._update_causality_links(caused_by_list, entry_id)

            # Call post hook if defined
            if "post_append" in self.config.hooks:
                self.config.hooks["post_append"](entry)

            # Index the entry in SQLite
            diagnostic_fields = {}
            if tool is not None:
                diagnostic_fields["tool"] = tool
            if duration_ms is not None:
                diagnostic_fields["duration_ms"] = duration_ms
            if exit_code is not None:
                diagnostic_fields["exit_code"] = exit_code
            if command is not None:
                diagnostic_fields["command"] = command
            if error_type is not None:
                diagnostic_fields["error_type"] = error_type

            self.index.index_entry(entry, journal_file, diagnostic_fields if diagnostic_fields else None)

        return entry

    def _update_causality_links(self, caused_by: list[str], new_entry_id: str) -> None:
        """Update the 'causes' field in entries that caused this one.

        Note: This is a best-effort update. The markdown format makes it
        difficult to reliably update, so we append a causality note instead.
        """
        # For now, we don't modify existing entries (append-only)
        # The causality is tracked in the new entry's caused_by field
        # Future: could maintain a separate causality index file
        pass

    def journal_amend(
        self,
        references_entry: str,
        correction: str,
        actual: str,
        impact: str,
        author: str,
    ) -> JournalEntry:
        """Add an amendment to a previous entry (NOT edit it).

        Returns:
            The created amendment entry.

        Raises:
            InvalidReferenceError: If the referenced entry doesn't exist.
        """
        if not self._validate_reference(references_entry):
            raise InvalidReferenceError(f"Cannot amend non-existent entry: {references_entry}")

        now = utc_now()
        journal_file = self._get_journal_file(now)

        with file_lock(journal_file):
            sequence = self._get_next_sequence(now)
            entry_id = generate_entry_id(now, sequence)

            entry = JournalEntry(
                entry_id=entry_id,
                timestamp=now,
                author=author,
                entry_type=EntryType.AMENDMENT,
                references_entry=references_entry,
                correction=correction,
                actual=actual,
                impact=impact,
            )

            markdown = entry.to_markdown()

            if not journal_file.exists():
                header = f"# Journal - {now.strftime('%Y-%m-%d')}\n\n"
                journal_file.write_text(header + markdown, encoding="utf-8")
            else:
                with open(journal_file, "a", encoding="utf-8") as f:
                    f.write(markdown)

            # Index the amendment entry
            self.index.index_entry(entry, journal_file)

        return entry

    # ========== Config Operations ==========

    def config_archive(
        self,
        file_path: str,
        reason: str,
        stage: Optional[str] = None,
        journal_entry: Optional[str] = None,
    ) -> ConfigArchive:
        """Archive a configuration file before modification.

        Returns:
            ConfigArchive record.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            DuplicateContentError: If identical content already archived.
        """
        source = Path(file_path)
        if not source.is_absolute():
            source = self.config.project_root / file_path

        if not source.exists():
            raise FileNotFoundError(f"Config file not found: {source}")

        content_hash = self._file_hash(source)
        now = utc_now()

        # Check for duplicate content (lazy directory creation)
        configs_dir = self.config.get_configs_path()
        configs_dir.mkdir(parents=True, exist_ok=True)
        for existing in configs_dir.glob(f"{source.stem}.*"):
            if existing.suffix in [".lock", ".tmp"]:
                continue
            if existing.exists() and self._file_hash(existing) == content_hash:
                raise DuplicateContentError(
                    f"Identical content already archived at: {existing}"
                )

        # Build archive filename
        timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
        stage_part = f".{stage}" if stage else ""
        archive_name = f"{source.stem}.{timestamp_str}{stage_part}{source.suffix}"
        archive_path = configs_dir / archive_name

        # Copy file to archive
        with file_lock(archive_path):
            content = source.read_bytes()
            archive_path.write_bytes(content)

        record = ConfigArchive(
            original_path=str(file_path),
            archive_path=str(archive_path.relative_to(self.config.project_root)),
            timestamp=now,
            reason=reason,
            stage=stage,
            journal_entry=journal_entry,
            content_hash=content_hash,
        )

        # Update index
        self._update_config_index(record)

        return record

    def config_activate(
        self,
        archive_path: str,
        target_path: str,
        reason: str,
        journal_entry: str,
    ) -> ConfigArchive:
        """Set an archived config as active.

        First archives current target (if exists), then copies archive to target.

        Returns:
            ConfigArchive of the previously active config (if any).
        """
        archive = Path(archive_path)
        if not archive.is_absolute():
            archive = self.config.project_root / archive_path

        target = Path(target_path)
        if not target.is_absolute():
            target = self.config.project_root / target_path

        if not archive.exists():
            raise FileNotFoundError(f"Archive not found: {archive}")

        # Archive current target if it exists
        old_archive = None
        if target.exists():
            old_archive = self.config_archive(
                file_path=str(target),
                reason=f"Superseded by {archive_path}",
                journal_entry=journal_entry,
            )
            # Mark old archive as superseded
            superseded_path = Path(old_archive.archive_path)
            if not superseded_path.is_absolute():
                superseded_path = self.config.project_root / old_archive.archive_path
            superseded_path.rename(superseded_path.with_suffix(superseded_path.suffix + ".superseded"))

        # Copy archive to target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read_bytes())

        return old_archive

    def _update_config_index(self, record: ConfigArchive) -> None:
        """Update configs/INDEX.md with new archive record."""
        index_path = self.config.get_configs_path() / "INDEX.md"

        with file_lock(index_path):
            if not index_path.exists():
                header = """# Configuration Archive Index

| Timestamp | Archive Path | Stage | Reason | Journal Entry |
|-----------|--------------|-------|--------|---------------|
"""
                index_path.write_text(header, encoding="utf-8")

            with open(index_path, "a", encoding="utf-8") as f:
                f.write(record.to_index_line() + "\n")

    # ========== Log Operations ==========

    def log_preserve(
        self,
        file_path: str,
        category: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> LogPreservation:
        """Preserve a log file (move with timestamp, never delete).

        Returns:
            LogPreservation record.
        """
        source = Path(file_path)
        if not source.is_absolute():
            source = self.config.project_root / file_path

        if not source.exists():
            raise FileNotFoundError(f"Log file not found: {source}")

        now = utc_now()
        outcome_enum = LogOutcome(outcome) if outcome else LogOutcome.UNKNOWN

        # Build preserved filename (lazy directory creation)
        logs_dir = self.config.get_logs_path()
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
        cat_part = f"{category}." if category else ""
        base_name = f"{cat_part}{timestamp_str}.{outcome_enum.value}"
        preserved_name = f"{base_name}.log"
        preserved_path = logs_dir / preserved_name

        # Handle filename collision (e.g., multiple logs in same second)
        counter = 1
        while preserved_path.exists():
            preserved_name = f"{base_name}.{counter}.log"
            preserved_path = logs_dir / preserved_name
            counter += 1

        # Move file to logs directory
        with file_lock(preserved_path):
            source.rename(preserved_path)

        record = LogPreservation(
            original_path=str(file_path),
            preserved_path=str(preserved_path.relative_to(self.config.project_root)),
            timestamp=now,
            category=category,
            outcome=outcome_enum,
        )

        # Update index
        self._update_log_index(record)

        return record

    def _update_log_index(self, record: LogPreservation) -> None:
        """Update logs/INDEX.md with new preservation record."""
        index_path = self.config.get_logs_path() / "INDEX.md"

        with file_lock(index_path):
            if not index_path.exists():
                header = """# Log Preservation Index

| Timestamp | Preserved Path | Category | Outcome |
|-----------|----------------|----------|---------|
"""
                index_path.write_text(header, encoding="utf-8")

            with open(index_path, "a", encoding="utf-8") as f:
                f.write(record.to_index_line() + "\n")

    # ========== Snapshot Operations ==========

    def state_snapshot(
        self,
        name: str,
        include_configs: bool = True,
        include_env: bool = True,
        include_versions: bool = True,
        include_build_dir_listing: bool = False,
        build_dir: Optional[str] = None,
        custom_data: Optional[dict] = None,
    ) -> StateSnapshot:
        """Capture complete state atomically.

        Returns:
            StateSnapshot record.
        """
        now = utc_now()
        # Lazy directory creation
        snapshots_dir = self.config.get_snapshots_path()
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = now.strftime("%Y-%m-%d.%H%M%S")
        snapshot_name = f"{name}.{timestamp_str}.json"
        snapshot_path = snapshots_dir / snapshot_name

        snapshot = StateSnapshot(
            name=name,
            timestamp=now,
            snapshot_path=str(snapshot_path.relative_to(self.config.project_root)),
        )

        # Capture configs
        if include_configs:
            snapshot.configs = {}
            configs_dir = self.config.get_configs_path()
            for pattern in self.config.config_patterns:
                for config_file in self.config.project_root.glob(pattern):
                    if config_file.is_file():
                        try:
                            rel_path = str(config_file.relative_to(self.config.project_root))
                            snapshot.configs[rel_path] = config_file.read_text(encoding="utf-8")
                        except Exception:
                            pass

        # Capture environment
        if include_env:
            snapshot.environment = dict(os.environ)

        # Capture versions
        if include_versions:
            snapshot.versions = {}
            for vc in self.config.version_commands:
                try:
                    result = subprocess.run(
                        vc.command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    output = result.stdout.strip() or result.stderr.strip()
                    if vc.parse_regex:
                        match = re.search(vc.parse_regex, output)
                        if match:
                            output = match.group(1) if match.groups() else match.group(0)
                    snapshot.versions[vc.name] = output
                except Exception as e:
                    snapshot.versions[vc.name] = f"ERROR: {e}"

            # Call hook for additional versions
            if "capture_versions" in self.config.hooks:
                extra = self.config.hooks["capture_versions"](self)
                if extra:
                    snapshot.versions.update(extra)

        # Capture build directory listing
        if include_build_dir_listing and build_dir:
            bd = Path(build_dir)
            if not bd.is_absolute():
                bd = self.config.project_root / build_dir
            if bd.exists():
                snapshot.build_dir_listing = [
                    str(p.relative_to(bd)) for p in bd.rglob("*") if p.is_file()
                ]

        # Include custom data
        if custom_data:
            snapshot.custom_data = custom_data

        # Write snapshot atomically
        with locked_atomic_write(snapshot_path) as f:
            json.dump({
                "name": snapshot.name,
                "timestamp": format_timestamp(snapshot.timestamp),
                "configs": snapshot.configs,
                "environment": snapshot.environment,
                "versions": snapshot.versions,
                "build_dir_listing": snapshot.build_dir_listing,
                "custom_data": snapshot.custom_data,
            }, f, indent=2)

        # Update index
        self._update_snapshot_index(snapshot)

        return snapshot

    def _update_snapshot_index(self, record: StateSnapshot) -> None:
        """Update snapshots/INDEX.md with new snapshot record."""
        index_path = self.config.get_snapshots_path() / "INDEX.md"

        with file_lock(index_path):
            if not index_path.exists():
                header = """# Snapshot Index

| Timestamp | Snapshot Path | Name | Contents |
|-----------|---------------|------|----------|
"""
                index_path.write_text(header, encoding="utf-8")

            with open(index_path, "a", encoding="utf-8") as f:
                f.write(record.to_index_line() + "\n")

    # ========== Search Operations ==========

    def journal_search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        author: Optional[str] = None,
        entry_type: Optional[str] = None,
    ) -> list[dict]:
        """Search journal entries.

        Returns:
            List of matching entry summaries.
        """
        results = []
        journal_dir = self.config.get_journal_path()

        for journal_file in sorted(journal_dir.glob("*.md")):
            # Filter by date range
            file_date = journal_file.stem
            if date_from and file_date < date_from:
                continue
            if date_to and file_date > date_to:
                continue

            content = journal_file.read_text(encoding="utf-8")

            # Simple entry parsing
            entries = re.split(r"\n## (\d{4}-\d{2}-\d{2}-\d{3})\n", content)

            for i in range(1, len(entries), 2):
                entry_id = entries[i]
                entry_content = entries[i + 1] if i + 1 < len(entries) else ""

                # Filter by author
                if author:
                    author_match = re.search(r"\*\*Author\*\*:\s*(.+)", entry_content)
                    if not author_match or author.lower() not in author_match.group(1).lower():
                        continue

                # Filter by entry type
                if entry_type:
                    type_match = re.search(r"\*\*Type\*\*:\s*(.+)", entry_content)
                    if not type_match or entry_type.lower() != type_match.group(1).lower():
                        continue

                # Filter by query
                if query.lower() not in entry_content.lower():
                    continue

                # Extract summary
                timestamp_match = re.search(r"\*\*Timestamp\*\*:\s*(.+)", entry_content)
                author_match = re.search(r"\*\*Author\*\*:\s*(.+)", entry_content)

                results.append({
                    "entry_id": entry_id,
                    "timestamp": timestamp_match.group(1) if timestamp_match else "",
                    "author": author_match.group(1) if author_match else "",
                    "file": str(journal_file.relative_to(self.config.project_root)),
                    "preview": entry_content[:200] + "..." if len(entry_content) > 200 else entry_content,
                })

        return results

    # ========== SQLite Index Query Operations ==========

    def journal_query(
        self,
        filters: Optional[dict[str, Any]] = None,
        text_search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "timestamp",
        order_desc: bool = True,
    ) -> list[dict]:
        """Query journal entries using the SQLite index.

        This is a faster, more flexible alternative to journal_search
        that uses the SQLite index for efficient querying.

        Args:
            filters: Dictionary of field=value filters (e.g., {"tool": "bash", "outcome": "failure"})
            text_search: Full-text search query
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum results to return (default: 100)
            offset: Number of results to skip (default: 0)
            order_by: Field to order by (default: "timestamp")
            order_desc: True for descending order (default: True)

        Returns:
            List of matching entry dictionaries
        """
        return self.index.query(
            filters=filters,
            text_search=text_search,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_desc=order_desc,
        )

    def journal_stats(
        self,
        group_by: Optional[str] = None,
        aggregations: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """Get aggregated statistics over journal entries.

        Args:
            group_by: Field to group by (e.g., "tool", "outcome", "author")
            aggregations: List of aggregation expressions (e.g., ["count", "avg:duration_ms"])
            filters: Additional filters
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dictionary with aggregation results including groups and totals
        """
        if group_by is None:
            # Return overall stats
            return self.index.get_stats()

        return self.index.aggregate(
            group_by=group_by,
            aggregations=aggregations,
            filters=filters,
            date_from=date_from,
            date_to=date_to,
        )

    def journal_active(
        self,
        threshold_ms: int = 30000,
        tool_filter: Optional[str] = None,
    ) -> list[dict]:
        """Find potentially active or hanging operations.

        This is useful for detecting long-running tool calls that might
        have hung or operations that weren't properly completed.

        Args:
            threshold_ms: Duration threshold in milliseconds (default: 30000)
            tool_filter: Optional tool name filter

        Returns:
            List of entries that might be active/hanging
        """
        return self.index.get_active_operations(
            threshold_ms=threshold_ms,
            tool_filter=tool_filter,
        )

    def rebuild_sqlite_index(self) -> dict:
        """Rebuild the SQLite index from markdown files.

        This parses all journal markdown files and rebuilds the index.
        Use this if the index gets out of sync or corrupted.

        Returns:
            Dictionary with rebuild statistics
        """
        return self.index.rebuild_from_markdown(
            parse_entry_func=self._parse_journal_entries,
        )

    # ========== Index Rebuild ==========

    def index_rebuild(
        self,
        directory: str,
        dry_run: bool = False,
    ) -> dict:
        """Rebuild INDEX.md from actual files.

        Args:
            directory: One of "configs", "logs", or "snapshots"
            dry_run: If True, return what would be done without writing

        Returns:
            Dict with rebuild results.
        """
        if directory == "configs":
            target_dir = self.config.get_configs_path()
            pattern = "*"
        elif directory == "logs":
            target_dir = self.config.get_logs_path()
            pattern = "*.log"
        elif directory == "snapshots":
            target_dir = self.config.get_snapshots_path()
            pattern = "*.json"
        else:
            raise ValueError(f"Unknown directory: {directory}")

        # Handle non-existent directory (lazy creation means it may not exist)
        if not target_dir.exists():
            return {
                "directory": directory,
                "files_found": 0,
                "files": [],
                "action": "skipped_no_directory",
            }

        files = sorted(target_dir.glob(pattern))
        files = [f for f in files if f.name != "INDEX.md" and not f.suffix in [".lock", ".tmp"]]

        if dry_run:
            return {
                "directory": directory,
                "files_found": len(files),
                "files": [str(f.name) for f in files],
                "action": "dry_run",
            }

        # Rebuild index based on directory type
        index_path = target_dir / "INDEX.md"

        if directory == "configs":
            header = """# Configuration Archive Index

| Timestamp | Archive Path | Stage | Reason | Journal Entry |
|-----------|--------------|-------|--------|---------------|
"""
        elif directory == "logs":
            header = """# Log Preservation Index

| Timestamp | Preserved Path | Category | Outcome |
|-----------|----------------|----------|---------|
"""
        else:  # snapshots
            header = """# Snapshot Index

| Timestamp | Snapshot Path | Name | Contents |
|-----------|---------------|------|----------|
"""

        with locked_atomic_write(index_path) as f:
            f.write(header)
            for file in files:
                # Extract info from filename
                f.write(f"| (rebuilt) | {file.name} | - | - |\n")

        return {
            "directory": directory,
            "files_found": len(files),
            "index_path": str(index_path),
            "action": "rebuilt",
        }

    # ========== Journal Read ==========

    def journal_read(
        self,
        entry_id: Optional[str] = None,
        date: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_content: bool = True,
    ) -> list[dict]:
        """Read journal entries by ID or date range.

        Args:
            entry_id: Specific entry ID (e.g., "2026-01-06-003")
            date: All entries for a specific date (YYYY-MM-DD)
            date_from: Range start
            date_to: Range end
            include_content: Include full content vs summary only

        Returns:
            List of entry dictionaries
        """
        results = []
        journal_dir = self.config.get_journal_path()

        # Determine which files to read
        if entry_id:
            # Single entry - extract date from ID
            date_str = entry_id[:10]
            files = [journal_dir / f"{date_str}.md"]
        elif date:
            files = [journal_dir / f"{date}.md"]
        else:
            files = sorted(journal_dir.glob("*.md"))

        for journal_file in files:
            if not journal_file.exists():
                continue

            file_date = journal_file.stem

            # Filter by date range
            if date_from and file_date < date_from:
                continue
            if date_to and file_date > date_to:
                continue

            content = journal_file.read_text(encoding="utf-8")
            entries = self._parse_journal_entries(content, journal_file)

            for entry in entries:
                # Filter by entry_id if specified
                if entry_id and entry["entry_id"] != entry_id:
                    continue

                if not include_content:
                    # Remove large content fields for summary
                    entry = {k: v for k, v in entry.items()
                            if k not in ["context", "intent", "action",
                                        "observation", "analysis", "next_steps",
                                        "correction", "actual", "impact"]}

                results.append(entry)

        return results

    def _parse_journal_entries(self, content: str, file_path: Path) -> list[dict]:
        """Parse journal file content into entry dictionaries."""
        entries = []
        # Split on entry headers
        parts = re.split(r"\n## (\d{4}-\d{2}-\d{2}-\d{3})\n", content)

        for i in range(1, len(parts), 2):
            entry_id = parts[i]
            entry_content = parts[i + 1] if i + 1 < len(parts) else ""

            entry = self._parse_entry_content(entry_id, entry_content)
            entry["file"] = str(file_path.relative_to(self.config.project_root))
            entries.append(entry)

        return entries

    def _parse_entry_content(self, entry_id: str, content: str) -> dict:
        """Parse a single entry's content into a dictionary."""
        entry = {"entry_id": entry_id}

        # Extract metadata fields
        patterns = {
            "timestamp": r"\*\*Timestamp\*\*:\s*(.+)",
            "author": r"\*\*Author\*\*:\s*(.+)",
            "entry_type": r"\*\*Type\*\*:\s*(.+)",
            "outcome": r"\*\*Outcome\*\*:\s*(.+)",
            "template": r"\*\*Template\*\*:\s*(.+)",
            "config_used": r"\*\*Config\*\*:\s*(.+)",
            "log_produced": r"\*\*Log\*\*:\s*(.+)",
            "caused_by": r"\*\*Caused-By\*\*:\s*(.+)",
            "causes": r"\*\*Causes\*\*:\s*(.+)",
            "amends": r"\*\*Amends\*\*:\s*(.+)",
            # Diagnostic fields
            "tool": r"\*\*Tool\*\*:\s*(.+)",
            "duration_ms": r"\*\*Duration\*\*:\s*(\d+)ms",
            "exit_code": r"\*\*Exit-Code\*\*:\s*(-?\d+)",
            "command": r"\*\*Command\*\*:\s*(.+)",
            "error_type": r"\*\*Error-Type\*\*:\s*(.+)",
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1).strip()
                # Parse comma-separated lists
                if field in ["caused_by", "causes"]:
                    entry[field] = [v.strip() for v in value.split(",")]
                # Parse integer fields
                elif field in ["duration_ms", "exit_code"]:
                    entry[field] = int(value)
                else:
                    entry[field] = value

        # Extract section content
        sections = {
            "context": r"### Context\n(.*?)(?=\n###|\n---|\Z)",
            "intent": r"### Intent\n(.*?)(?=\n###|\n---|\Z)",
            "action": r"### Action\n(.*?)(?=\n###|\n---|\Z)",
            "observation": r"### Observation\n(.*?)(?=\n###|\n---|\Z)",
            "analysis": r"### Analysis\n(.*?)(?=\n###|\n---|\Z)",
            "next_steps": r"### Next Steps\n(.*?)(?=\n###|\n---|\Z)",
            "correction": r"### Correction\n(.*?)(?=\n###|\n---|\Z)",
            "actual": r"### Actual\n(.*?)(?=\n###|\n---|\Z)",
            "impact": r"### Impact\n(.*?)(?=\n###|\n---|\Z)",
        }

        for field, pattern in sections.items():
            match = re.search(pattern, content, re.DOTALL)
            if match:
                entry[field] = match.group(1).strip()

        # Extract references
        refs_match = re.search(r"### References\n(.*?)(?=\n###|\n---|\Z)", content, re.DOTALL)
        if refs_match:
            refs_text = refs_match.group(1)
            entry["references"] = [
                line.lstrip("- ").strip()
                for line in refs_text.strip().split("\n")
                if line.strip().startswith("-")
            ]

        return entry

    # ========== Timeline ==========

    def timeline(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get unified chronological view across all event types.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            event_types: Filter to specific types ("entry", "config", "log", "snapshot")
            limit: Maximum events to return

        Returns:
            List of timeline events sorted by timestamp
        """
        events = []
        types = event_types or ["entry", "amendment", "config", "log", "snapshot"]

        # Collect journal entries
        if "entry" in types or "amendment" in types:
            journal_dir = self.config.get_journal_path()
            for journal_file in journal_dir.glob("*.md"):
                file_date = journal_file.stem
                if date_from and file_date < date_from:
                    continue
                if date_to and file_date > date_to:
                    continue

                content = journal_file.read_text(encoding="utf-8")
                for entry in self._parse_journal_entries(content, journal_file):
                    entry_type = entry.get("entry_type", "entry")
                    if entry_type not in types:
                        continue

                    events.append(TimelineEvent(
                        timestamp=parse_timestamp(entry["timestamp"]) if "timestamp" in entry else utc_now(),
                        event_type=TimelineEventType.JOURNAL_AMENDMENT if entry_type == "amendment" else TimelineEventType.JOURNAL_ENTRY,
                        summary=entry.get("context", entry.get("correction", ""))[:100],
                        entry_id=entry["entry_id"],
                        author=entry.get("author"),
                        outcome=entry.get("outcome"),
                        details={"template": entry.get("template")},
                    ))

        # Collect config archives
        if "config" in types:
            configs_dir = self.config.get_configs_path()
            if configs_dir.exists():
                for config_file in configs_dir.glob("*"):
                    if config_file.suffix in [".lock", ".tmp", ".md"]:
                        continue
                    # Parse timestamp from filename
                    match = re.search(r"\.(\d{4}-\d{2}-\d{2})\.(\d{6})", config_file.name)
                    if match:
                        date_str = match.group(1)
                        time_str = match.group(2)
                        if date_from and date_str < date_from:
                            continue
                        if date_to and date_str > date_to:
                            continue

                        ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
                        events.append(TimelineEvent(
                            timestamp=ts.replace(tzinfo=utc_now().tzinfo),
                            event_type=TimelineEventType.CONFIG_ARCHIVE,
                            summary=f"Config archived: {config_file.name}",
                            path=str(config_file.relative_to(self.config.project_root)),
                        ))

        # Collect log preservations
        if "log" in types:
            logs_dir = self.config.get_logs_path()
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log"):
                    # Parse timestamp and outcome from filename
                    match = re.search(r"(\d{4}-\d{2}-\d{2})\.(\d{6})\.(\w+)\.log", log_file.name)
                    if match:
                        date_str = match.group(1)
                        time_str = match.group(2)
                        outcome = match.group(3)
                        if date_from and date_str < date_from:
                            continue
                        if date_to and date_str > date_to:
                            continue

                        ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
                        events.append(TimelineEvent(
                            timestamp=ts.replace(tzinfo=utc_now().tzinfo),
                            event_type=TimelineEventType.LOG_PRESERVE,
                            summary=f"Log preserved: {log_file.name}",
                            path=str(log_file.relative_to(self.config.project_root)),
                            outcome=outcome,
                        ))

        # Collect snapshots
        if "snapshot" in types:
            snapshots_dir = self.config.get_snapshots_path()
            if snapshots_dir.exists():
                for snapshot_file in snapshots_dir.glob("*.json"):
                    match = re.search(r"\.(\d{4}-\d{2}-\d{2})\.(\d{6})\.json", snapshot_file.name)
                    if match:
                        date_str = match.group(1)
                        time_str = match.group(2)
                        if date_from and date_str < date_from:
                            continue
                        if date_to and date_str > date_to:
                            continue

                        ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
                        # Extract name from filename
                        name = snapshot_file.name.split(".")[0]
                        events.append(TimelineEvent(
                            timestamp=ts.replace(tzinfo=utc_now().tzinfo),
                            event_type=TimelineEventType.SNAPSHOT,
                            summary=f"Snapshot: {name}",
                            path=str(snapshot_file.relative_to(self.config.project_root)),
                        ))

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)

        # Apply limit
        if limit:
            events = events[:limit]

        return [e.to_dict() for e in events]

    # ========== Config Diff ==========

    def config_diff(
        self,
        path_a: str,
        path_b: str,
        context_lines: int = 3,
    ) -> dict:
        """Show diff between two config files.

        Args:
            path_a: First config path (archive path, or "current:path/to/file")
            path_b: Second config path
            context_lines: Lines of context around changes

        Returns:
            Dict with diff information
        """
        # Resolve paths
        def resolve_path(p: str) -> Path:
            if p.startswith("current:"):
                return self.config.project_root / p[8:]
            path = Path(p)
            if not path.is_absolute():
                path = self.config.project_root / p
            return path

        file_a = resolve_path(path_a)
        file_b = resolve_path(path_b)

        if not file_a.exists():
            raise FileNotFoundError(f"Config not found: {file_a}")
        if not file_b.exists():
            raise FileNotFoundError(f"Config not found: {file_b}")

        content_a = file_a.read_text(encoding="utf-8").splitlines(keepends=True)
        content_b = file_b.read_text(encoding="utf-8").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            content_a,
            content_b,
            fromfile=str(path_a),
            tofile=str(path_b),
            n=context_lines,
        ))

        # Count changes
        additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

        return {
            "path_a": str(path_a),
            "path_b": str(path_b),
            "identical": len(diff) == 0,
            "additions": additions,
            "deletions": deletions,
            "diff": "".join(diff),
        }

    # ========== Session Handoff ==========

    def session_handoff(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_configs: bool = True,
        include_logs: bool = True,
        format: str = "markdown",
    ) -> dict:
        """Generate session handoff summary for AI context transfer.

        Args:
            date_from: Start of session (default: today)
            date_to: End of session (default: now)
            include_configs: Include config change summary
            include_logs: Include log outcome summary
            format: Output format ("markdown" or "json")

        Returns:
            Dict with handoff content and metadata
        """
        today = utc_now().strftime("%Y-%m-%d")
        date_from = date_from or today
        date_to = date_to or today

        # Get timeline of events
        events = self.timeline(date_from=date_from, date_to=date_to)

        # Get journal entries with full content
        entries = self.journal_read(date_from=date_from, date_to=date_to)

        # Separate by type
        journal_entries = [e for e in entries if e.get("entry_type") != "amendment"]
        amendments = [e for e in entries if e.get("entry_type") == "amendment"]

        # Count outcomes
        outcomes = {"success": 0, "failure": 0, "partial": 0, "unknown": 0}
        for entry in journal_entries:
            outcome = entry.get("outcome", "unknown")
            if outcome in outcomes:
                outcomes[outcome] += 1

        # Get config changes
        config_events = [e for e in events if e["event_type"] == "config"]

        # Get log outcomes
        log_events = [e for e in events if e["event_type"] == "log"]
        log_outcomes = {"success": 0, "failure": 0, "interrupted": 0, "unknown": 0}
        for log in log_events:
            outcome = log.get("outcome", "unknown")
            if outcome in log_outcomes:
                log_outcomes[outcome] += 1

        # Find current state
        current_state = {
            "last_entry": journal_entries[-1] if journal_entries else None,
            "last_outcome": journal_entries[-1].get("outcome") if journal_entries else None,
            "config_changes": len(config_events),
            "log_count": len(log_events),
        }

        # Get recommended next steps from last entry
        next_steps = None
        if journal_entries and journal_entries[-1].get("next_steps"):
            next_steps = journal_entries[-1]["next_steps"]

        # Build handoff document
        if format == "markdown":
            content = self._format_handoff_markdown(
                date_from, date_to, journal_entries, amendments,
                config_events, log_events, outcomes, log_outcomes,
                current_state, next_steps
            )
        else:
            content = {
                "period": {"from": date_from, "to": date_to},
                "summary": {
                    "entry_count": len(journal_entries),
                    "amendment_count": len(amendments),
                    "config_changes": len(config_events),
                    "log_count": len(log_events),
                    "outcomes": outcomes,
                    "log_outcomes": log_outcomes,
                },
                "entries": journal_entries,
                "amendments": amendments,
                "config_events": config_events if include_configs else [],
                "log_events": log_events if include_logs else [],
                "current_state": current_state,
                "next_steps": next_steps,
            }

        return {
            "format": format,
            "date_from": date_from,
            "date_to": date_to,
            "content": content,
        }

    def _format_handoff_markdown(
        self,
        date_from: str,
        date_to: str,
        entries: list[dict],
        amendments: list[dict],
        config_events: list[dict],
        log_events: list[dict],
        outcomes: dict,
        log_outcomes: dict,
        current_state: dict,
        next_steps: Optional[str],
    ) -> str:
        """Format handoff as markdown."""
        lines = [
            f"# Session Handoff",
            f"**Period**: {date_from} to {date_to}",
            f"**Project**: {self.config.project_name}",
            "",
            "## Summary",
            f"- **Journal entries**: {len(entries)}",
            f"- **Amendments**: {len(amendments)}",
            f"- **Config changes**: {len(config_events)}",
            f"- **Logs preserved**: {len(log_events)}",
            "",
            "### Outcomes",
            f"- Success: {outcomes['success']}",
            f"- Failure: {outcomes['failure']}",
            f"- Partial: {outcomes['partial']}",
            "",
            "### Log Results",
            f"- Success: {log_outcomes['success']}",
            f"- Failure: {log_outcomes['failure']}",
            "",
        ]

        # Key events (chronological)
        if entries:
            lines.extend(["## Key Events", ""])
            for entry in entries:
                ts = entry.get("timestamp", "")[:16]  # Trim to minute
                outcome_str = f" [{entry.get('outcome', '')}]" if entry.get("outcome") else ""
                context = entry.get("context", "")[:80]
                lines.append(f"- **{ts}** ({entry['entry_id']}){outcome_str}: {context}")
            lines.append("")

        # Config changes
        if config_events:
            lines.extend(["## Config Changes", ""])
            for cfg in config_events:
                lines.append(f"- {cfg['timestamp'][:16]}: {cfg['summary']}")
            lines.append("")

        # Current state
        lines.extend(["## Current State", ""])
        if current_state["last_entry"]:
            last = current_state["last_entry"]
            lines.append(f"- **Last entry**: {last['entry_id']}")
            lines.append(f"- **Last outcome**: {current_state['last_outcome'] or 'N/A'}")
            if last.get("config_used"):
                lines.append(f"- **Active config**: {last['config_used']}")
        lines.append("")

        # Next steps
        if next_steps:
            lines.extend([
                "## Recommended Next Steps",
                "",
                next_steps,
                "",
            ])

        # Entry reference IDs for drilling down
        if entries:
            lines.extend([
                "## Entry References",
                "",
                "For detailed context, read these entries:",
                "",
            ])
            for entry in entries[-5:]:  # Last 5 entries
                lines.append(f"- `{entry['entry_id']}`: {entry.get('context', '')[:50]}...")
            lines.append("")

        return "\n".join(lines)

    # ========== Causality Tracing ==========

    def trace_causality(
        self,
        entry_id: str,
        direction: str = "both",
        depth: int = 10,
    ) -> dict:
        """Trace causality links from an entry.

        Args:
            entry_id: Starting entry ID
            direction: "forward" (effects), "backward" (causes), or "both"
            depth: Maximum depth to trace

        Returns:
            Dict with causality graph
        """
        # Read the starting entry
        entries = self.journal_read(entry_id=entry_id)
        if not entries:
            raise InvalidReferenceError(f"Entry not found: {entry_id}")

        start_entry = entries[0]
        graph = {
            "root": entry_id,
            "direction": direction,
            "nodes": {entry_id: start_entry},
            "edges": [],
        }

        visited = {entry_id}

        def trace_backward(eid: str, current_depth: int):
            if current_depth >= depth:
                return
            entries = self.journal_read(entry_id=eid)
            if not entries:
                return
            entry = entries[0]
            caused_by = entry.get("caused_by", [])
            for cause_id in caused_by:
                if cause_id not in visited:
                    visited.add(cause_id)
                    cause_entries = self.journal_read(entry_id=cause_id)
                    if cause_entries:
                        graph["nodes"][cause_id] = cause_entries[0]
                        graph["edges"].append({"from": cause_id, "to": eid, "type": "causes"})
                        trace_backward(cause_id, current_depth + 1)

        def trace_forward(eid: str, current_depth: int):
            if current_depth >= depth:
                return
            # Search for entries that have this entry in their caused_by
            all_entries = self.journal_read()
            for entry in all_entries:
                if eid in entry.get("caused_by", []):
                    effect_id = entry["entry_id"]
                    if effect_id not in visited:
                        visited.add(effect_id)
                        graph["nodes"][effect_id] = entry
                        graph["edges"].append({"from": eid, "to": effect_id, "type": "causes"})
                        trace_forward(effect_id, current_depth + 1)

        if direction in ["backward", "both"]:
            trace_backward(entry_id, 0)

        if direction in ["forward", "both"]:
            trace_forward(entry_id, 0)

        return graph

    # ========== Template Operations ==========

    def list_templates(self) -> list[dict]:
        """List available entry templates.

        Returns:
            List of template info dictionaries
        """
        templates = []
        for name, tmpl in self.config.templates.items():
            templates.append({
                "name": name,
                "description": tmpl.description,
                "required_fields": tmpl.required_fields,
                "optional_fields": tmpl.optional_fields,
                "default_outcome": tmpl.default_outcome,
            })
        return templates

    def get_template(self, name: str) -> Optional[dict]:
        """Get template details by name.

        Returns:
            Template info dictionary or None
        """
        tmpl = self.config.get_template(name)
        if tmpl is None:
            return None
        return {
            "name": tmpl.name,
            "description": tmpl.description,
            "context": tmpl.context,
            "intent": tmpl.intent,
            "action": tmpl.action,
            "observation": tmpl.observation,
            "analysis": tmpl.analysis,
            "next_steps": tmpl.next_steps,
            "required_fields": tmpl.required_fields,
            "optional_fields": tmpl.optional_fields,
            "default_outcome": tmpl.default_outcome,
        }

    # ========== Help System ==========

    _HELP_CONTENT = {
        "overview": {
            "brief": (
                "MCP Journal Server enforces scientific lab journal discipline. "
                "Core principle: Append-only, timestamped, attributed, complete, reproducible."
            ),
            "full": """MCP Journal Server enforces scientific lab journal discipline for software projects.

**Core Principle**: Append-only, timestamped, attributed, complete, reproducible.

Every action is recorded. Nothing is deleted. Full traceability from cause to effect.

**Directory Structure**:
- `journal/` - Daily markdown entries (YYYY-MM-DD.md)
- `configs/` - Archived configurations with INDEX.md
- `logs/` - Preserved logs with INDEX.md
- `snapshots/` - State captures (JSON) with INDEX.md

**Quick Start**:
1. Call `state_snapshot(name="session-start")` to capture initial state
2. Use `journal_append(...)` to document work
3. Use `config_archive(...)` before modifying configs
4. Use `log_preserve(...)` to preserve logs
5. Call `session_handoff(...)` to generate summary for next session

Use `journal_help(topic="workflow")` for detailed usage patterns.
Use `journal_help(topic="tools")` for tool reference.

**Complete Documentation**:
- User Guide: doc/user-guide.md
- Configuration: doc/configuration.md
- CLI Reference: doc/cli-reference.md
- API Reference: doc/api/README.md (man-page style for each tool)""",
        },
        "principles": {
            "brief": (
                "Five principles: Append-Only, Timestamped, Attributed, Complete, Reproducible."
            ),
            "full": """**The Five Core Principles**

1. **Append-Only**
   - Never delete, edit, or overwrite existing content
   - Use `journal_amend()` to correct previous entries
   - History is immutable and auditable

2. **Timestamped**
   - Every action has a precise UTC timestamp
   - Enables chronological reconstruction
   - Format: ISO 8601 (e.g., 2026-01-06T14:30:00Z)

3. **Attributed**
   - Every entry has an author
   - Enables accountability and filtering
   - Authors can be humans or AI agents

4. **Complete**
   - Capture full context, not just changes
   - Include intent, action, observation, analysis
   - Future readers should understand "why"

5. **Reproducible**
   - Archive everything needed to reproduce state
   - State snapshots capture configs, env, versions
   - Enables "time travel" debugging""",
        },
        "workflow": {
            "brief": (
                "Typical flow: snapshot -> journal intent -> archive config -> "
                "make changes -> preserve logs -> journal results -> handoff."
            ),
            "full": """**Recommended Workflow**

**Starting a Session**:
```
state_snapshot(name="session-start")
journal_append(author="...", context="Starting work on X", intent="Will do Y")
```

**Before Modifying Configs**:
```
config_archive(file_path="config.toml", reason="Adding new feature")
# Now safe to modify the file
```

**After Completing Work**:
```
log_preserve(file_path="build.log", category="build", outcome="success")
journal_append(
    author="...",
    action="Modified X, created Y",
    observation="Tests pass",
    outcome="success",
    caused_by=["previous-entry-id"]
)
```

**Ending a Session**:
```
session_handoff(include_configs=True, include_logs=True)
```

**Error Recovery**:
- Use `journal_amend()` to correct entries (never edit directly)
- Use `index_rebuild(directory="configs")` if INDEX.md is corrupted
- Use `trace_causality()` to understand what led to a problem""",
        },
        "tools": {
            "brief": (
                "16 tools: journal_append, journal_amend, journal_read, journal_search, "
                "config_archive, config_activate, config_diff, log_preserve, state_snapshot, "
                "timeline, trace_causality, session_handoff, list_templates, get_template, "
                "index_rebuild, journal_help."
            ),
            "full": """**Tool Reference**

**Journal Operations**:
- `journal_append` - Add timestamped entry (never edits existing)
- `journal_amend` - Add correction linking to original entry
- `journal_read` - Read entries by ID or date range
- `journal_search` - Search entries with filters

**Config Management**:
- `config_archive` - Archive config before modification
- `config_activate` - Restore archived config (archives current first)
- `config_diff` - Compare two config versions

**Log Preservation**:
- `log_preserve` - Move log with timestamp and outcome

**State Capture**:
- `state_snapshot` - Atomic capture of configs, env, versions

**Analysis & Navigation**:
- `timeline` - Unified chronological view of all events
- `trace_causality` - Follow cause-effect chains
- `session_handoff` - Generate AI context transfer summary

**Templates**:
- `list_templates` - Show available entry templates
- `get_template` - Get template details

**Recovery**:
- `index_rebuild` - Rebuild INDEX.md from files

**Help**:
- `journal_help` - This help system

Use `journal_help(tool="<name>")` for detailed help on any tool.

**API Documentation**: Full man(3) page style documentation available at doc/api/<tool_name>.md""",
        },
        "causality": {
            "brief": (
                "Link entries with caused_by parameter. Use trace_causality() to traverse the graph."
            ),
            "full": """**Causality Tracking**

Causality tracking enables "why did this happen?" analysis by linking entries.

**Entry IDs**: `YYYY-MM-DD-NNN` (e.g., 2026-01-06-003)

**Creating Causal Links**:
```
journal_append(
    author="claude",
    context="Fixing bug discovered in previous entry",
    caused_by=["2026-01-06-001", "2026-01-06-002"]
)
```

**Tracing the Graph**:
```
trace_causality(
    entry_id="2026-01-06-005",
    direction="backward",  # or "forward", "both"
    depth=10
)
```

**Returns**:
- `nodes` - All entries in the graph
- `edges` - Causal relationships
- `root` - Starting entry

**Use Cases**:
- Debugging: "What led to this failure?"
- Impact analysis: "What depends on this config?"
- Documentation: "Show the chain of reasoning" """,
        },
        "templates": {
            "brief": (
                "Templates ensure consistent entry formats. Use list_templates() and get_template()."
            ),
            "full": """**Template System**

Templates provide consistent entry formats for common scenarios.

**Listing Templates**:
```
list_templates()
# Returns: [{name, description, required_fields, optional_fields}, ...]
```

**Getting Template Details**:
```
get_template(name="build")
# Returns full template with field defaults
```

**Using Templates**:
```
journal_append(
    author="claude",
    template="build",
    template_values={
        "build_target": "release",
        "compiler": "gcc-12"
    }
)
```

**Template Configuration**:
Templates are defined in `journal_config.toml` or `journal_config.py`.

**Required Templates Mode**:
When `require_templates = true` in config, all entries must use a template.""",
        },
        "errors": {
            "brief": (
                "Common errors: DuplicateContentError, InvalidReferenceError, "
                "AppendOnlyViolation, TemplateRequiredError."
            ),
            "full": """**Error Handling Guide**

**DuplicateContentError**
- Cause: Archiving config with identical content to existing archive
- Action: Safe to ignore - content already preserved
- Prevention: Check if content changed before archiving

**InvalidReferenceError**
- Cause: Referenced entry ID or file doesn't exist
- Action: Verify entry ID format (YYYY-MM-DD-NNN)
- Prevention: Use journal_read() to verify entries exist

**AppendOnlyViolation**
- Cause: Attempted to edit or delete existing content
- Action: Use journal_amend() to add corrections
- Prevention: Never modify files in journal/ directory directly

**TemplateRequiredError**
- Cause: Template required but not provided
- Action: Use list_templates() and add template parameter
- Prevention: Check require_templates setting

**TemplateNotFoundError**
- Cause: Specified template doesn't exist
- Action: Use list_templates() to see available templates

**FileNotFoundError**
- Cause: Config/log file to archive doesn't exist
- Action: Verify file path

**Recovery Tools**:
- `journal_amend()` - Correct entries without editing
- `index_rebuild()` - Rebuild corrupted INDEX.md""",
        },
        "documentation": {
            "brief": (
                "Comprehensive documentation available in doc/ directory: "
                "user-guide.md, configuration.md, cli-reference.md, architecture.md, "
                "developer-guide.md, and api/*.md for each tool."
            ),
            "full": """**Documentation Index**

Complete documentation is available in the `doc/` directory of the project.

**User Documentation**:
- `doc/user-guide.md` - Installation, configuration, daily usage, best practices
- `doc/configuration.md` - All configuration options (TOML, JSON, Python)
- `doc/cli-reference.md` - Command-line interface reference

**Developer Documentation**:
- `doc/architecture.md` - System design, components, data flow
- `doc/developer-guide.md` - Contributing, code standards, testing

**API Reference** (`doc/api/`):
Man(3) page style documentation for each MCP tool:
- `journal_append.md` - Append entries
- `journal_amend.md` - Add amendments
- `journal_read.md` - Read entries
- `journal_query.md` - Query with filters
- `journal_search.md` - Full-text search
- `journal_stats.md` - Aggregated statistics
- `journal_active.md` - Find long-running operations
- `config_archive.md` - Archive configs
- `config_activate.md` - Restore configs
- `config_diff.md` - Compare configs
- `log_preserve.md` - Preserve logs
- `state_snapshot.md` - Capture state
- `timeline.md` - Chronological view
- `trace_causality.md` - Trace relationships
- `session_handoff.md` - Generate handoffs
- `index_rebuild.md` - Rebuild indexes
- `list_templates.md` - List templates
- `get_template.md` - Template details
- `journal_help.md` - Help system

**For AI Agents**:
Documentation is included with the package for runtime access.
Use this help system for quick reference, and read doc/api/*.md for complete details.""",
        },
    }

    _TOOL_HELP = {
        "journal_append": {
            "brief": "Add a timestamped entry to the daily journal.",
            "full": """**journal_append** - Add a timestamped entry to the daily journal

Never edits existing entries. Supports templates and causality tracking.

**Required Parameters**:
- `author` (string) - Who/what is making this entry

**Optional Parameters**:
- `context` - Current state, what we're trying to accomplish
- `intent` - What action we're about to take and why
- `action` - Commands executed, files modified
- `observation` - What happened, output received
- `analysis` - What does this mean, what did we learn
- `next_steps` - What should happen next
- `references` - Cross-references to files or entries
- `caused_by` - Entry IDs that caused this entry
- `config_used` - Config archive path used
- `log_produced` - Log path produced
- `outcome` - "success", "failure", or "partial"
- `template` - Template name to use
- `template_values` - Values for template placeholders""",
            "examples": """**Examples**:

Basic entry:
```json
{
    "author": "claude",
    "context": "Investigating build failure",
    "intent": "Check compiler version compatibility"
}
```

With causality:
```json
{
    "author": "claude",
    "action": "Fixed auth.py token handling",
    "observation": "All tests pass",
    "outcome": "success",
    "caused_by": ["2026-01-06-001"]
}
```

With template:
```json
{
    "author": "claude",
    "template": "build",
    "template_values": {"target": "release"}
}
```""",
        },
        "journal_amend": {
            "brief": "Add a correction to a previous entry (never edits original).",
            "full": """**journal_amend** - Add a correction to a previous entry

Creates a new amendment entry linking to the original. Original is never modified.

**Required Parameters**:
- `references_entry` - Entry ID being amended (e.g., "2026-01-06-003")
- `correction` - What was incorrect in the original
- `actual` - What is actually true
- `impact` - How this changes understanding
- `author` - Who is making this amendment""",
            "examples": """**Example**:
```json
{
    "references_entry": "2026-01-06-003",
    "correction": "Stated tests were passing",
    "actual": "One integration test was skipped due to network timeout",
    "impact": "Need to re-run integration tests before merge",
    "author": "claude"
}
```""",
        },
        "journal_read": {
            "brief": "Read journal entries by ID or date range.",
            "full": """**journal_read** - Read journal entries by ID or date range

**Optional Parameters** (at least one recommended):
- `entry_id` - Specific entry (e.g., "2026-01-06-003")
- `date` - All entries for a date (YYYY-MM-DD)
- `date_from` - Range start date
- `date_to` - Range end date
- `include_content` - Include full content (default: true)

If no parameters provided, returns all entries.""",
            "examples": """**Examples**:

Single entry:
```json
{"entry_id": "2026-01-06-003"}
```

Date range:
```json
{"date_from": "2026-01-01", "date_to": "2026-01-06"}
```""",
        },
        "journal_search": {
            "brief": "Search journal entries with text and filters.",
            "full": """**journal_search** - Search journal entries with filters

**Required Parameters**:
- `query` - Search term to find in entries

**Optional Filters**:
- `date_from` - Start date (YYYY-MM-DD)
- `date_to` - End date (YYYY-MM-DD)
- `author` - Filter by author
- `entry_type` - "entry" or "amendment" """,
            "examples": """**Example**:
```json
{
    "query": "authentication",
    "author": "claude",
    "date_from": "2026-01-01"
}
```""",
        },
        "config_archive": {
            "brief": "Archive a config file before modification.",
            "full": """**config_archive** - Archive a configuration file before modification

Computes SHA-256 hash. Refuses if identical content already archived.

**Required Parameters**:
- `file_path` - Path to the config file
- `reason` - Why the file is being archived

**Optional Parameters**:
- `stage` - Build stage (e.g., "stage1", "analysis")
- `journal_entry` - Link to journal entry explaining change""",
            "examples": """**Example**:
```json
{
    "file_path": "config/build.toml",
    "reason": "Adding LLVM optimization flags",
    "stage": "stage2",
    "journal_entry": "2026-01-06-005"
}
```""",
        },
        "config_activate": {
            "brief": "Restore an archived config as active.",
            "full": """**config_activate** - Set an archived config as active

Archives current target first if it exists (safety).

**Required Parameters**:
- `archive_path` - Path to archived config
- `target_path` - Where to place active copy
- `reason` - Why this config is being activated
- `journal_entry` - Link to journal entry (required)""",
            "examples": """**Example**:
```json
{
    "archive_path": "configs/build.2026-01-05.143000.toml",
    "target_path": "config/build.toml",
    "reason": "Reverting to known working config",
    "journal_entry": "2026-01-06-010"
}
```""",
        },
        "config_diff": {
            "brief": "Show diff between two config versions.",
            "full": """**config_diff** - Show diff between two config files

Use 'current:path' for active config comparison.

**Required Parameters**:
- `path_a` - First config path (archive or 'current:path/to/file')
- `path_b` - Second config path

**Optional Parameters**:
- `context_lines` - Lines of context around changes (default: 3)""",
            "examples": """**Example**:
```json
{
    "path_a": "configs/build.2026-01-05.143000.toml",
    "path_b": "current:config/build.toml",
    "context_lines": 5
}
```""",
        },
        "log_preserve": {
            "brief": "Preserve a log file with timestamp and outcome.",
            "full": """**log_preserve** - Preserve a log file by moving with timestamp

Never deletes - moves to logs/ directory with metadata.

**Required Parameters**:
- `file_path` - Path to the log file

**Optional Parameters**:
- `category` - Log category (e.g., "build", "test", "analysis")
- `outcome` - "success", "failure", "interrupted", or "unknown" """,
            "examples": """**Example**:
```json
{
    "file_path": "build/output.log",
    "category": "build",
    "outcome": "success"
}
```""",
        },
        "state_snapshot": {
            "brief": "Capture complete state atomically.",
            "full": """**state_snapshot** - Capture complete state atomically

Includes configs, environment variables, and tool versions.

**Required Parameters**:
- `name` - Snapshot name (e.g., "pre-build", "post-analysis")

**Optional Parameters**:
- `include_configs` - Include config contents (default: true)
- `include_env` - Include environment variables (default: true)
- `include_versions` - Include tool versions (default: true)
- `include_build_dir_listing` - Include build directory listing (default: false)
- `build_dir` - Build directory to list""",
            "examples": """**Example**:
```json
{
    "name": "pre-stage2-build",
    "include_configs": true,
    "include_versions": true,
    "include_build_dir_listing": true,
    "build_dir": "build/"
}
```""",
        },
        "timeline": {
            "brief": "Unified chronological view of all events.",
            "full": """**timeline** - Get unified chronological view of all events

Combines entries, configs, logs, and snapshots.

**Optional Parameters**:
- `date_from` - Start date (YYYY-MM-DD)
- `date_to` - End date (YYYY-MM-DD)
- `event_types` - Filter: ["entry", "amendment", "config", "log", "snapshot"]
- `limit` - Maximum events to return""",
            "examples": """**Example**:
```json
{
    "date_from": "2026-01-06",
    "event_types": ["entry", "config"],
    "limit": 50
}
```""",
        },
        "trace_causality": {
            "brief": "Trace cause-effect chains between entries.",
            "full": """**trace_causality** - Trace causality links from an entry

**Required Parameters**:
- `entry_id` - Starting entry ID

**Optional Parameters**:
- `direction` - "forward", "backward", or "both" (default: "both")
- `depth` - Maximum depth to trace (default: 10)

**Returns**:
- `nodes` - All entries in the graph
- `edges` - Causal relationships ({from, to, type})
- `root` - Starting entry ID""",
            "examples": """**Example**:
```json
{
    "entry_id": "2026-01-06-005",
    "direction": "backward",
    "depth": 5
}
```""",
        },
        "session_handoff": {
            "brief": "Generate context summary for AI session transfer.",
            "full": """**session_handoff** - Generate session summary for AI handoff

Creates a summary suitable for transferring context between AI sessions.

**Optional Parameters**:
- `date_from` - Start of session (default: today)
- `date_to` - End of session (default: today)
- `include_configs` - Include config change summary (default: true)
- `include_logs` - Include log outcome summary (default: true)
- `format` - "markdown" or "json" (default: "markdown")""",
            "examples": """**Example**:
```json
{
    "date_from": "2026-01-06",
    "include_configs": true,
    "include_logs": true,
    "format": "markdown"
}
```""",
        },
        "list_templates": {
            "brief": "List available entry templates.",
            "full": """**list_templates** - List available entry templates

No parameters required.

**Returns**:
- `templates` - List of {name, description, required_fields, optional_fields}
- `require_templates` - Whether templates are required""",
            "examples": """**Example**:
```json
{}
```""",
        },
        "get_template": {
            "brief": "Get details of a specific template.",
            "full": """**get_template** - Get template details

**Required Parameters**:
- `name` - Template name

**Returns**: Full template with all field definitions.""",
            "examples": """**Example**:
```json
{"name": "build"}
```""",
        },
        "index_rebuild": {
            "brief": "Rebuild INDEX.md from actual files (recovery).",
            "full": """**index_rebuild** - Rebuild INDEX.md from actual files

Recovery tool for corrupted or missing INDEX.md.

**Required Parameters**:
- `directory` - "configs", "logs", or "snapshots"

**Optional Parameters**:
- `dry_run` - Preview without writing (default: false)""",
            "examples": """**Example**:
```json
{
    "directory": "configs",
    "dry_run": true
}
```""",
        },
        "journal_help": {
            "brief": "Get documentation about the journal system.",
            "full": """**journal_help** - Get documentation about the journal system

**Optional Parameters**:
- `topic` - "overview", "principles", "workflow", "tools", "causality", "templates", "errors"
- `tool` - Get detailed help for a specific tool
- `detail` - "brief", "full", or "examples" (default: "full")

If no parameters, returns overview.""",
            "examples": """**Examples**:

Topic help:
```json
{"topic": "workflow", "detail": "full"}
```

Tool help:
```json
{"tool": "journal_append", "detail": "examples"}
```""",
        },
    }

    def journal_help(
        self,
        topic: Optional[str] = None,
        tool: Optional[str] = None,
        detail: str = "full",
    ) -> dict[str, Any]:
        """Get documentation about the journal system.

        Args:
            topic: Documentation topic (overview, principles, workflow, tools,
                   causality, templates, errors)
            tool: Specific tool to get help for
            detail: Level of detail (brief, full, examples)

        Returns:
            Help content dictionary
        """
        valid_topics = list(self._HELP_CONTENT.keys())
        valid_details = ["brief", "full", "examples"]

        # Validate detail level
        if detail not in valid_details:
            detail = "full"

        # Tool-specific help takes precedence
        if tool:
            tool_lower = tool.lower()
            if tool_lower in self._TOOL_HELP:
                tool_info = self._TOOL_HELP[tool_lower]
                if detail == "examples" and "examples" in tool_info:
                    content = tool_info["full"] + "\n\n" + tool_info["examples"]
                elif detail == "brief":
                    content = tool_info["brief"]
                else:
                    content = tool_info["full"]

                return {
                    "type": "tool",
                    "tool": tool_lower,
                    "detail": detail,
                    "content": content,
                    "related_topics": ["tools", "workflow"],
                }
            else:
                return {
                    "type": "error",
                    "error": f"Unknown tool: {tool}",
                    "available_tools": list(self._TOOL_HELP.keys()),
                }

        # Topic help
        if topic is None:
            topic = "overview"

        topic_lower = topic.lower()
        if topic_lower not in self._HELP_CONTENT:
            return {
                "type": "error",
                "error": f"Unknown topic: {topic}",
                "available_topics": valid_topics,
            }

        topic_info = self._HELP_CONTENT[topic_lower]
        if detail == "brief":
            content = topic_info["brief"]
        else:
            content = topic_info["full"]

        # Determine related topics
        related = [t for t in valid_topics if t != topic_lower][:3]

        return {
            "type": "topic",
            "topic": topic_lower,
            "detail": detail,
            "content": content,
            "related_topics": related,
        }
