# trace_causality(3) - Trace Cause-Effect Relationships

## NAME

**trace_causality** - Trace cause-effect relationships between entries

## SYNOPSIS

```
trace_causality(
    entry_id: str,
    direction: str = "both",
    depth: int = 10
) -> dict
```

## DESCRIPTION

The **trace_causality** tool navigates the `caused_by` links between journal entries to reveal the chain of events that led to a particular outcome or that followed from a particular action.

This is essential for:
- Understanding why a failure occurred
- Tracking the impact of a change
- Reconstructing decision paths
- Debugging complex multi-step processes

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_id` | string | - | Starting entry ID |
| `direction` | string | "both" | Trace direction |
| `depth` | integer | 10 | Maximum depth to trace |

### Direction Values

| Value | Description |
|-------|-------------|
| `backward` | Trace causes (what led to this entry) |
| `forward` | Trace effects (what this entry caused) |
| `both` | Trace in both directions |

## RETURN VALUE

```json
{
  "entry_id": "2026-01-17-010",
  "direction": "both",
  "depth": 10,
  "backward": {
    "depth": 3,
    "chain": [
      {
        "entry_id": "2026-01-17-010",
        "author": "claude",
        "summary": "Build failed with linker errors",
        "caused_by": ["2026-01-17-008"]
      },
      {
        "entry_id": "2026-01-17-008",
        "author": "claude",
        "summary": "Changed LLVM link settings",
        "caused_by": ["2026-01-17-005"]
      },
      {
        "entry_id": "2026-01-17-005",
        "author": "claude",
        "summary": "Investigating build performance",
        "caused_by": []
      }
    ]
  },
  "forward": {
    "depth": 2,
    "chain": [
      {
        "entry_id": "2026-01-17-010",
        "author": "claude",
        "summary": "Build failed with linker errors"
      },
      {
        "entry_id": "2026-01-17-012",
        "author": "claude",
        "summary": "Rolled back LLVM settings",
        "caused_by": ["2026-01-17-010"]
      },
      {
        "entry_id": "2026-01-17-015",
        "author": "claude",
        "summary": "Build succeeded after rollback",
        "caused_by": ["2026-01-17-012"]
      }
    ]
  }
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `EntryNotFoundError` | entry_id does not exist |
| `ValueError` | Invalid direction value |
| `ValueError` | depth < 1 |

## EXAMPLES

### Trace Full Chain

```json
{
  "entry_id": "2026-01-17-010"
}
```

### Trace Only Causes

```json
{
  "entry_id": "2026-01-17-010",
  "direction": "backward"
}
```

### Trace Only Effects

```json
{
  "entry_id": "2026-01-17-005",
  "direction": "forward"
}
```

### Limit Depth

```json
{
  "entry_id": "2026-01-17-010",
  "direction": "both",
  "depth": 3
}
```

## NOTES

### Building Causality Chains

When creating entries, link them with `caused_by`:

```json
{
  "author": "claude",
  "context": "Build failed, investigating",
  "caused_by": ["2026-01-17-005"],
  "outcome": "failure"
}
```

This creates a traceable chain:
```
2026-01-17-005 (change config)
       ↓ caused
2026-01-17-008 (rebuild)
       ↓ caused
2026-01-17-010 (failure)
       ↓ caused
2026-01-17-012 (rollback)
```

### Amendments in Causality

Amendments automatically link to their referenced entry:

```json
{
  "references_entry": "2026-01-17-005",
  "correction": "...",
  "actual": "...",
  "impact": "...",
  "author": "claude"
}
```

The amendment appears in the forward chain from the referenced entry.

### Use Cases

**Root Cause Analysis**:
```json
{
  "entry_id": "2026-01-17-020",
  "direction": "backward",
  "depth": 20
}
```
Find what led to a failure.

**Impact Analysis**:
```json
{
  "entry_id": "2026-01-17-005",
  "direction": "forward"
}
```
See all effects of a change.

**Decision Reconstruction**:
```json
{
  "entry_id": "2026-01-17-015",
  "direction": "both"
}
```
Understand the full context of a decision.

### Visualization

The chain can be visualized as a tree:

```
Backward (causes):
└── 2026-01-17-010: Build failed
    └── 2026-01-17-008: Changed settings
        └── 2026-01-17-005: Investigating performance

Forward (effects):
└── 2026-01-17-010: Build failed
    └── 2026-01-17-012: Rolled back
        └── 2026-01-17-015: Build succeeded
```

### Best Practices

1. **Always link related entries** with `caused_by`
2. **Be specific** about causality (not just "related to")
3. **Include multiple causes** when applicable
4. **Use amendments** for corrections, not new caused_by links

### Circular References

The tool handles circular references gracefully by tracking visited entries and stopping when a cycle is detected.

## SEE ALSO

- [journal_append(3)](journal_append.md) - Create entries with caused_by
- [journal_amend(3)](journal_amend.md) - Create amendments
- [journal_query(3)](journal_query.md) - Query entries
- [timeline(3)](timeline.md) - Chronological view
