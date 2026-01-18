# journal_help(3) - Get Documentation and Help

## NAME

**journal_help** - Get documentation about the journal system, tools, and workflows

## SYNOPSIS

```
journal_help(
    topic: str = None,
    tool: str = None,
    detail: str = "full"
) -> str
```

## DESCRIPTION

The **journal_help** tool provides runtime documentation for AI agents and users. It returns information about the journal system, available tools, workflows, and best practices.

This tool is the primary discovery mechanism for AI agents to understand how to use the journal system effectively.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `topic` | string | None | Documentation topic |
| `tool` | string | None | Specific tool name |
| `detail` | string | "full" | Level of detail |

### Topics

| Topic | Description |
|-------|-------------|
| `overview` | General system overview (default) |
| `principles` | Core design principles |
| `workflow` | Recommended workflows |
| `tools` | List of all tools |
| `causality` | Causality tracking explanation |
| `templates` | Template system documentation |
| `errors` | Error handling and troubleshooting |

### Detail Levels

| Level | Description |
|-------|-------------|
| `brief` | Short summary |
| `full` | Complete documentation (default) |
| `examples` | Focus on examples |

## RETURN VALUE

Returns markdown-formatted documentation string.

### Overview Response

```markdown
# MCP Journal System

The MCP Journal Server enforces scientific lab journal discipline...

## Core Principles
- Append-only: Never edit or delete
- Timestamped: All entries have precise timestamps
- Attributed: All entries have authors
- Complete: All relevant context is recorded
- Reproducible: State can be reconstructed

## Quick Start
1. Use journal_append to record observations
2. Use journal_amend to correct entries
3. Use config_archive before changing configs
4. Use state_snapshot before major changes

## Available Tools
- journal_append, journal_amend, journal_read...
```

### Tool Response

```markdown
# journal_append

Append a new entry to the journal.

## Parameters
- author (required): Who is making this entry
- context: Current state, what we're trying to accomplish
...

## Example
{
  "author": "claude",
  "context": "Starting build process"
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Unknown topic |
| `ValueError` | Unknown tool name |
| `ValueError` | Invalid detail level |

## EXAMPLES

### Get Overview

```json
{}
```

or

```json
{
  "topic": "overview"
}
```

### Get Tool Documentation

```json
{
  "tool": "journal_append"
}
```

### Get Brief Tool List

```json
{
  "topic": "tools",
  "detail": "brief"
}
```

### Get Workflow Examples

```json
{
  "topic": "workflow",
  "detail": "examples"
}
```

### Get Principles

```json
{
  "topic": "principles"
}
```

### Get Error Help

```json
{
  "topic": "errors"
}
```

## NOTES

### For AI Agents

Recommended discovery pattern:

1. **Initial Discovery**:
   ```json
   {"topic": "overview"}
   ```

2. **Learn Available Tools**:
   ```json
   {"topic": "tools"}
   ```

3. **Understand Workflow**:
   ```json
   {"topic": "workflow", "detail": "examples"}
   ```

4. **Get Specific Tool Help**:
   ```json
   {"tool": "journal_query"}
   ```

### Documentation Sources

The help system draws from:
- Built-in documentation strings
- `doc/api/*.md` files (if available)
- Template definitions
- Configuration-defined help

### Extending Help

Custom help can be added via Python configuration:

```python
# journal_config.py
CUSTOM_HELP = {
    "my-workflow": "Documentation for my custom workflow..."
}
```

### Relationship to doc/ Directory

This tool provides runtime access to documentation. For complete reference documentation, see the `doc/api/` directory which contains man(3) style pages for each tool.

## SEE ALSO

- [API Reference](README.md) - Complete API documentation
- [User Guide](../user-guide.md) - User documentation
- [list_templates(3)](list_templates.md) - List templates
- [get_template(3)](get_template.md) - Get template details
