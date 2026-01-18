# timeline(3) - Unified Chronological View

## NAME

**timeline** - Get unified chronological view of all events

## SYNOPSIS

```
timeline(
    date_from: str = None,
    date_to: str = None,
    event_types: list[str] = None,
    limit: int = 100
) -> dict
```

## DESCRIPTION

The **timeline** tool provides a unified chronological view of all recorded events: journal entries, amendments, config archives, log preservations, and state snapshots. This gives a complete picture of project activity.

Unlike `journal_query` which only returns journal entries, `timeline` integrates all event types into a single timeline.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date_from` | string | None | Start date (YYYY-MM-DD) |
| `date_to` | string | None | End date (YYYY-MM-DD) |
| `event_types` | list[str] | None | Filter to specific event types |
| `limit` | integer | 100 | Maximum events to return |

### Event Types

| Type | Description |
|------|-------------|
| `entry` | Regular journal entries |
| `amendment` | Journal amendments |
| `config` | Configuration archives |
| `log` | Preserved logs |
| `snapshot` | State snapshots |

## RETURN VALUE

```json
{
  "count": 15,
  "date_from": "2026-01-17",
  "date_to": "2026-01-17",
  "events": [
    {
      "type": "entry",
      "timestamp": "2026-01-17T16:30:00+00:00",
      "entry_id": "2026-01-17-010",
      "author": "claude",
      "summary": "Build completed successfully"
    },
    {
      "type": "log",
      "timestamp": "2026-01-17T16:25:00+00:00",
      "path": "logs/build/2026-01-17T16-25-00_success.log",
      "category": "build",
      "outcome": "success"
    },
    {
      "type": "config",
      "timestamp": "2026-01-17T14:30:00+00:00",
      "path": "configs/bootstrap.toml/2026-01-17T14-30-00_pre-build.toml",
      "reason": "pre-build"
    },
    {
      "type": "snapshot",
      "timestamp": "2026-01-17T14:00:00+00:00",
      "path": "snapshots/2026-01-17T14-00-00_session-start.json",
      "name": "session-start"
    }
  ]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Invalid date format |
| `ValueError` | Invalid event_type |
| `ValueError` | date_from after date_to |

## EXAMPLES

### Today's Timeline

```json
{
  "date_from": "today"
}
```

### Full Timeline for Date Range

```json
{
  "date_from": "2026-01-15",
  "date_to": "2026-01-17"
}
```

### Journal Entries Only

```json
{
  "event_types": ["entry", "amendment"],
  "date_from": "today"
}
```

### Config and Snapshot History

```json
{
  "event_types": ["config", "snapshot"],
  "limit": 50
}
```

### All Logs

```json
{
  "event_types": ["log"]
}
```

## NOTES

### Event Ordering

Events are returned in reverse chronological order (newest first) by default. All event types are interleaved based on their timestamp.

### Event Summary

Each event type has different summary information:

**Entry**:
```json
{
  "type": "entry",
  "entry_id": "2026-01-17-010",
  "author": "claude",
  "outcome": "success",
  "summary": "Build completed"
}
```

**Amendment**:
```json
{
  "type": "amendment",
  "entry_id": "2026-01-17-011",
  "author": "claude",
  "references_entry": "2026-01-17-010",
  "summary": "Corrected build time"
}
```

**Config**:
```json
{
  "type": "config",
  "path": "configs/bootstrap.toml/...",
  "reason": "pre-build",
  "journal_entry": "2026-01-17-005"
}
```

**Log**:
```json
{
  "type": "log",
  "path": "logs/build/...",
  "category": "build",
  "outcome": "failure"
}
```

**Snapshot**:
```json
{
  "type": "snapshot",
  "path": "snapshots/...",
  "name": "pre-build",
  "components": ["configs", "env", "versions"]
}
```

### Use Cases

**Daily Review**:
```json
{"date_from": "today"}
```

**Session Reconstruction**:
```json
{
  "date_from": "2026-01-17T14:00:00",
  "date_to": "2026-01-17T18:00:00"
}
```

**Failure Analysis**:
```json
{
  "event_types": ["entry", "log"],
  "date_from": "2026-01-17"
}
```

**Config History**:
```json
{
  "event_types": ["config"],
  "date_from": "2026-01-01"
}
```

### Relationship to Other Tools

| Need | Tool |
|------|------|
| Query journal entries with filters | `journal_query` |
| Full-text search entries | `journal_search` |
| All event types chronologically | `timeline` |
| Trace causality between entries | `trace_causality` |

## SEE ALSO

- [journal_query(3)](journal_query.md) - Query journal entries
- [trace_causality(3)](trace_causality.md) - Trace relationships
- [session_handoff(3)](session_handoff.md) - Generate handoff
- [state_snapshot(3)](state_snapshot.md) - Capture state
