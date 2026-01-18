# API Reference

**Version**: 0.2.0
**Last Updated**: 2026-01-17

This directory contains detailed API documentation for all MCP Journal tools in man(3) page style.

## Tool Index

### Journal Operations

| Tool | Description |
|------|-------------|
| [journal_append(3)](journal_append.md) | Append a new entry to the journal |
| [journal_amend(3)](journal_amend.md) | Add an amendment to a previous entry |
| [journal_read(3)](journal_read.md) | Read journal entries by ID or date range |
| [journal_query(3)](journal_query.md) | Query entries with filters and pagination |
| [journal_search(3)](journal_search.md) | Full-text search across journal entries |
| [journal_stats(3)](journal_stats.md) | Get aggregated statistics |
| [journal_active(3)](journal_active.md) | Find active or long-running operations |
| [journal_help(3)](journal_help.md) | Get documentation and help |

### Configuration Management

| Tool | Description |
|------|-------------|
| [config_archive(3)](config_archive.md) | Archive a configuration file before modification |
| [config_activate(3)](config_activate.md) | Set an archived configuration as active |
| [config_diff(3)](config_diff.md) | Show differences between configuration versions |

### Log Management

| Tool | Description |
|------|-------------|
| [log_preserve(3)](log_preserve.md) | Preserve a log file with timestamp and outcome |

### State Management

| Tool | Description |
|------|-------------|
| [state_snapshot(3)](state_snapshot.md) | Capture complete system state atomically |
| [timeline(3)](timeline.md) | Get unified chronological view of all events |
| [trace_causality(3)](trace_causality.md) | Trace cause-effect relationships between entries |

### Session Management

| Tool | Description |
|------|-------------|
| [session_handoff(3)](session_handoff.md) | Generate session summary for AI context transfer |

### Maintenance

| Tool | Description |
|------|-------------|
| [index_rebuild(3)](index_rebuild.md) | Rebuild INDEX.md files from actual files |

### Templates

| Tool | Description |
|------|-------------|
| [list_templates(3)](list_templates.md) | List available entry templates |
| [get_template(3)](get_template.md) | Get details of a specific template |

---

## Quick Reference

### Most Common Tools

For everyday journaling, these are the most frequently used tools:

```
journal_append   - Record what you're doing
journal_amend    - Correct or add to previous entries
journal_query    - Find entries with filters
journal_search   - Full-text search
state_snapshot   - Capture state before major changes
session_handoff  - End-of-session summary
```

### Diagnostic Workflow

For tool call diagnostics (especially with mcp-cygwin):

```
1. journal_append with template="diagnostic" before tool call
2. Record tool, command, intent
3. journal_append with outcome, duration_ms, exit_code after
4. journal_active to find long-running operations
5. journal_stats --by tool to analyze patterns
```

### Configuration Change Workflow

```
1. config_archive before modifying config
2. Make changes to configuration file
3. journal_append to document why changes were made
4. config_activate if rolling back to previous version
5. config_diff to compare versions
```

---

## Parameter Types

### Common Types

| Type | Format | Example |
|------|--------|---------|
| `string` | Text | `"claude"` |
| `integer` | Whole number | `100` |
| `boolean` | true/false | `true` |
| `date` | YYYY-MM-DD | `"2026-01-17"` |
| `timestamp` | ISO 8601 | `"2026-01-17T14:30:00+00:00"` |
| `entry_id` | YYYY-MM-DD-NNN | `"2026-01-17-001"` |
| `path` | File path | `"/path/to/file"` |

### Outcome Values

| Value | Meaning |
|-------|---------|
| `"success"` | Operation completed successfully |
| `"failure"` | Operation failed |
| `"partial"` | Operation partially completed |

### Entry Types

| Value | Meaning |
|-------|---------|
| `"entry"` | Regular journal entry |
| `"amendment"` | Amendment to existing entry |

---

## Return Value Conventions

### Success Response

```json
{
  "status": "success",
  "entry_id": "2026-01-17-001",
  "message": "Entry created successfully"
}
```

### Query Response

```json
{
  "count": 25,
  "total": 100,
  "limit": 25,
  "offset": 0,
  "entries": [...]
}
```

### Error Response

```json
{
  "status": "error",
  "error": "EntryNotFoundError",
  "message": "Entry 2026-01-17-999 not found"
}
```

---

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `ValueError` | Invalid parameter | Check parameter format |
| `EntryNotFoundError` | Entry ID doesn't exist | Verify entry_id |
| `ConfigurationError` | Invalid config | Check config file |
| `IOError` | File operation failed | Check permissions |

### Validation Errors

Tools validate parameters before execution:

- Required parameters must be provided
- String parameters cannot be empty when required
- Enum parameters must match allowed values
- Date parameters must be valid dates

---

## For AI Agents

### Discovery Pattern

```
1. journal_help()                    # Overview
2. journal_help(topic="tools")       # List all tools
3. journal_help(tool="journal_query") # Specific tool
4. Read doc/api/journal_query.md     # Full reference
```

### Best Practices

1. **Always provide author**: Required for accountability
2. **Use templates**: Ensure consistent entry structure
3. **Link entries**: Use `caused_by` for traceability
4. **Record outcomes**: Always set success/failure/partial
5. **Include context**: Future you will thank present you

### Example Session

```python
# Start of session
snapshot = state_snapshot(name="session-start")

# Document intent
entry = journal_append(
    author="claude",
    context="Starting code review task",
    intent="Review and improve error handling"
)

# Record work
entry = journal_append(
    author="claude",
    context="Reviewing error handling in engine.py",
    action="Read engine.py and identified 5 error paths",
    observation="3 paths have inconsistent error messages",
    template="diagnostic"
)

# End of session
handoff = session_handoff()
```

---

## See Also

- [User Guide](../user-guide.md) - Getting started
- [Configuration](../configuration.md) - Configuration reference
- [CLI Reference](../cli-reference.md) - Command-line usage
- [Architecture](../architecture.md) - System design
