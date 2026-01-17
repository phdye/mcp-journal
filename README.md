# MCP Journal Server

[![PyPI version](https://badge.fury.io/py/mcp-journal.svg)](https://badge.fury.io/py/mcp-journal)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/phdyex/mcp-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/phdyex/mcp-journal/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/phdyex/mcp-journal)

A Model Context Protocol (MCP) server enforcing scientific lab journal discipline for software development and data analysis projects.

## Core Principle

**Append-only, timestamped, attributed, complete, reproducible.**

Every action is recorded. Nothing is deleted. Full traceability from cause to effect.

## Features

- **Append-Only Journal**: Daily markdown files with timestamped, attributed entries
- **Config Archival**: Archive configuration files before modification with content hashing
- **Log Preservation**: Move logs with timestamps and outcome classification
- **State Snapshots**: Atomic capture of configs, environment, and tool versions
- **Causality Tracking**: Link entries with `caused_by` relationships for full traceability
- **Session Handoff**: Generate AI-friendly summaries for context transfer
- **Templates**: Standardized entry formats for consistency

## Installation

```bash
# Basic installation (requires Python 3.10+)
pip install mcp-journal

# With MCP server support
pip install mcp-journal[mcp]

# With development dependencies
pip install mcp-journal[dev]

# Everything
pip install mcp-journal[all]
```

## Quick Start

```bash
# Initialize journal directories in your project
mcp-journal --init --project-root /path/to/project

# Run the MCP server
mcp-journal --project-root /path/to/project
```

This creates the following structure:

```
your-project/
├── journal/       # Daily markdown entries (YYYY-MM-DD.md)
├── configs/       # Archived configurations with INDEX.md
├── logs/          # Preserved logs with INDEX.md
└── snapshots/     # State snapshots (JSON) with INDEX.md
```

## Configuration

### Simple Configuration (TOML)

Create `journal_config.toml` in your project root:

```toml
[project]
name = "my-project"

[tracking]
config_patterns = ["*.toml", "*.json", "*.yaml"]
log_categories = ["build", "test", "deploy"]

[versions]
python = "python --version"
node = "node --version"
rust = "rustc --version"
```

### Advanced Configuration (Python)

For custom tools and hooks, create `journal_config.py`:

```python
"""Advanced journal configuration with hooks and custom tools."""

# Project settings
project_name = "my-project"
config_patterns = ["*.toml", "*.json"]

# Hooks
def hook_pre_append(entry, custom_fields):
    """Called before each journal entry is written."""
    # Add custom validation or modification
    return entry

def hook_post_append(entry):
    """Called after each journal entry is written."""
    # Trigger notifications, sync, etc.
    pass

def hook_capture_versions(engine):
    """Add custom version information to snapshots."""
    return {"custom_tool": "1.2.3"}

# Custom MCP tools
def custom_tool_deploy_check(engine, params):
    """Check deployment readiness.

    Args:
        params: {"environment": "staging"}
    """
    env = params.get("environment", "staging")
    return {"ready": True, "environment": env}
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `journal_append` | Add timestamped entries to daily journal (never edit existing) |
| `journal_amend` | Add amendments linking to original entries |
| `journal_read` | Read entries by ID, date, or range |
| `journal_search` | Search entries with filters |
| `config_archive` | Archive config files before modification |
| `config_activate` | Set archived config as active (archives current first) |
| `config_diff` | Show diff between two config versions |
| `log_preserve` | Move logs with timestamp (never delete) |
| `state_snapshot` | Capture complete build/analysis state atomically |
| `timeline` | Unified chronological view across all event types |
| `trace_causality` | Trace cause-effect relationships between entries |
| `session_handoff` | Generate context transfer summary for AI handoff |
| `index_rebuild` | Rebuild INDEX.md from actual files (recovery) |
| `list_templates` | List available entry templates |
| `get_template` | Get template details |

## Entry Format

Journal entries follow a structured markdown format:

```markdown
## 2026-01-06-003

**Timestamp**: 2026-01-06T14:30:00Z
**Author**: claude
**Type**: entry
**Outcome**: success
**Caused-By**: 2026-01-06-001, 2026-01-06-002
**Config**: configs/build.2026-01-06.143000.toml
**Log**: logs/build.2026-01-06.143000.success.log

### Context
Implementing new authentication module.

### Intent
Add OAuth2 support for third-party integrations.

### Action
Created oauth2.py with provider abstraction...

### Observation
All tests passing. Token refresh working correctly.

### Analysis
Implementation matches RFC 6749 requirements...

### Next Steps
- Add rate limiting
- Implement token revocation endpoint

---
```

## Causality Tracking

Track relationships between entries:

```python
# Entry caused by previous entries
engine.journal_append(
    author="claude",
    context="Fixed authentication bug",
    caused_by=["2026-01-06-001"],  # Links to causing entry
    config_used="configs/auth.toml",
    outcome="success",
)
```

Trace the causality graph:

```python
graph = engine.trace_causality(
    entry_id="2026-01-06-005",
    direction="both",  # or "forward", "backward"
    depth=10,
)
```

## Integration with Claude/AI

### MCP Server Configuration

Add to your Claude Desktop or MCP client configuration:

```json
{
  "mcpServers": {
    "journal": {
      "command": "mcp-journal",
      "args": ["--project-root", "/path/to/project"]
    }
  }
}
```

### Session Handoff

Generate context for AI session transfers:

```python
handoff = engine.session_handoff(
    date_from="2026-01-06",
    include_configs=True,
    include_logs=True,
    format="markdown",
)
```

### Claude Code Skills

Install slash commands for streamlined journal workflow:

```bash
# List available skills
mcp-journal --list-skills

# Install skills to ~/.claude/skills/
mcp-journal --install-skills

# Update skills (overwrite existing)
mcp-journal --install-skills --force

# Remove skills
mcp-journal --uninstall-skills
```

**Available Skills:**

| Skill | Purpose |
|-------|---------|
| `/journal-start` | Begin session with state snapshot and intent entry |
| `/journal-end` | End session with summary and handoff generation |
| `/journal-checkpoint` | Quick progress entry with causality linking |
| `/journal-config` | Archive config before modification |
| `/journal-log` | Preserve log file with outcome classification |
| `/journal-trace` | Trace causality chains between entries |

**Example Workflow:**

```
/journal-start Implementing authentication module
... do work ...
/journal-checkpoint Found existing auth utilities in utils/
... more work ...
/journal-config pyproject.toml Adding new dependency
... edit config ...
/journal-end Completed auth module, all tests passing
```

## Design Principles

1. **Append-Only**: Never delete, edit, or overwrite existing content
2. **Timestamped**: Every action has a precise UTC timestamp
3. **Attributed**: Every entry has an author
4. **Complete**: Capture full context, not just changes
5. **Reproducible**: Archive everything needed to reproduce state

## Development

```bash
# Clone the repository
git clone https://github.com/phdyex/mcp-journal.git
cd mcp-journal

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/mcp_journal --cov-report=term-missing

# Type checking (optional)
mypy src/mcp_journal
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
