# journal_append(3) - Append Entry to Journal

## NAME

**journal_append** - Append a new timestamped entry to the daily journal

## SYNOPSIS

```
journal_append(
    author: str,
    context: str = None,
    intent: str = None,
    action: str = None,
    observation: str = None,
    analysis: str = None,
    next_steps: str = None,
    outcome: str = None,
    references: list[str] = None,
    caused_by: list[str] = None,
    config_used: str = None,
    log_produced: str = None,
    template: str = None,
    template_values: dict = None,
    tool: str = None,
    command: str = None,
    duration_ms: int = None,
    exit_code: int = None,
    error_type: str = None
) -> dict
```

## DESCRIPTION

The **journal_append** tool creates a new entry in today's journal file. Each entry is assigned a unique ID in the format `YYYY-MM-DD-NNN` where NNN is a sequential number starting from 001.

Entries are **append-only** - once created, they cannot be modified or deleted. To correct an entry, use **journal_amend**(3) to add an amendment that references the original.

The entry is written atomically to `journal/YYYY-MM-DD.md` and indexed in the SQLite database for efficient querying.

## PARAMETERS

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `author` | string | Who is making this entry. Cannot be empty. |

### Content Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `context` | string | None | Current state, what we're trying to accomplish |
| `intent` | string | None | What action we're about to take and why |
| `action` | string | None | Commands executed, files modified |
| `observation` | string | None | What happened, output received |
| `analysis` | string | None | What does this mean, what did we learn |
| `next_steps` | string | None | What should happen next |
| `outcome` | string | None | Result: "success", "failure", or "partial" |

### Link Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `references` | list[str] | None | Cross-references to files or other entries |
| `caused_by` | list[str] | None | Entry IDs that caused/led to this entry |
| `config_used` | string | None | Config archive path used for this operation |
| `log_produced` | string | None | Log path produced by this operation |

### Template Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `template` | string | None | Template name to use for this entry |
| `template_values` | dict | None | Values to fill template placeholders |

### Diagnostic Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool` | string | None | Tool name (e.g., "bash", "read_file") |
| `command` | string | None | Command that was executed |
| `duration_ms` | integer | None | Operation duration in milliseconds |
| `exit_code` | integer | None | Command exit code |
| `error_type` | string | None | Type of error (e.g., "timeout", "permission") |

## RETURN VALUE

Returns a dictionary with the created entry details:

```json
{
  "status": "success",
  "entry_id": "2026-01-17-001",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "file_path": "journal/2026-01-17.md"
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | author is empty or None |
| `ValueError` | template specified but not found |
| `ValueError` | outcome not one of: success, failure, partial |
| `IOError` | Cannot write to journal file |

## EXAMPLES

### Basic Entry

```json
{
  "author": "claude",
  "context": "Starting code review",
  "intent": "Review error handling in engine.py"
}
```

### Entry with Outcome

```json
{
  "author": "claude",
  "context": "Building release version",
  "action": "make build",
  "observation": "Build completed successfully",
  "outcome": "success"
}
```

### Diagnostic Entry

```json
{
  "author": "claude",
  "template": "diagnostic",
  "tool": "bash",
  "command": "pytest tests/",
  "context": "Running test suite",
  "duration_ms": 45000,
  "exit_code": 0,
  "outcome": "success"
}
```

### Entry with Causality

```json
{
  "author": "claude",
  "context": "Fixing test failures identified in previous entry",
  "caused_by": ["2026-01-17-005"],
  "action": "Updated error handling in parse_config()",
  "outcome": "success"
}
```

### Using Template

```json
{
  "author": "claude",
  "template": "build",
  "template_values": {
    "target": "release",
    "jobs": 12
  },
  "outcome": "success"
}
```

## NOTES

### Entry ID Generation

Entry IDs are sequential within each day:
- First entry of 2026-01-17: `2026-01-17-001`
- Second entry: `2026-01-17-002`
- After 999: `2026-01-17-1000` (no limit)

### File Format

Entries are written to markdown files with this structure:

```markdown
## 2026-01-17-001

**Timestamp**: 2026-01-17T14:30:00+00:00
**Author**: claude

### Context
Starting code review

### Intent
Review error handling in engine.py

---
```

### Atomicity

The write operation is atomic - either the entire entry is written or nothing is written. This is achieved through:
1. File locking to prevent concurrent writes
2. Complete entry construction before write
3. Index update after successful file write

### Hooks

If configured, these hooks are called:
- `hook_pre_append(entry_data)` - Before writing (can modify/cancel)
- `hook_post_append(entry)` - After successful write

## SEE ALSO

- [journal_amend(3)](journal_amend.md) - Add amendment to entry
- [journal_read(3)](journal_read.md) - Read entries
- [journal_query(3)](journal_query.md) - Query entries
- [list_templates(3)](list_templates.md) - List available templates
- [trace_causality(3)](trace_causality.md) - Trace entry relationships
