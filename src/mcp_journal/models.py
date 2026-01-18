"""Data models for journal entries, configs, logs, and snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class EntryType(Enum):
    """Type of journal entry."""
    ENTRY = "entry"
    AMENDMENT = "amendment"


class LogOutcome(Enum):
    """Outcome of a logged operation."""
    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def generate_entry_id(date: datetime, sequence: int) -> str:
    """Generate entry ID in format YYYY-MM-DD-NNN."""
    return f"{date.strftime('%Y-%m-%d')}-{sequence:03d}"


def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 with timezone."""
    return dt.isoformat(timespec='milliseconds')


def parse_timestamp(s: str) -> datetime:
    """Parse ISO 8601 timestamp string."""
    return datetime.fromisoformat(s)


@dataclass
class JournalEntry:
    """A single journal entry."""
    entry_id: str
    timestamp: datetime
    author: str
    entry_type: EntryType = EntryType.ENTRY

    # Content fields
    context: Optional[str] = None
    intent: Optional[str] = None
    action: Optional[str] = None
    observation: Optional[str] = None
    analysis: Optional[str] = None
    next_steps: Optional[str] = None

    # For amendments
    references_entry: Optional[str] = None
    correction: Optional[str] = None
    actual: Optional[str] = None
    impact: Optional[str] = None

    # Cross-references
    references: list[str] = field(default_factory=list)

    # Causality links
    caused_by: list[str] = field(default_factory=list)  # Entry IDs that led to this
    causes: list[str] = field(default_factory=list)      # Entry IDs this leads to
    config_used: Optional[str] = None                     # Config archive path used
    log_produced: Optional[str] = None                    # Log path produced
    outcome: Optional[str] = None                         # success/failure/partial

    # Template used (if any)
    template: Optional[str] = None

    # Diagnostic fields (for tool call tracking)
    tool: Optional[str] = None           # Tool name (bash, read_file, etc.)
    duration_ms: Optional[int] = None    # Duration in milliseconds
    exit_code: Optional[int] = None      # Exit code for commands
    command: Optional[str] = None        # Command executed
    error_type: Optional[str] = None     # Type of error if failure

    def to_markdown(self) -> str:
        """Render entry as markdown."""
        lines = [
            f"## {self.entry_id}",
            f"**Timestamp**: {format_timestamp(self.timestamp)}",
            f"**Author**: {self.author}",
            f"**Type**: {self.entry_type.value}",
        ]

        # Add causality metadata if present
        if self.outcome:
            lines.append(f"**Outcome**: {self.outcome}")
        if self.template:
            lines.append(f"**Template**: {self.template}")
        if self.config_used:
            lines.append(f"**Config**: {self.config_used}")
        if self.log_produced:
            lines.append(f"**Log**: {self.log_produced}")
        if self.caused_by:
            lines.append(f"**Caused-By**: {', '.join(self.caused_by)}")
        if self.causes:
            lines.append(f"**Causes**: {', '.join(self.causes)}")

        # Add diagnostic metadata if present
        if self.tool:
            lines.append(f"**Tool**: {self.tool}")
        if self.duration_ms is not None:
            lines.append(f"**Duration**: {self.duration_ms}ms")
        if self.exit_code is not None:
            lines.append(f"**Exit-Code**: {self.exit_code}")
        if self.command:
            lines.append(f"**Command**: {self.command}")
        if self.error_type:
            lines.append(f"**Error-Type**: {self.error_type}")

        lines.append("")

        if self.entry_type == EntryType.AMENDMENT:
            lines.extend([
                f"**Amends**: {self.references_entry}",
                "",
                "### Correction",
                self.correction or "",
                "",
                "### Actual",
                self.actual or "",
                "",
                "### Impact",
                self.impact or "",
            ])
        else:
            if self.context:
                lines.extend(["### Context", self.context, ""])
            if self.intent:
                lines.extend(["### Intent", self.intent, ""])
            if self.action:
                lines.extend(["### Action", self.action, ""])
            if self.observation:
                lines.extend(["### Observation", self.observation, ""])
            if self.analysis:
                lines.extend(["### Analysis", self.analysis, ""])
            if self.next_steps:
                lines.extend(["### Next Steps", self.next_steps, ""])

        if self.references:
            lines.extend(["### References"])
            for ref in self.references:
                lines.append(f"- {ref}")
            lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert entry to dictionary for JSON serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": format_timestamp(self.timestamp),
            "author": self.author,
            "entry_type": self.entry_type.value,
            "context": self.context,
            "intent": self.intent,
            "action": self.action,
            "observation": self.observation,
            "analysis": self.analysis,
            "next_steps": self.next_steps,
            "references_entry": self.references_entry,
            "correction": self.correction,
            "actual": self.actual,
            "impact": self.impact,
            "references": self.references,
            "caused_by": self.caused_by,
            "causes": self.causes,
            "config_used": self.config_used,
            "log_produced": self.log_produced,
            "outcome": self.outcome,
            "template": self.template,
            "tool": self.tool,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "command": self.command,
            "error_type": self.error_type,
        }


@dataclass
class EntryTemplate:
    """Template for journal entries - enforces consistent structure."""
    name: str
    description: str
    context_template: Optional[str] = None
    intent_template: Optional[str] = None
    action_template: Optional[str] = None
    observation_template: Optional[str] = None
    analysis_template: Optional[str] = None
    next_steps_template: Optional[str] = None
    required_fields: list[str] = field(default_factory=list)  # Template variables that must be provided
    optional_fields: list[str] = field(default_factory=list)  # Template variables that are optional
    default_outcome: Optional[str] = None  # Default outcome if not specified

    def render(self, values: dict[str, str]) -> dict[str, Optional[str]]:
        """Render template with provided values.

        Args:
            values: Dict of template variable values

        Returns:
            Dict of rendered fields

        Raises:
            ValueError: If required fields are missing
        """
        missing = [f for f in self.required_fields if f not in values]
        if missing:
            raise ValueError(f"Missing required template fields: {missing}")

        def render_field(template: Optional[str]) -> Optional[str]:
            if template is None:
                return None
            try:
                return template.format(**values)
            except KeyError as e:
                raise ValueError(f"Template variable not provided: {e}")

        return {
            "context": render_field(self.context_template),
            "intent": render_field(self.intent_template),
            "action": render_field(self.action_template),
            "observation": render_field(self.observation_template),
            "analysis": render_field(self.analysis_template),
            "next_steps": render_field(self.next_steps_template),
        }


class TimelineEventType(Enum):
    """Type of timeline event."""
    JOURNAL_ENTRY = "entry"
    JOURNAL_AMENDMENT = "amendment"
    CONFIG_ARCHIVE = "config"
    LOG_PRESERVE = "log"
    SNAPSHOT = "snapshot"


@dataclass
class TimelineEvent:
    """A unified timeline event from any source."""
    timestamp: datetime
    event_type: TimelineEventType
    summary: str
    entry_id: Optional[str] = None      # For journal entries
    path: Optional[str] = None          # For configs/logs/snapshots
    outcome: Optional[str] = None       # For logs
    author: Optional[str] = None        # For journal entries
    details: Optional[dict] = None      # Additional context

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": format_timestamp(self.timestamp),
            "event_type": self.event_type.value,
            "summary": self.summary,
            "entry_id": self.entry_id,
            "path": self.path,
            "outcome": self.outcome,
            "author": self.author,
            "details": self.details,
        }


@dataclass
class ConfigArchive:
    """Record of an archived configuration file."""
    original_path: str
    archive_path: str
    timestamp: datetime
    reason: str
    stage: Optional[str] = None
    journal_entry: Optional[str] = None
    content_hash: Optional[str] = None

    def to_index_line(self) -> str:
        """Format as markdown table row for INDEX.md."""
        stage_str = self.stage or "-"
        entry_str = self.journal_entry or "-"
        return f"| {format_timestamp(self.timestamp)} | {self.archive_path} | {stage_str} | {self.reason} | {entry_str} |"


@dataclass
class LogPreservation:
    """Record of a preserved log file."""
    original_path: str
    preserved_path: str
    timestamp: datetime
    category: Optional[str] = None
    outcome: LogOutcome = LogOutcome.UNKNOWN

    def to_index_line(self) -> str:
        """Format as markdown table row for INDEX.md."""
        cat_str = self.category or "-"
        return f"| {format_timestamp(self.timestamp)} | {self.preserved_path} | {cat_str} | {self.outcome.value} |"


@dataclass
class StateSnapshot:
    """A complete state snapshot."""
    name: str
    timestamp: datetime
    snapshot_path: str
    configs: Optional[dict] = None
    environment: Optional[dict] = None
    versions: Optional[dict] = None
    build_dir_listing: Optional[list[str]] = None
    custom_data: Optional[dict] = None

    def to_index_line(self) -> str:
        """Format as markdown table row for INDEX.md."""
        contents = []
        if self.configs:
            contents.append("configs")
        if self.environment:
            contents.append("env")
        if self.versions:
            contents.append("versions")
        if self.build_dir_listing:
            contents.append("listing")
        if self.custom_data:
            contents.append("custom")
        return f"| {format_timestamp(self.timestamp)} | {self.snapshot_path} | {self.name} | {', '.join(contents)} |"
