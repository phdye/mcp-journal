# journal_active(3) - Find Active Operations

## NAME

**journal_active** - Find active or long-running operations

## SYNOPSIS

```
journal_active(
    threshold_ms: int = 30000,
    tool_filter: str = None
) -> list[dict]
```

## DESCRIPTION

The **journal_active** tool identifies operations that have been running for longer than a specified threshold. This is particularly useful for detecting:

- Hung processes
- Long-running builds
- Operations that may need intervention
- Performance bottlenecks

It works by finding entries that have a `duration_ms` field exceeding the threshold, or entries that started but have no corresponding completion entry.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold_ms` | integer | 30000 | Minimum duration in milliseconds |
| `tool_filter` | string | None | Filter to specific tool |

## RETURN VALUE

```json
{
  "threshold_ms": 30000,
  "count": 3,
  "entries": [
    {
      "entry_id": "2026-01-17-005",
      "timestamp": "2026-01-17T14:30:00+00:00",
      "author": "claude",
      "tool": "bash",
      "command": "make build",
      "duration_ms": 180000,
      "context": "Building release version",
      "outcome": "success"
    },
    {
      "entry_id": "2026-01-17-008",
      "timestamp": "2026-01-17T15:00:00+00:00",
      "author": "claude",
      "tool": "bash",
      "command": "pytest tests/",
      "duration_ms": 45000,
      "context": "Running test suite",
      "outcome": "success"
    }
  ]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | threshold_ms < 0 |

## EXAMPLES

### Find All Long Operations

```json
{}
```

Uses default threshold of 30 seconds.

### Find Very Long Operations

```json
{
  "threshold_ms": 300000
}
```

Find operations over 5 minutes.

### Find Long Bash Commands

```json
{
  "threshold_ms": 60000,
  "tool_filter": "bash"
}
```

### Find Operations Over 1 Second

```json
{
  "threshold_ms": 1000
}
```

Useful for finding slow operations.

## NOTES

### Threshold Formats

The CLI accepts human-readable durations:
- `30s` - 30 seconds (30000 ms)
- `5m` - 5 minutes (300000 ms)
- `1h` - 1 hour (3600000 ms)

The API always uses milliseconds.

### Use Cases

**Detecting Hangs**:
Monitor for operations that exceed expected duration.

**Performance Analysis**:
Find the slowest operations to optimize.

**Build Monitoring**:
Track long-running build processes.

**Resource Management**:
Identify operations that may be consuming resources.

### Integration with mcp-cygwin

When using mcp-cygwin for shell operations, record diagnostic entries:

```json
{
  "template": "diagnostic",
  "tool": "bash",
  "command": "make -j12",
  "duration_ms": 180000,
  "exit_code": 0,
  "outcome": "success"
}
```

Then use journal_active to monitor:

```json
{
  "tool_filter": "bash",
  "threshold_ms": 60000
}
```

### Incomplete Operations

Operations recorded with intent but no outcome may indicate:
- Still running
- Crashed without recording completion
- Forgotten to record outcome

These can be found by querying for null outcomes:
```json
{
  "filters": {"outcome": null},
  "date_from": "today"
}
```

## SEE ALSO

- [journal_query(3)](journal_query.md) - Query entries
- [journal_stats(3)](journal_stats.md) - Aggregated statistics
- [journal_append(3)](journal_append.md) - Create entries with duration
