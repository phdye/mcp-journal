# journal_stats(3) - Get Aggregated Statistics

## NAME

**journal_stats** - Get aggregated statistics from journal entries

## SYNOPSIS

```
journal_stats(
    group_by: str = None,
    aggregations: list[str] = None,
    filters: dict = None,
    date_from: str = None,
    date_to: str = None
) -> dict
```

## DESCRIPTION

The **journal_stats** tool computes aggregated statistics from journal entries. It can group entries by various fields and compute counts, averages, and other aggregations.

This is useful for understanding patterns in your work, identifying problem areas, and tracking progress over time.

## PARAMETERS

### Grouping Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_by` | string | None | Field to group by |

### Aggregation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `aggregations` | list[str] | ["count"] | Aggregations to compute |

### Filter Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filters` | dict | None | Key-value filters (same as journal_query) |
| `date_from` | string | None | Start date (YYYY-MM-DD) |
| `date_to` | string | None | End date (YYYY-MM-DD) |

### Group By Fields

| Field | Description |
|-------|-------------|
| `outcome` | Group by outcome (success/failure/partial) |
| `author` | Group by author |
| `tool` | Group by tool name |
| `template` | Group by template name |
| `date` | Group by date |
| `error_type` | Group by error type |

### Aggregation Types

| Aggregation | Description |
|-------------|-------------|
| `count` | Count of entries |
| `avg:field` | Average of numeric field |
| `sum:field` | Sum of numeric field |
| `min:field` | Minimum of numeric field |
| `max:field` | Maximum of numeric field |

Numeric fields for aggregations:
- `duration_ms` - Operation duration
- `exit_code` - Command exit code

## RETURN VALUE

### Without Grouping

```json
{
  "total": 150,
  "aggregations": {
    "count": 150,
    "avg:duration_ms": 45000,
    "max:duration_ms": 300000
  }
}
```

### With Grouping

```json
{
  "group_by": "outcome",
  "total": 150,
  "groups": [
    {
      "outcome": "success",
      "count": 120,
      "avg:duration_ms": 30000
    },
    {
      "outcome": "failure",
      "count": 25,
      "avg:duration_ms": 90000
    },
    {
      "outcome": "partial",
      "count": 5,
      "avg:duration_ms": 60000
    }
  ]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Invalid group_by field |
| `ValueError` | Invalid aggregation format |
| `ValueError` | Invalid date format |

## EXAMPLES

### Overall Statistics

```json
{}
```

Returns total count of all entries.

### Group by Outcome

```json
{
  "group_by": "outcome"
}
```

### Group by Tool with Duration Stats

```json
{
  "group_by": "tool",
  "aggregations": ["count", "avg:duration_ms", "max:duration_ms"]
}
```

### Today's Statistics by Author

```json
{
  "group_by": "author",
  "date_from": "today"
}
```

### Failure Analysis by Tool

```json
{
  "group_by": "tool",
  "filters": {"outcome": "failure"},
  "date_from": "2026-01-15"
}
```

### Daily Entry Counts

```json
{
  "group_by": "date",
  "date_from": "2026-01-01",
  "date_to": "2026-01-17"
}
```

### Error Type Distribution

```json
{
  "group_by": "error_type",
  "filters": {"outcome": "failure"}
}
```

## NOTES

### Use Cases

**Progress Tracking**:
```json
{
  "group_by": "date",
  "aggregations": ["count"],
  "date_from": "2026-01-01"
}
```

**Performance Analysis**:
```json
{
  "group_by": "tool",
  "aggregations": ["count", "avg:duration_ms", "max:duration_ms"],
  "filters": {"outcome": "success"}
}
```

**Failure Investigation**:
```json
{
  "group_by": "error_type",
  "filters": {"outcome": "failure", "tool": "bash"}
}
```

### Null Handling

- Entries with null values for group_by field are grouped as `"(none)"`
- Null values are excluded from numeric aggregations

### Performance

- Statistics are computed via SQL aggregation (efficient)
- Large date ranges may take longer
- Consider adding filters to reduce data scanned

## SEE ALSO

- [journal_query(3)](journal_query.md) - Query entries
- [journal_active(3)](journal_active.md) - Find long-running operations
- [timeline(3)](timeline.md) - Chronological view
