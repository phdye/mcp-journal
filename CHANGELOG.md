# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-06

### Added

- Initial release
- Core journal engine with append-only semantics
- MCP server integration for AI tool use
- Journal operations:
  - `journal_append` - Add timestamped entries
  - `journal_amend` - Add amendments to existing entries
  - `journal_read` - Read entries by ID or date range
  - `journal_search` - Search with filters
- Configuration management:
  - `config_archive` - Archive before modification
  - `config_activate` - Restore archived configs
  - `config_diff` - Compare config versions
- Log preservation:
  - `log_preserve` - Move logs with timestamps and outcomes
- State snapshots:
  - `state_snapshot` - Atomic state capture
  - Environment, configs, and tool versions
- Causality tracking:
  - `caused_by` relationships between entries
  - `trace_causality` - Graph traversal
- Session handoff:
  - `session_handoff` - AI context transfer summaries
- Timeline view:
  - `timeline` - Unified chronological view
- Template support:
  - Entry templates for consistency
  - `list_templates` and `get_template` tools
- Index management:
  - `index_rebuild` - Recovery from INDEX.md corruption
- Configuration options:
  - TOML configuration (`journal_config.toml`)
  - Python configuration with hooks (`journal_config.py`)
  - Custom tool support
- File locking for concurrent access safety
- 100% test coverage

### Security

- Content hashing for config archives (SHA-256)
- Append-only design prevents tampering with history

[Unreleased]: https://github.com/phdyex/mcp-journal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/phdyex/mcp-journal/releases/tag/v0.1.0
