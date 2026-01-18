# Plan: Query and Search Feature with SQLite Index

## Overview

Add sophisticated query capabilities to mcp-journal using SQLite as an index. Markdown files remain the source of truth; SQLite provides fast structured queries and aggregations.

**Key Decisions:**
- **Storage**: SQLite (stdlib `sqlite3`, zero dependencies)
- **Source of truth**: Markdown files (unchanged)
- **Index location**: `journal/.index.db`
- **Query interface**: Structured dict parameters (no custom parser needed)
- **CLI**: Flag-based with argparse

## Architecture

```
Markdown Files (source of truth)
       ↓ (extract on append)
SQLite Index (.index.db)
       ↓ (query)
Results
```

### Index Schema

```sql
CREATE TABLE entries (
    entry_id TEXT PRIMARY KEY,      -- 2026-01-17-001
    timestamp TEXT NOT NULL,        -- ISO 8601
    date TEXT NOT NULL,             -- YYYY-MM-DD (for fast date filtering)
    author TEXT NOT NULL,
    entry_type TEXT NOT NULL,       -- entry, amendment
    outcome TEXT,                   -- success, failure, partial
    template TEXT,

    -- Content fields (for full-text search)
    context TEXT,
    intent TEXT,
    action TEXT,
    observation TEXT,
    analysis TEXT,
    next_steps TEXT,

    -- Causality
    config_used TEXT,
    log_produced TEXT,
    caused_by TEXT,                 -- JSON array of entry IDs

    -- Diagnostic fields (for mcp-cygwin integration)
    tool TEXT,                      -- bash, read_file, etc.
    duration_ms INTEGER,
    exit_code INTEGER,
    command TEXT,
    error_type TEXT,

    -- Metadata
    file_path TEXT NOT NULL         -- journal/2026-01-17.md
);

CREATE INDEX idx_date ON entries(date);
CREATE INDEX idx_author ON entries(author);
CREATE INDEX idx_outcome ON entries(outcome);
CREATE INDEX idx_tool ON entries(tool);
CREATE INDEX idx_entry_type ON entries(entry_type);

-- Full-text search
CREATE VIRTUAL TABLE entries_fts USING fts5(
    entry_id,
    context,
    intent,
    action,
    observation,
    analysis,
    content='entries',
    content_rowid='rowid'
);
```

## Implementation Steps

### Step 1: Create `src/mcp_journal/index.py`

New module for SQLite index management:

```python
class JournalIndex:
    def __init__(self, journal_path: Path)
    def _init_schema(self)
    def index_entry(self, entry: JournalEntry, file_path: Path)
    def rebuild_from_markdown(self)
    def query(self, filters: dict, limit: int, offset: int, order_by: str) -> list[dict]
    def aggregate(self, group_by: str, aggregations: list[str], filters: dict) -> dict
    def search_text(self, query: str, filters: dict) -> list[dict]
```

### Step 2: Integrate with `engine.py`

Modify `JournalEngine`:
- Add `self.index = JournalIndex(...)` in `__init__`
- Call `self.index.index_entry()` after each `journal_append()` and `journal_amend()`
- Add new methods: `journal_query()`, `journal_stats()`, `journal_active()`

### Step 3: Add MCP Tools in `tools.py`

**New tool: `journal_query`**
```python
@tool
def journal_query(
    filters: dict = None,      # {"tool": "bash", "outcome": "failure"}
    text_search: str = None,   # Full-text search
    date_from: str = None,
    date_to: str = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "timestamp",
    order_desc: bool = True
) -> list[dict]
```

**New tool: `journal_stats`**
```python
@tool
def journal_stats(
    group_by: str = None,           # "tool", "outcome", "author"
    aggregations: list[str] = None, # ["count", "avg:duration_ms", "max:duration_ms"]
    filters: dict = None,
    date_from: str = None,
    date_to: str = None
) -> dict
```

**New tool: `journal_active`** (for diagnostic hang detection)
```python
@tool
def journal_active(
    threshold_ms: int = 30000,
    tool_filter: str = None
) -> list[dict]
```

### Step 4: Add CLI Commands

Extend `server.py` or create `cli.py`:

```bash
# Structured query with flags
mcp-journal query --tool bash --outcome failure --since today

# Text search
mcp-journal search "config error" --author claude

# Statistics
mcp-journal stats --by tool --since today

# Active operations
mcp-journal active --threshold 30s

# Export
mcp-journal export --format json --since yesterday > entries.json
```

### Step 5: Add Diagnostic Template

Add to default templates in `config.py`:

```python
DIAGNOSTIC_TEMPLATE = Template(
    name="diagnostic",
    description="Tool call diagnostic entry",
    required_fields=["tool", "status"],
    optional_fields=["command", "duration_ms", "exit_code", "error_type"],
    # ... field templates
)
```

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `src/mcp_journal/index.py` | **CREATE** | SQLite index management |
| `src/mcp_journal/engine.py` | MODIFY | Integrate index, add query methods |
| `src/mcp_journal/tools.py` | MODIFY | Add journal_query, journal_stats, journal_active |
| `src/mcp_journal/server.py` | MODIFY | Add CLI commands |
| `src/mcp_journal/models.py` | MODIFY | Add diagnostic fields to JournalEntry |
| `src/mcp_journal/config.py` | MODIFY | Add diagnostic template |
| `tests/test_index.py` | **CREATE** | Index tests |
| `tests/test_query.py` | **CREATE** | Query tests |

## Verification

1. **Unit tests**: `pytest tests/test_index.py tests/test_query.py -v`
2. **Integration test**:
   ```bash
   # Create test entries
   mcp-journal --init --project-root /tmp/test-journal
   # Use MCP tools to append entries with different outcomes/tools
   # Query and verify results
   mcp-journal query --tool bash --outcome failure
   mcp-journal stats --by tool
   ```
3. **Index rebuild**: Delete `.index.db`, verify it rebuilds from markdown
4. **FTS search**: Verify full-text search finds entries by content

## Dependencies

None new - uses stdlib `sqlite3`.

## Backwards Compatibility

- Existing `journal_search` unchanged (still works)
- New tools are additions, not replacements
- Index is optional cache; if deleted, rebuilds from markdown
