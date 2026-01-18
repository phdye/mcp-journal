# CLI Reference

**Version**: 0.2.0
**Last Updated**: 2026-01-17

## Table of Contents

1. [Synopsis](#synopsis)
2. [Description](#description)
3. [Global Options](#global-options)
4. [Commands](#commands)
5. [Exit Codes](#exit-codes)
6. [Examples](#examples)
7. [Environment Variables](#environment-variables)

---

## Synopsis

```
mcp-journal [OPTIONS] [COMMAND] [COMMAND_OPTIONS]
```

---

## Description

`mcp-journal` is the command-line interface for the MCP Journal Server. It can operate in two modes:

1. **Server Mode** (default): Run as an MCP server for AI agent integration
2. **Command Mode**: Execute specific commands for querying, searching, and maintenance

---

## Global Options

### `--project-root PATH`

Specify the project root directory.

| Attribute | Value |
|-----------|-------|
| Type | Path |
| Required | No |
| Default | Current directory |

```bash
mcp-journal --project-root /path/to/project
```

### `--config PATH`

Specify an explicit configuration file.

| Attribute | Value |
|-----------|-------|
| Type | Path |
| Required | No |
| Default | Auto-discovered |

```bash
mcp-journal --config /path/to/journal_config.toml
```

### `--init`

Initialize journal directories in the project root.

| Attribute | Value |
|-----------|-------|
| Type | Flag |
| Required | No |

```bash
mcp-journal --init --project-root /path/to/project
```

Creates:
- `journal/` - Journal entries
- `configs/` - Configuration archives
- `logs/` - Preserved logs
- `snapshots/` - State snapshots

### `--version`

Show version information and exit.

```bash
mcp-journal --version
```

### `--help`

Show help message and exit.

```bash
mcp-journal --help
```

---

## Commands

### query

Query journal entries with filters.

#### Synopsis

```
mcp-journal query [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--author TEXT` | string | Filter by author |
| `--outcome TEXT` | string | Filter by outcome (success/failure/partial) |
| `--tool TEXT` | string | Filter by tool name |
| `--template TEXT` | string | Filter by template |
| `--since DATE` | date | Entries since date (YYYY-MM-DD or 'today', 'yesterday') |
| `--until DATE` | date | Entries until date |
| `--limit N` | integer | Maximum entries to return (default: 100) |
| `--offset N` | integer | Skip first N entries |
| `--order-by FIELD` | string | Sort by field (timestamp, author, outcome) |
| `--desc` | flag | Sort descending (default: true) |
| `--asc` | flag | Sort ascending |
| `--format FORMAT` | string | Output format (text, json) |

#### Examples

```bash
# Query failed bash operations today
mcp-journal query --tool bash --outcome failure --since today

# Query entries by author
mcp-journal query --author claude --limit 20

# Query with date range, JSON output
mcp-journal query --since 2026-01-15 --until 2026-01-17 --format json

# Query with pagination
mcp-journal query --limit 10 --offset 20 --order-by timestamp --asc
```

#### Output Format (text)

```
Entry: 2026-01-17-001
Timestamp: 2026-01-17T14:30:00Z
Author: claude
Outcome: failure
Context: Build failed due to missing dependency
---
Entry: 2026-01-17-002
Timestamp: 2026-01-17T14:45:00Z
...
```

#### Output Format (json)

```json
{
  "count": 2,
  "entries": [
    {
      "entry_id": "2026-01-17-001",
      "timestamp": "2026-01-17T14:30:00Z",
      "author": "claude",
      "outcome": "failure",
      "context": "Build failed due to missing dependency"
    }
  ]
}
```

---

### search

Full-text search across journal entries.

#### Synopsis

```
mcp-journal search QUERY [OPTIONS]
```

#### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `QUERY` | string | Search query (required) |

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--author TEXT` | string | Filter by author |
| `--since DATE` | date | Entries since date |
| `--until DATE` | date | Entries until date |
| `--limit N` | integer | Maximum entries (default: 50) |
| `--format FORMAT` | string | Output format (text, json) |

#### Examples

```bash
# Search for authentication errors
mcp-journal search "authentication error"

# Search by author and date
mcp-journal search "build failed" --author claude --since today

# Search with JSON output
mcp-journal search "config" --format json
```

---

### stats

Show aggregated statistics.

#### Synopsis

```
mcp-journal stats [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--by FIELD` | string | Group by field (outcome, author, tool, template) |
| `--since DATE` | date | Entries since date |
| `--until DATE` | date | Entries until date |
| `--format FORMAT` | string | Output format (text, json) |

#### Examples

```bash
# Statistics by outcome
mcp-journal stats --by outcome

# Statistics by tool since yesterday
mcp-journal stats --by tool --since yesterday

# Statistics by author, JSON output
mcp-journal stats --by author --format json
```

#### Output Format (text)

```
Statistics grouped by outcome:

outcome     count
---------   -----
success     45
failure     12
partial     8

Total: 65 entries
```

#### Output Format (json)

```json
{
  "group_by": "outcome",
  "groups": [
    {"outcome": "success", "count": 45},
    {"outcome": "failure", "count": 12},
    {"outcome": "partial", "count": 8}
  ],
  "totals": {
    "count": 65
  }
}
```

---

### active

Find active or long-running operations.

#### Synopsis

```
mcp-journal active [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--threshold DURATION` | duration | Minimum duration (default: 30s) |
| `--tool TEXT` | string | Filter by tool name |
| `--format FORMAT` | string | Output format (text, json) |

#### Duration Format

- `30s` - 30 seconds
- `5m` - 5 minutes
- `1h` - 1 hour
- `30000` - 30000 milliseconds

#### Examples

```bash
# Find operations over 60 seconds
mcp-journal active --threshold 60s

# Find long-running bash commands
mcp-journal active --threshold 5m --tool bash

# JSON output
mcp-journal active --threshold 30s --format json
```

#### Output Format (text)

```
Active/Long-running Operations (threshold: 30s)

Entry: 2026-01-17-005
Tool: bash
Duration: 2m 45s
Command: make build
Context: Building release version
---
```

---

### export

Export journal entries.

#### Synopsis

```
mcp-journal export [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--format FORMAT` | string | Output format (json, csv, markdown) |
| `--since DATE` | date | Entries since date |
| `--until DATE` | date | Entries until date |
| `--author TEXT` | string | Filter by author |
| `--output FILE` | path | Output file (default: stdout) |

#### Examples

```bash
# Export to JSON
mcp-journal export --format json --since yesterday > entries.json

# Export to CSV
mcp-journal export --format csv --since 2026-01-01 --output entries.csv

# Export to markdown
mcp-journal export --format markdown --author claude > claude-entries.md
```

#### JSON Format

```json
{
  "exported_at": "2026-01-17T16:00:00Z",
  "count": 25,
  "entries": [
    {
      "entry_id": "2026-01-17-001",
      "timestamp": "2026-01-17T14:30:00Z",
      "author": "claude",
      ...
    }
  ]
}
```

#### CSV Format

```csv
entry_id,timestamp,author,outcome,context
2026-01-17-001,2026-01-17T14:30:00Z,claude,success,"Build completed"
```

#### Markdown Format

```markdown
# Journal Export

Exported: 2026-01-17T16:00:00Z

## 2026-01-17-001

**Timestamp**: 2026-01-17T14:30:00Z
**Author**: claude
**Outcome**: success

### Context
Build completed successfully.

---
```

---

### rebuild-index

Rebuild the SQLite search index.

#### Synopsis

```
mcp-journal rebuild-index [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--verbose` | flag | Show detailed progress |

#### Examples

```bash
# Rebuild index
mcp-journal rebuild-index

# Rebuild with progress
mcp-journal rebuild-index --verbose
```

#### Output

```
Rebuilding SQLite index...
Processing: journal/2026-01-15.md (12 entries)
Processing: journal/2026-01-16.md (8 entries)
Processing: journal/2026-01-17.md (5 entries)

Index rebuilt successfully.
Files processed: 3
Entries indexed: 25
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | File not found |
| 4 | Invalid arguments |
| 5 | MCP not installed (server mode) |

---

## Examples

### Initialize and Run Server

```bash
# Initialize new project
mcp-journal --init --project-root ~/myproject

# Run MCP server
mcp-journal --project-root ~/myproject
```

### Daily Workflow

```bash
# Morning: Check yesterday's failures
mcp-journal query --outcome failure --since yesterday

# Review statistics
mcp-journal stats --by outcome --since today

# Search for specific issues
mcp-journal search "timeout error" --since today

# Export daily report
mcp-journal export --format markdown --since today > daily-report.md
```

### Maintenance

```bash
# Rebuild corrupted index
mcp-journal rebuild-index --verbose

# Export historical data
mcp-journal export --format json --since 2026-01-01 --until 2026-01-31 > january.json
```

### Integration with Scripts

```bash
#!/bin/bash

# Check for failures before deployment
failures=$(mcp-journal query --outcome failure --since today --format json | jq '.count')

if [ "$failures" -gt "0" ]; then
    echo "Cannot deploy: $failures failures today"
    exit 1
fi

echo "No failures, proceeding with deployment"
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MCP_JOURNAL_PROJECT_ROOT` | Default project root |
| `MCP_JOURNAL_CONFIG` | Default config file path |
| `MCP_JOURNAL_DEBUG` | Enable debug logging |
| `NO_COLOR` | Disable colored output |

---

## See Also

- [User Guide](user-guide.md)
- [Configuration Reference](configuration.md)
- [API Reference](api/README.md)
