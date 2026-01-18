# journal_search(3) - Search Journal Entries

## NAME

**journal_search** - Full-text search across journal entries

## SYNOPSIS

```
journal_search(
    query: str,
    author: str = None,
    date_from: str = None,
    date_to: str = None
) -> list[dict]
```

## DESCRIPTION

The **journal_search** tool performs full-text search across journal entries. It searches through the content fields of entries to find matches.

**Note**: This is the legacy search interface. For more powerful queries with pagination and filtering, use **journal_query**(3) with the `text_search` parameter.

## PARAMETERS

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query text |
| `author` | string | No | None | Filter by author |
| `date_from` | string | No | None | Start date (YYYY-MM-DD) |
| `date_to` | string | No | None | End date (YYYY-MM-DD) |

## RETURN VALUE

Returns a list of matching entries:

```json
[
  {
    "entry_id": "2026-01-17-005",
    "timestamp": "2026-01-17T16:30:00+00:00",
    "author": "claude",
    "context": "Build failed with config error",
    "outcome": "failure"
  },
  {
    "entry_id": "2026-01-16-012",
    "timestamp": "2026-01-16T10:15:00+00:00",
    "author": "claude",
    "context": "Investigating config error from yesterday",
    "outcome": "success"
  }
]
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | query is empty |
| `ValueError` | Invalid date format |

## EXAMPLES

### Basic Search

```json
{
  "query": "config error"
}
```

### Search by Author

```json
{
  "query": "build failed",
  "author": "claude"
}
```

### Search with Date Range

```json
{
  "query": "timeout",
  "date_from": "2026-01-15",
  "date_to": "2026-01-17"
}
```

### Search Today's Entries

```json
{
  "query": "test failure",
  "date_from": "today"
}
```

## NOTES

### Search Fields

The search covers these content fields:
- context
- intent
- action
- observation
- analysis
- next_steps

### Search Syntax

Basic search supports:
- Single words: `error`
- Multiple words (OR): `error warning`
- Phrases: `"build failed"`

### Comparison with journal_query

| Feature | journal_search | journal_query |
|---------|----------------|---------------|
| Full-text search | Yes | Yes (text_search param) |
| Filter by outcome | No | Yes |
| Filter by tool | No | Yes |
| Pagination | No | Yes |
| Sorting | No | Yes |
| Result count | No | Yes |

### Migration to journal_query

Replace:
```json
{"query": "config error", "author": "claude"}
```

With:
```json
{
  "text_search": "config error",
  "filters": {"author": "claude"},
  "limit": 100
}
```

## SEE ALSO

- [journal_query(3)](journal_query.md) - Query with filters (recommended)
- [journal_read(3)](journal_read.md) - Read by ID/date
- [journal_stats(3)](journal_stats.md) - Aggregated statistics
