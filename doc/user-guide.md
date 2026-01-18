# MCP Journal User Guide

**Version**: 0.2.0
**Last Updated**: 2026-01-17

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Core Concepts](#core-concepts)
5. [Directory Structure](#directory-structure)
6. [Journal Entries](#journal-entries)
7. [Configuration Management](#configuration-management)
8. [Log Preservation](#log-preservation)
9. [State Snapshots](#state-snapshots)
10. [Causality Tracking](#causality-tracking)
11. [Query and Search](#query-and-search)
12. [Templates](#templates)
13. [Session Management](#session-management)
14. [AI Integration](#ai-integration)
15. [CLI Usage](#cli-usage)
16. [Best Practices](#best-practices)
17. [Troubleshooting](#troubleshooting)

---

## Introduction

MCP Journal Server is a Model Context Protocol (MCP) server that enforces scientific lab journal discipline for software development and data analysis projects. It provides a systematic approach to recording, tracking, and reproducing work.

### Core Principle

**Append-only, timestamped, attributed, complete, reproducible.**

- **Append-only**: Nothing is ever deleted or overwritten
- **Timestamped**: Every action has a precise UTC timestamp
- **Attributed**: Every entry has a clear author
- **Complete**: Full context is captured, not just changes
- **Reproducible**: Everything needed to reproduce state is archived

### Use Cases

- **Build Systems**: Track build configurations, outcomes, and debug sessions
- **Data Analysis**: Record analysis steps, parameters, and observations
- **AI Development**: Maintain context across AI agent sessions
- **Debugging**: Create audit trails for complex debugging sessions
- **Compliance**: Meet audit requirements with immutable records

---

## Installation

### Requirements

- Python 3.10 or higher
- pip package manager

### Installation Options

```bash
# Basic installation
pip install mcp-journal

# With MCP server support (recommended)
pip install mcp-journal[mcp]

# With development dependencies
pip install mcp-journal[dev]

# Full installation with all extras
pip install mcp-journal[all]
```

### Verifying Installation

```bash
# Check version
mcp-journal --version

# View help
mcp-journal --help
```

### Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| `mcp` | MCP protocol support | Optional |
| `tomli` | TOML parsing (Python < 3.11) | Recommended |
| `tomli-w` | TOML writing | Recommended |
| `portalocker` | Cross-platform file locking | Required |

---

## Quick Start

### 1. Initialize a Project

```bash
# Create journal directories in your project
mcp-journal --init --project-root /path/to/your/project
```

This creates:
```
your-project/
├── journal/       # Daily journal entries
├── configs/       # Archived configurations
├── logs/          # Preserved logs
└── snapshots/     # State snapshots
```

### 2. Create a Configuration File (Optional)

Create `journal_config.toml` in your project root:

```toml
[project]
name = "my-project"

[tracking]
config_patterns = ["*.toml", "*.json", "*.yaml"]

[versions]
python = "python --version"
```

### 3. Run the MCP Server

```bash
# Start the server
mcp-journal --project-root /path/to/your/project
```

### 4. Connect Your AI Client

Configure your MCP client (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "journal": {
      "command": "mcp-journal",
      "args": ["--project-root", "/path/to/your/project"]
    }
  }
}
```

---

## Core Concepts

### Append-Only Discipline

The fundamental principle is that no data is ever deleted or modified. Instead:

1. **Journal entries** are appended to daily files
2. **Amendments** reference and correct previous entries
3. **Configurations** are archived before modification
4. **Logs** are moved (preserved), not deleted

### Entry Identification

Each journal entry has a unique ID in the format:

```
YYYY-MM-DD-NNN
```

Where:
- `YYYY-MM-DD` is the date
- `NNN` is a zero-padded sequence number (001, 002, etc.)

Example: `2026-01-17-003` (third entry on January 17, 2026)

### Timestamps

All timestamps use ISO 8601 format with UTC timezone:

```
2026-01-17T14:30:00.123456Z
```

### Authors

Every entry must have an author. Common conventions:
- `claude` - AI agent entries
- `human` - Human operator entries
- `system` - Automated system entries
- Specific names for identified individuals

---

## Directory Structure

### Standard Layout

```
project-root/
├── journal/                    # Journal entries
│   ├── 2026-01-15.md          # Daily journal files
│   ├── 2026-01-16.md
│   ├── 2026-01-17.md
│   └── .index.db              # SQLite search index
├── configs/                    # Archived configurations
│   ├── INDEX.md               # Configuration index
│   ├── build.2026-01-17.143000.toml
│   └── auth.2026-01-17.150000.json
├── logs/                       # Preserved logs
│   ├── INDEX.md               # Log index
│   ├── build.2026-01-17.143000.success.log
│   └── test.2026-01-17.150000.failure.log
├── snapshots/                  # State snapshots
│   ├── INDEX.md               # Snapshot index
│   └── 2026-01-17.143000.pre-build.json
└── journal_config.toml         # Configuration file
```

### File Naming Conventions

#### Journal Files
- Format: `YYYY-MM-DD.md`
- One file per day
- Contains all entries for that day

#### Archived Configurations
- Format: `{original_name}.{YYYY-MM-DD}.{HHMMSS}.{extension}`
- Preserves original filename
- Adds timestamp for uniqueness

#### Preserved Logs
- Format: `{category}.{YYYY-MM-DD}.{HHMMSS}.{outcome}.log`
- Categories: `build`, `test`, `deploy`, etc.
- Outcomes: `success`, `failure`, `interrupted`, `unknown`

#### Snapshots
- Format: `{YYYY-MM-DD}.{HHMMSS}.{name}.json`
- Name is user-provided description

---

## Journal Entries

### Entry Structure

Journal entries follow a structured markdown format:

```markdown
## 2026-01-17-001

**Timestamp**: 2026-01-17T14:30:00.123456Z
**Author**: claude
**Type**: entry
**Outcome**: success
**Template**: build
**Caused-By**: 2026-01-16-005
**Config**: configs/build.2026-01-17.143000.toml
**Log**: logs/build.2026-01-17.143000.success.log

### Context
Starting build process for authentication module.

### Intent
Compile and test the new OAuth2 implementation.

### Action
Ran `make build` with optimized settings.

### Observation
Build completed in 45 seconds. All 127 tests passed.

### Analysis
Performance improved 15% from previous build due to caching.

### Next Steps
- Deploy to staging environment
- Run integration tests

---
```

### Entry Fields

#### Required Fields

| Field | Description |
|-------|-------------|
| `entry_id` | Unique identifier (YYYY-MM-DD-NNN) |
| `timestamp` | UTC timestamp of entry creation |
| `author` | Who/what created the entry |
| `entry_type` | `entry` or `amendment` |

#### Optional Fields

| Field | Description |
|-------|-------------|
| `context` | Current state, what we're trying to accomplish |
| `intent` | What action we're about to take and why |
| `action` | Commands executed, files modified |
| `observation` | What happened, output received |
| `analysis` | What this means, what we learned |
| `next_steps` | What should happen next |
| `outcome` | `success`, `failure`, or `partial` |
| `caused_by` | Entry IDs that led to this entry |
| `config_used` | Path to configuration used |
| `log_produced` | Path to log produced |
| `references` | Cross-references to files or entries |
| `template` | Template name used |

#### Diagnostic Fields (for tool tracking)

| Field | Description |
|-------|-------------|
| `tool` | Tool name (bash, read_file, etc.) |
| `command` | Command executed |
| `duration_ms` | Duration in milliseconds |
| `exit_code` | Exit code for commands |
| `error_type` | Type of error if failure |

### Creating Entries

#### Via MCP Tool

```json
{
  "tool": "journal_append",
  "arguments": {
    "author": "claude",
    "context": "Building authentication module",
    "intent": "Implement OAuth2 support",
    "outcome": "success"
  }
}
```

#### Via Python API

```python
from mcp_journal.engine import JournalEngine
from mcp_journal.config import ProjectConfig

config = ProjectConfig(project_root="/path/to/project")
engine = JournalEngine(config)

entry = engine.journal_append(
    author="claude",
    context="Building authentication module",
    intent="Implement OAuth2 support",
    outcome="success",
)
print(f"Created entry: {entry.entry_id}")
```

### Amendments

Amendments correct or update previous entries without modifying them:

```json
{
  "tool": "journal_amend",
  "arguments": {
    "references_entry": "2026-01-17-001",
    "correction": "Exit code was actually 1, not 0",
    "actual": "Build failed due to missing dependency",
    "impact": "Need to rerun build after installing dependency",
    "author": "claude"
  }
}
```

---

## Configuration Management

### Archiving Configurations

Before modifying any configuration file, archive it:

```json
{
  "tool": "config_archive",
  "arguments": {
    "file_path": "build.toml",
    "reason": "Updating compiler flags",
    "journal_entry": "2026-01-17-001"
  }
}
```

This:
1. Copies the file to `configs/` with a timestamp
2. Records the content hash for verification
3. Updates `configs/INDEX.md`
4. Returns the archive path

### Duplicate Detection

The system detects when you try to archive identical content:

```python
# First archive succeeds
record1 = engine.config_archive("build.toml", "Initial")

# Second archive with same content fails
try:
    record2 = engine.config_archive("build.toml", "Same content")
except DuplicateContentError as e:
    print(f"Already archived at: {e.existing_path}")
```

### Activating Configurations

To restore a previous configuration:

```json
{
  "tool": "config_activate",
  "arguments": {
    "archive_path": "configs/build.2026-01-15.100000.toml",
    "target_path": "build.toml",
    "reason": "Reverting to working configuration",
    "journal_entry": "2026-01-17-003"
  }
}
```

This automatically archives the current version before overwriting.

### Comparing Configurations

```json
{
  "tool": "config_diff",
  "arguments": {
    "path_a": "configs/build.2026-01-15.100000.toml",
    "path_b": "current:build.toml",
    "context_lines": 3
  }
}
```

Use `current:` prefix to compare with active files.

---

## Log Preservation

### Preserving Logs

Never delete logs—preserve them:

```json
{
  "tool": "log_preserve",
  "arguments": {
    "file_path": "build.log",
    "category": "build",
    "outcome": "success"
  }
}
```

### Categories

Standard log categories:
- `build` - Compilation and build logs
- `test` - Test execution logs
- `deploy` - Deployment logs
- `analysis` - Data analysis logs
- `debug` - Debug session logs

### Outcomes

- `success` - Operation completed successfully
- `failure` - Operation failed
- `interrupted` - Operation was interrupted
- `unknown` - Outcome not determined

### Log Index

The `logs/INDEX.md` maintains a chronological list:

```markdown
# Log Preservation Index

| Timestamp | Category | Outcome | Path |
|-----------|----------|---------|------|
| 2026-01-17T14:30:00Z | build | success | build.2026-01-17.143000.success.log |
| 2026-01-17T15:00:00Z | test | failure | test.2026-01-17.150000.failure.log |
```

---

## State Snapshots

### Creating Snapshots

Capture complete system state atomically:

```json
{
  "tool": "state_snapshot",
  "arguments": {
    "name": "pre-build",
    "include_configs": true,
    "include_env": true,
    "include_versions": true,
    "include_build_dir_listing": true,
    "build_dir": "build"
  }
}
```

### Snapshot Contents

A snapshot captures:

1. **Configurations**: Content of all tracked config files
2. **Environment**: All environment variables
3. **Versions**: Output of version commands
4. **Build Directory**: File listing if requested
5. **Custom Data**: User-provided metadata

### Snapshot Format

Snapshots are stored as JSON:

```json
{
  "name": "pre-build",
  "timestamp": "2026-01-17T14:30:00.123456Z",
  "configs": {
    "build.toml": "[build]\noptimize = true"
  },
  "environment": {
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/user"
  },
  "versions": {
    "python": "3.10.0",
    "rust": "1.70.0"
  },
  "build_dir_listing": [
    "src/main.rs",
    "src/lib.rs"
  ]
}
```

### Version Commands

Configure version commands in `journal_config.toml`:

```toml
[versions]
python = "python --version"
rust = "rustc --version"
node = "node --version"

# With regex extraction
[versions.gcc]
command = "gcc --version"
parse_regex = "gcc \\(.*\\) (\\d+\\.\\d+\\.\\d+)"
```

---

## Causality Tracking

### Linking Entries

Connect related entries with `caused_by`:

```json
{
  "tool": "journal_append",
  "arguments": {
    "author": "claude",
    "context": "Fixing build failure",
    "caused_by": ["2026-01-17-001", "2026-01-17-002"],
    "config_used": "configs/build.2026-01-17.143000.toml",
    "outcome": "success"
  }
}
```

### Tracing Causality

Explore the cause-effect graph:

```json
{
  "tool": "trace_causality",
  "arguments": {
    "entry_id": "2026-01-17-005",
    "direction": "both",
    "depth": 10
  }
}
```

Directions:
- `forward` - What did this entry cause?
- `backward` - What caused this entry?
- `both` - Full bidirectional graph

### Causality Graph Structure

```json
{
  "root": "2026-01-17-005",
  "nodes": {
    "2026-01-17-001": {
      "timestamp": "2026-01-17T10:00:00Z",
      "author": "claude",
      "context": "Initial task"
    },
    "2026-01-17-005": {
      "timestamp": "2026-01-17T14:00:00Z",
      "author": "claude",
      "context": "Follow-up work"
    }
  },
  "edges": {
    "2026-01-17-001": ["2026-01-17-003"],
    "2026-01-17-003": ["2026-01-17-005"]
  }
}
```

---

## Query and Search

### Basic Queries

Query entries with filters:

```json
{
  "tool": "journal_query",
  "arguments": {
    "filters": {
      "author": "claude",
      "outcome": "failure"
    },
    "limit": 10,
    "order_by": "timestamp",
    "order_desc": true
  }
}
```

### Text Search

Full-text search across entry content:

```json
{
  "tool": "journal_query",
  "arguments": {
    "text_search": "authentication error",
    "date_from": "2026-01-15",
    "date_to": "2026-01-17"
  }
}
```

### Statistics

Aggregate statistics:

```json
{
  "tool": "journal_stats",
  "arguments": {
    "group_by": "outcome",
    "date_from": "2026-01-01"
  }
}
```

Available groupings:
- `outcome` - Group by success/failure/partial
- `author` - Group by entry author
- `tool` - Group by tool name (diagnostic entries)
- `template` - Group by template used

### Finding Active Operations

Find potentially hung or long-running operations:

```json
{
  "tool": "journal_active",
  "arguments": {
    "threshold_ms": 60000,
    "tool_filter": "bash"
  }
}
```

### Timeline View

Get a unified chronological view:

```json
{
  "tool": "timeline",
  "arguments": {
    "date_from": "2026-01-17",
    "event_types": ["entry", "config", "log"],
    "limit": 50
  }
}
```

Event types:
- `entry` - Journal entries
- `amendment` - Amendments
- `config` - Configuration archives
- `log` - Log preservations
- `snapshot` - State snapshots

---

## Templates

### Built-in Templates

Three default templates are available:

#### Diagnostic Template
For tool call tracking:
```json
{
  "template": "diagnostic",
  "template_values": {
    "tool": "bash",
    "status": "completed"
  }
}
```

#### Build Template
For build operations:
```json
{
  "template": "build",
  "template_values": {
    "target": "release"
  }
}
```

#### Test Template
For test execution:
```json
{
  "template": "test",
  "template_values": {
    "target": "unit-tests"
  }
}
```

### Custom Templates

Define templates in `journal_config.toml`:

```toml
[[templates]]
name = "deployment"
description = "Deployment operation entry"
required_fields = ["environment", "version"]
optional_fields = ["rollback_plan", "validation_steps"]
default_outcome = "partial"

[[templates]]
name = "analysis"
description = "Data analysis entry"
required_fields = ["dataset", "method"]
optional_fields = ["parameters", "results"]
```

### Using Templates

```json
{
  "tool": "journal_append",
  "arguments": {
    "author": "claude",
    "template": "deployment",
    "template_values": {
      "environment": "staging",
      "version": "1.2.3"
    }
  }
}
```

### Listing Templates

```json
{
  "tool": "list_templates",
  "arguments": {}
}
```

### Getting Template Details

```json
{
  "tool": "get_template",
  "arguments": {
    "name": "deployment"
  }
}
```

---

## Session Management

### Session Handoff

Generate context for AI session transfers:

```json
{
  "tool": "session_handoff",
  "arguments": {
    "date_from": "2026-01-17",
    "include_configs": true,
    "include_logs": true,
    "format": "markdown"
  }
}
```

### Handoff Content

The handoff includes:

1. **Summary**: Overview of session activity
2. **Recent Entries**: Last N entries with context
3. **Config Changes**: Configurations modified
4. **Log Outcomes**: Build/test results
5. **Active Config**: Currently active configuration
6. **Recommendations**: Suggested next steps

### Formats

- `markdown` - Human-readable markdown (default)
- `json` - Structured JSON for programmatic use

---

## AI Integration

### MCP Server Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "journal": {
      "command": "mcp-journal",
      "args": ["--project-root", "/path/to/project"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Recommended AI Workflow

1. **Session Start**
   ```json
   {"tool": "state_snapshot", "arguments": {"name": "session-start"}}
   {"tool": "journal_append", "arguments": {"author": "claude", "context": "Starting session", "intent": "..."}}
   ```

2. **During Work**
   ```json
   {"tool": "journal_append", "arguments": {"author": "claude", "context": "...", "action": "...", "observation": "..."}}
   ```

3. **Before Config Changes**
   ```json
   {"tool": "config_archive", "arguments": {"file_path": "...", "reason": "..."}}
   ```

4. **After Build/Test**
   ```json
   {"tool": "log_preserve", "arguments": {"file_path": "...", "category": "build", "outcome": "success"}}
   ```

5. **Session End**
   ```json
   {"tool": "session_handoff", "arguments": {"format": "markdown"}}
   ```

### Getting Help

Use the `journal_help` tool:

```json
// Get overview
{"tool": "journal_help", "arguments": {}}

// Get specific topic
{"tool": "journal_help", "arguments": {"topic": "workflow"}}

// Get tool help
{"tool": "journal_help", "arguments": {"tool": "journal_append"}}

// Get examples
{"tool": "journal_help", "arguments": {"tool": "config_archive", "detail": "examples"}}
```

Available topics:
- `overview` - System overview
- `principles` - Core principles
- `workflow` - Recommended workflow
- `tools` - Tool overview
- `causality` - Causality tracking
- `templates` - Template system
- `errors` - Error handling

---

## CLI Usage

### Basic Commands

```bash
# Initialize project
mcp-journal --init --project-root /path/to/project

# Run MCP server
mcp-journal --project-root /path/to/project

# Use specific config file
mcp-journal --project-root /path/to/project --config /path/to/config.toml
```

### Query Commands

```bash
# Query entries
mcp-journal query --tool bash --outcome failure --since today

# Text search
mcp-journal search "authentication error" --author claude

# Statistics
mcp-journal stats --by outcome --since 2026-01-01

# Active operations
mcp-journal active --threshold 60s

# Export entries
mcp-journal export --format json --since yesterday > entries.json
```

### Maintenance Commands

```bash
# Rebuild SQLite index
mcp-journal rebuild-index

# Rebuild INDEX.md files
# (via MCP tool: index_rebuild)
```

See [CLI Reference](cli-reference.md) for complete documentation.

---

## Best Practices

### 1. Always Archive Before Modifying

Never modify a configuration without archiving first:

```json
// WRONG
{"tool": "write_file", "arguments": {"path": "build.toml", ...}}

// RIGHT
{"tool": "config_archive", "arguments": {"file_path": "build.toml", "reason": "..."}}
// Then modify
```

### 2. Use Meaningful Context

Provide enough context for future readers:

```json
// WRONG
{"context": "Fixed bug"}

// RIGHT
{"context": "Fixed authentication timeout bug that occurred when OAuth tokens expired during long-running operations"}
```

### 3. Link Related Entries

Use `caused_by` to create audit trails:

```json
{
  "caused_by": ["2026-01-17-001"],
  "context": "Implementing fix suggested in previous entry"
}
```

### 4. Categorize Outcomes

Always specify outcomes for trackability:

```json
{"outcome": "success"}  // or "failure" or "partial"
```

### 5. Use Templates for Consistency

Define templates for repetitive entry types:

```json
{
  "template": "build",
  "template_values": {"target": "release"}
}
```

### 6. Preserve All Logs

Never delete logs—preserve them:

```bash
# WRONG
rm build.log

# RIGHT
mcp-journal log_preserve --file build.log --category build --outcome success
```

### 7. Snapshot Before Major Operations

Create snapshots before significant changes:

```json
{"tool": "state_snapshot", "arguments": {"name": "pre-major-refactor"}}
```

### 8. Use Handoffs for Context Transfer

Generate handoffs when switching AI sessions:

```json
{"tool": "session_handoff", "arguments": {"format": "markdown"}}
```

---

## Troubleshooting

### Common Issues

#### "Device or resource busy" Error

**Cause**: SQLite database is locked by another process.

**Solution**:
1. Ensure no other MCP server instances are running
2. Check for orphaned Python processes
3. Delete `.index.db` and rebuild: `mcp-journal rebuild-index`

#### "Entry not found" Error

**Cause**: Referenced entry ID doesn't exist.

**Solution**:
1. Verify the entry ID format (YYYY-MM-DD-NNN)
2. Check the journal file exists for that date
3. Use `journal_read` to list entries for the date

#### "Duplicate content" Error

**Cause**: Trying to archive identical content.

**Solution**:
1. Check if the file was already archived
2. Use the existing archive path
3. Only archive if content has changed

#### Configuration Not Loading

**Cause**: Config file not found or invalid.

**Solution**:
1. Verify config file name: `journal_config.toml`, `.toml`, `.json`, or `.py`
2. Check TOML/JSON syntax
3. Use `--config` to specify explicit path

#### Missing Templates

**Cause**: Custom templates not defined.

**Solution**:
1. Check template definition in config
2. Use `list_templates` to see available templates
3. Verify required fields are provided

### Getting Help

1. **Runtime Help**: Use `journal_help` tool
2. **Documentation**: See [doc/](.) directory
3. **Issues**: Open GitHub issue at [github.com/phdyex/mcp-journal/issues](https://github.com/phdyex/mcp-journal/issues)

### Debug Mode

Enable debug logging:

```bash
PYTHONUNBUFFERED=1 mcp-journal --project-root /path/to/project 2>&1 | tee debug.log
```

---

## See Also

- [Configuration Reference](configuration.md)
- [CLI Reference](cli-reference.md)
- [API Reference](api/README.md)
- [Architecture](architecture.md)
- [Developer Guide](developer-guide.md)
