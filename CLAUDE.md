# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP Journal Server - A Model Context Protocol server enforcing scientific lab journal discipline for software development and data analysis projects. Core principle: **append-only, timestamped, attributed, complete, reproducible**.

## Build & Test Commands

```bash
# Install dependencies
pip install -e .
pip install -e ".[dev]"

# Run tests
pytest
pytest tests/test_engine.py -v          # Specific test file
pytest -k "test_creates_journal"         # Run by name pattern

# Run server
mcp-journal --project-root /path/to/project
mcp-journal --init                        # Initialize journal dirs

# Type checking (if mypy installed)
mypy src/mcp_journal
```

## Architecture

### Source Structure

```
src/mcp_journal/
├── __init__.py      # Package init, version
├── server.py        # MCP server entry point, tool registration
├── engine.py        # Core journal operations (append-only logic)
├── tools.py         # MCP tool definitions and execution
├── config.py        # Configuration loading (TOML/JSON/Python)
├── models.py        # Data models (JournalEntry, ConfigArchive, etc.)
└── locking.py       # File locking for concurrent access
```

### Configuration Tiers

1. **Simple** (`journal_config.toml` / `.json`) - Declarative, most users
2. **Advanced** (`journal_config.py`) - Python module with hooks and custom tools:
   - `hook_*` functions → lifecycle hooks
   - `custom_tool_*` functions → additional MCP tools

### MCP Tools (8 built-in)

| Tool | Purpose |
|------|---------|
| `journal_append` | Add timestamped entries to daily journal (never edit existing) |
| `journal_amend` | Add amendments linking to original entries |
| `config_archive` | Archive config files before modification |
| `config_activate` | Set archived config as active (archives current first) |
| `log_preserve` | Move logs with timestamp (never delete) |
| `state_snapshot` | Capture complete build/analysis state atomically |
| `journal_search` | Search journal entries with filters |
| `index_rebuild` | Rebuild INDEX.md from actual files (recovery) |

### Managed Directory Structure

```
{project}/
├── journal/       # Daily markdown (YYYY-MM-DD.md) - append-only
├── configs/       # Archived configs with timestamps + INDEX.md
├── logs/          # Preserved logs with outcomes + INDEX.md
└── snapshots/     # Complete state captures (JSON) + INDEX.md
```

### Design Constraints

- **NEVER** delete, overwrite, or edit existing journal/config/log content
- Atomic operations via `locking.py` - all or nothing
- ISO 8601 timestamps with timezone
- Entry IDs: `{YYYY-MM-DD}-{sequence}` (e.g., `2026-01-06-003`)
- File locking via `portalocker` for concurrent access

## Development Environment

- **Primary Shell**: Cygwin (`/home/phdyex/my-repos/mcp-journal`)
- **Windows Path**: `C:\-\cygwin\root\home\phdyex\my-repos\mcp-journal`
- **Python**: 3.10+
- **Dependencies**: `mcp`, `tomli`, `tomli-w`, `portalocker`

## Key Files

- `prompt/handoff/initial.md` - Original requirements and tool specifications
- `doc/Future-Features.md` - Planned features (on hold)
- `examples/journal_config.toml` - Simple configuration example
- `examples/journal_config.py` - Advanced configuration with hooks/custom tools
