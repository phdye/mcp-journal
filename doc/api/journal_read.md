# journal_read(3) - Read Journal Entries

## NAME

**journal_read** - Read journal entries by ID or date range

## SYNOPSIS

```
journal_read(
    entry_id: str = None,
    date: str = None,
    date_from: str = None,
    date_to: str = None,
    include_content: bool = True
) -> dict
```

## DESCRIPTION

The **journal_read** tool retrieves journal entries from markdown files. It can read a specific entry by ID, all entries for a date, or entries within a date range.

This tool reads directly from the markdown source files, providing the authoritative content. For filtered queries with pagination, use **journal_query**(3) instead.

## PARAMETERS

### Selection Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_id` | string | None | Specific entry ID (e.g., "2026-01-17-001") |
| `date` | string | None | All entries for date (YYYY-MM-DD) |
| `date_from` | string | None | Range start date (YYYY-MM-DD) |
| `date_to` | string | None | Range end date (YYYY-MM-DD) |

### Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_content` | bool | True | Include full entry content |

At least one selection parameter must be provided.

## RETURN VALUE

### Single Entry (entry_id specified)

```json
{
  "entry_id": "2026-01-17-001",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "author": "claude",
  "entry_type": "entry",
  "context": "Starting code review",
  "intent": "Review error handling in engine.py",
  "outcome": null,
  "file_path": "journal/2026-01-17.md"
}
```

### Multiple Entries (date or range specified)

```json
{
  "count": 5,
  "date_from": "2026-01-17",
  "date_to": "2026-01-17",
  "entries": [
    {
      "entry_id": "2026-01-17-001",
      "timestamp": "2026-01-17T14:30:00+00:00",
      "author": "claude",
      ...
    },
    {
      "entry_id": "2026-01-17-002",
      ...
    }
  ]
}
```

### Without Content (include_content=false)

```json
{
  "count": 5,
  "entries": [
    {
      "entry_id": "2026-01-17-001",
      "timestamp": "2026-01-17T14:30:00+00:00",
      "author": "claude",
      "entry_type": "entry"
    }
  ]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | No selection parameter provided |
| `ValueError` | Invalid date format |
| `ValueError` | date_from is after date_to |
| `EntryNotFoundError` | Specified entry_id not found |
| `FileNotFoundError` | Journal file for date not found |

## EXAMPLES

### Read Specific Entry

```json
{
  "entry_id": "2026-01-17-001"
}
```

### Read All Entries for Today

```json
{
  "date": "2026-01-17"
}
```

### Read Date Range

```json
{
  "date_from": "2026-01-15",
  "date_to": "2026-01-17"
}
```

### Read Entry IDs Only

```json
{
  "date": "2026-01-17",
  "include_content": false
}
```

## NOTES

### Date Formats

The `date`, `date_from`, and `date_to` parameters accept:
- ISO format: `"2026-01-17"`
- Special values: `"today"`, `"yesterday"`

### Entry ID Format

Entry IDs follow the pattern `YYYY-MM-DD-NNN`:
- `2026-01-17-001` - First entry on January 17, 2026
- `2026-01-17-042` - 42nd entry on January 17, 2026

### Read vs Query

| Need | Tool |
|------|------|
| Specific entry by ID | `journal_read` |
| All entries for a date | `journal_read` |
| Filter by author, outcome, tool | `journal_query` |
| Full-text search | `journal_search` or `journal_query` |
| Pagination | `journal_query` |

### Performance

- Reading by entry_id is O(n) where n = entries in that day
- Reading by date range reads all files in range
- For large date ranges, use `journal_query` with pagination

## SEE ALSO

- [journal_query(3)](journal_query.md) - Query with filters
- [journal_search(3)](journal_search.md) - Full-text search
- [journal_append(3)](journal_append.md) - Create entries
- [timeline(3)](timeline.md) - Chronological view
