# session_handoff(3) - Generate Session Summary

## NAME

**session_handoff** - Generate session summary for AI context transfer

## SYNOPSIS

```
session_handoff(
    date_from: str = None,
    date_to: str = None,
    include_configs: bool = True,
    include_logs: bool = True,
    format: str = "markdown"
) -> str
```

## DESCRIPTION

The **session_handoff** tool generates a comprehensive summary of work performed during a session. This summary is designed to provide context for:

- Continuing work in a new AI session
- Handing off to a human collaborator
- Creating documentation of what was accomplished
- Reviewing session activity

The summary includes journal entries, configuration changes, preserved logs, and key decisions made during the session.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date_from` | string | today | Start of session |
| `date_to` | string | today | End of session |
| `include_configs` | bool | True | Include config change summary |
| `include_logs` | bool | True | Include log outcome summary |
| `format` | string | "markdown" | Output format |

### Format Values

| Value | Description |
|-------|-------------|
| `markdown` | Markdown formatted summary |
| `json` | JSON structured data |

## RETURN VALUE

### Markdown Format

```markdown
# Session Handoff Summary

**Session**: 2026-01-17T14:00:00 to 2026-01-17T18:00:00
**Duration**: 4 hours
**Author**: claude

## Summary

This session focused on debugging and fixing the stage 2 build failure.
15 journal entries were created, 2 configurations were archived,
and 3 logs were preserved.

## Key Decisions

1. Rolled back LLVM link-shared setting after build failure
2. Increased parallel jobs from 8 to 12
3. Added explicit stdlib linking

## Journal Entries

### 2026-01-17-001 (14:30)
**Context**: Starting stage 2 build investigation
**Outcome**: N/A (investigation start)

### 2026-01-17-005 (15:00)
**Context**: Build failed with linker errors
**Outcome**: failure
**Analysis**: Missing libstdc++ symbols suggest static linking issue

... (more entries) ...

## Configuration Changes

| Config | Archives | Latest Reason |
|--------|----------|---------------|
| bootstrap.toml | 2 | rollback-linker-fix |

## Preserved Logs

| Category | Count | Outcomes |
|----------|-------|----------|
| build | 3 | 1 success, 2 failure |

## Open Items

- [ ] Investigate why static-libstdcpp=true causes issues
- [ ] Test with LLVM 18 when available

## Recommendations for Next Session

1. Start by reviewing 2026-01-17-015 for context
2. Check build logs in logs/build/
3. Consider trying alternative linking approach
```

### JSON Format

```json
{
  "session": {
    "date_from": "2026-01-17T14:00:00+00:00",
    "date_to": "2026-01-17T18:00:00+00:00",
    "duration_hours": 4,
    "author": "claude"
  },
  "summary": {
    "total_entries": 15,
    "config_archives": 2,
    "logs_preserved": 3,
    "outcomes": {
      "success": 8,
      "failure": 5,
      "partial": 2
    }
  },
  "entries": [...],
  "config_changes": [...],
  "logs": [...],
  "key_decisions": [...],
  "open_items": [...]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Invalid date format |
| `ValueError` | Invalid format value |
| `ValueError` | date_from after date_to |

## EXAMPLES

### Today's Session Summary

```json
{}
```

### Specific Date Range

```json
{
  "date_from": "2026-01-17T09:00:00",
  "date_to": "2026-01-17T17:00:00"
}
```

### Journal Only (No Config/Logs)

```json
{
  "include_configs": false,
  "include_logs": false
}
```

### JSON Output

```json
{
  "format": "json"
}
```

### Yesterday's Session

```json
{
  "date_from": "yesterday",
  "date_to": "yesterday"
}
```

## NOTES

### When to Generate Handoff

Generate a handoff summary:
- At the end of each work session
- Before context limits are reached
- When switching between tasks
- Before handing off to another person/AI

### Key Decisions Detection

The tool identifies key decisions by looking for entries with:
- `analysis` field containing decision language
- `outcome` field set (indicating completed actions)
- Config archives with significant reason text
- Multiple entries referencing the same cause

### Open Items Detection

Open items are detected from:
- Entries with `next_steps` field
- Failures without corresponding success entries
- Investigation entries without conclusions

### Recommendations Generation

Recommendations are generated based on:
- Most recent entry context
- Unresolved failures
- Pattern of work (what was being attempted)

### Integration with State Snapshots

For complete context transfer, combine with state snapshot:

```python
# End of session
snapshot = state_snapshot(name="session-end")
handoff = session_handoff()

# Save handoff to file
with open("handoff.md", "w") as f:
    f.write(handoff)
```

### Best Practices

1. **Generate handoffs regularly** - Don't wait until the last moment
2. **Include date range** - Be specific about session boundaries
3. **Use with snapshots** - Capture state at handoff time
4. **Review before sharing** - Ensure sensitive info is appropriate

## SEE ALSO

- [state_snapshot(3)](state_snapshot.md) - Capture system state
- [timeline(3)](timeline.md) - View events chronologically
- [journal_query(3)](journal_query.md) - Query entries
- [journal_read(3)](journal_read.md) - Read specific entries
