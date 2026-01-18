# journal_query(3) - Query Journal Entries

## NAME

**journal_query** - Query journal entries with filters, pagination, and sorting

## SYNOPSIS

```
journal_query(
    filters: dict = None,
    text_search: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "timestamp",
    order_desc: bool = True
) -> dict
```

## DESCRIPTION

The **journal_query** tool provides structured queries against the SQLite index. It supports filtering by multiple fields, date ranges, full-text search, pagination, and sorting.

This is the primary tool for finding entries based on criteria. It uses the SQLite index for efficient queries rather than parsing markdown files directly.

## PARAMETERS

### Filter Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filters` | dict | None | Key-value filters (see Filter Fields below) |
| `text_search` | string | None | Full-text search query |
| `date_from` | string | None | Start date (YYYY-MM-DD or "today", "yesterday") |
| `date_to` | string | None | End date (YYYY-MM-DD) |

### Pagination Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Maximum entries to return (1-1000) |
| `offset` | integer | 0 | Number of entries to skip |

### Sorting Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `order_by` | string | "timestamp" | Field to sort by |
| `order_desc` | bool | True | Sort descending (newest first) |

### Filter Fields

The `filters` parameter accepts these fields:

| Field | Type | Description |
|-------|------|-------------|
| `author` | string | Filter by author |
| `outcome` | string | Filter by outcome (success/failure/partial) |
| `entry_type` | string | Filter by type (entry/amendment) |
| `template` | string | Filter by template name |
| `tool` | string | Filter by tool name |
| `error_type` | string | Filter by error type |

### Order By Fields

| Field | Description |
|-------|-------------|
| `timestamp` | Entry creation time (default) |
| `entry_id` | Entry identifier |
| `author` | Author name |
| `outcome` | Outcome value |
| `duration_ms` | Operation duration |

## RETURN VALUE

```json
{
  "count": 25,
  "total": 150,
  "limit": 25,
  "offset": 0,
  "has_more": true,
  "entries": [
    {
      "entry_id": "2026-01-17-005",
      "timestamp": "2026-01-17T16:30:00+00:00",
      "author": "claude",
      "entry_type": "entry",
      "outcome": "failure",
      "context": "Build failed with linking errors",
      "tool": "bash",
      "duration_ms": 120000
    },
    ...
  ]
}
```

### Response Fields

| Field | Description |
|-------|-------------|
| `count` | Number of entries in this response |
| `total` | Total matching entries (for pagination) |
| `limit` | Limit used for this query |
| `offset` | Offset used for this query |
| `has_more` | Whether more entries exist |
| `entries` | Array of matching entries |

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Invalid filter field |
| `ValueError` | Invalid date format |
| `ValueError` | Invalid order_by field |
| `ValueError` | limit < 1 or > 1000 |
| `ValueError` | offset < 0 |

## EXAMPLES

### Query by Author

```json
{
  "filters": {"author": "claude"},
  "limit": 20
}
```

### Query Failed Operations

```json
{
  "filters": {"outcome": "failure"},
  "date_from": "today"
}
```

### Query by Tool

```json
{
  "filters": {"tool": "bash"},
  "order_by": "duration_ms",
  "order_desc": true
}
```

### Combined Filters

```json
{
  "filters": {
    "author": "claude",
    "outcome": "failure",
    "tool": "bash"
  },
  "date_from": "2026-01-15",
  "date_to": "2026-01-17"
}
```

### Full-Text Search with Filters

```json
{
  "text_search": "config error",
  "filters": {"author": "claude"},
  "limit": 50
}
```

### Pagination

```json
{
  "filters": {"author": "claude"},
  "limit": 25,
  "offset": 50
}
```

### Sort by Duration (Slowest First)

```json
{
  "filters": {"tool": "bash"},
  "order_by": "duration_ms",
  "order_desc": true,
  "limit": 10
}
```

### Query Amendments Only

```json
{
  "filters": {"entry_type": "amendment"}
}
```

## NOTES

### Filter Semantics

- Multiple filters are combined with AND
- String filters use exact match
- Null/missing fields don't match filters

### Full-Text Search

The `text_search` parameter searches across:
- context
- intent
- action
- observation
- analysis

It uses SQLite FTS5 for efficient full-text search with:
- Word stemming
- Phrase search with quotes: `"exact phrase"`
- Boolean operators: `error AND config`

### Date Shortcuts

| Value | Meaning |
|-------|---------|
| `"today"` | Current date |
| `"yesterday"` | Previous date |
| `"2026-01-17"` | Specific date |

### Performance

- Index queries are O(log n) for filtered lookups
- Full-text search is O(n log n) using FTS5
- Pagination is efficient (uses OFFSET/LIMIT)
- Large offsets may be slower (consider cursor-based pagination for very large result sets)

### Query vs Read

| Need | Tool |
|------|------|
| Specific entry by ID | `journal_read` |
| Filter by any field | `journal_query` |
| Paginated results | `journal_query` |
| Full-text search | `journal_query` |
| All entries for a date | `journal_read` |

## SEE ALSO

- [journal_search(3)](journal_search.md) - Legacy search
- [journal_read(3)](journal_read.md) - Read by ID/date
- [journal_stats(3)](journal_stats.md) - Aggregated statistics
- [journal_active(3)](journal_active.md) - Find long-running operations
