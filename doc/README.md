# MCP Journal Documentation

**Version**: 0.2.0
**Last Updated**: 2026-01-17

This directory contains comprehensive documentation for the MCP Journal Server, a Model Context Protocol (MCP) server enforcing scientific lab journal discipline for software development and data analysis projects.

## Documentation Index

### User Documentation

| Document | Description |
|----------|-------------|
| [User Guide](user-guide.md) | Complete guide for end users covering installation, configuration, daily usage patterns, and best practices |
| [Configuration Reference](configuration.md) | Comprehensive reference for all configuration options (TOML, JSON, Python) |
| [CLI Reference](cli-reference.md) | Command-line interface reference with examples for all commands |

### Developer Documentation

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System architecture, design decisions, component interactions, and data flow |
| [Developer Guide](developer-guide.md) | Contributing guidelines, code standards, testing practices, and development setup |
| [API Reference](api/README.md) | Complete API documentation for all MCP tools in man(3) page style |

### API Reference (man(3) Style)

The [api/](api/) directory contains detailed reference documentation for each MCP tool:

#### Journal Operations
- [journal_append(3)](api/journal_append.md) - Append entries to the journal
- [journal_amend(3)](api/journal_amend.md) - Add amendments to existing entries
- [journal_read(3)](api/journal_read.md) - Read journal entries
- [journal_search(3)](api/journal_search.md) - Search journal entries (legacy)
- [journal_query(3)](api/journal_query.md) - Query entries with filters and pagination
- [journal_stats(3)](api/journal_stats.md) - Aggregate statistics
- [journal_active(3)](api/journal_active.md) - Find active/long-running operations
- [journal_help(3)](api/journal_help.md) - Get documentation and help

#### Configuration Management
- [config_archive(3)](api/config_archive.md) - Archive configuration files
- [config_activate(3)](api/config_activate.md) - Activate archived configurations
- [config_diff(3)](api/config_diff.md) - Compare configuration versions

#### Log Management
- [log_preserve(3)](api/log_preserve.md) - Preserve log files

#### State Management
- [state_snapshot(3)](api/state_snapshot.md) - Capture complete system state
- [timeline(3)](api/timeline.md) - Unified chronological view
- [trace_causality(3)](api/trace_causality.md) - Trace cause-effect relationships

#### Session Management
- [session_handoff(3)](api/session_handoff.md) - Generate session handoff summaries

#### Maintenance
- [index_rebuild(3)](api/index_rebuild.md) - Rebuild INDEX.md files
- [rebuild_sqlite_index(3)](api/rebuild_sqlite_index.md) - Rebuild SQLite search index

#### Templates
- [list_templates(3)](api/list_templates.md) - List available templates
- [get_template(3)](api/get_template.md) - Get template details

### Internal Documentation

| Document | Description |
|----------|-------------|
| [Future Features](Future-Features.md) | Planned features and roadmap |
| [Query and Search Design](Query-and-Search-with-SQLite.md) | Design document for SQLite-based query system |
| [MCP Flexible Help](MCP-Flexible-Help.md) | Design document for the help system |
| [Test Analysis](Test-Analysis.md) | Test coverage analysis and testing strategy |
| [Comprehensive Testing](comprehensive-testing.md) | Testing methodology and standards |

## Quick Links

- **Getting Started**: See [User Guide - Quick Start](user-guide.md#quick-start)
- **Configuration**: See [Configuration Reference](configuration.md)
- **CLI Commands**: See [CLI Reference](cli-reference.md)
- **API for AI Agents**: See [API Reference](api/README.md)
- **Contributing**: See [Developer Guide](developer-guide.md)

## For AI Agents

If you are an AI agent using the MCP Journal Server:

1. **Tool Discovery**: Use `list_tools` to discover available tools
2. **Tool Help**: Use `journal_help` tool for runtime documentation
3. **API Details**: The [api/](api/) directory contains detailed documentation for each tool
4. **Best Practices**: See [User Guide - AI Integration](user-guide.md#ai-integration)

### Recommended Workflow

```
1. journal_help(topic="workflow")     # Understand the workflow
2. journal_help(tool="journal_append") # Learn specific tool
3. state_snapshot(name="session-start") # Capture initial state
4. journal_append(...)                 # Record your work
5. session_handoff(...)                # Generate handoff summary
```

## Document Conventions

### Version Compatibility

Documentation is versioned alongside the software. Each document header includes:
- **Version**: The software version this documentation applies to
- **Last Updated**: When the document was last modified

### Code Examples

Code examples use the following conventions:

```python
# Python code for programmatic usage
from mcp_journal.engine import JournalEngine

engine = JournalEngine(config)
entry = engine.journal_append(author="example", context="Example entry")
```

```bash
# Shell commands for CLI usage
$ mcp-journal query --tool bash --outcome failure
```

```json
// JSON for MCP tool parameters
{
  "author": "claude",
  "context": "Example entry",
  "outcome": "success"
}
```

### Parameter Tables

API documentation uses standardized parameter tables:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | The parameter name |
| `value` | int | No | 10 | Optional with default |

## Feedback and Corrections

If you find errors or have suggestions for improving this documentation:

1. **GitHub Issues**: Open an issue at [github.com/phdyex/mcp-journal/issues](https://github.com/phdyex/mcp-journal/issues)
2. **Pull Requests**: Submit documentation fixes via PR
3. **Discussion**: Use GitHub Discussions for questions

## License

This documentation is part of MCP Journal and is licensed under the MIT License.
