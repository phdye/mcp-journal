# Sophisticated Query and Search Tools for MCP Journal

## Problem Statement

MCP Journal currently has basic search capabilities (`journal_search` with text matching and simple filters), but lacks the sophisticated query and search tools needed for effective journal analysis, debugging workflows, and integration with diagnostic systems like mcp-cygwin.

Users need to:
1. Query journal entries with complex filters (AND/OR/NOT)
2. Search by structured metadata fields, not just text
3. Aggregate and analyze patterns across entries
4. Access journal data via CLI for scripting and manual debugging
5. Perform diagnostic-specific queries (tool performance, errors, hangs)

## Current State

### Existing Capabilities

| Tool | Capability | Limitations |
|------|------------|-------------|
| `journal_search` | Text query, date range, author, entry type filters | Text-only matching, no field-specific search, no aggregation |
| `journal_read` | Read by entry ID or date range | No filtering, returns raw entries |
| `timeline` | Chronological view across event types | Limited filtering, no aggregation |
| `trace_causality` | Follow cause-effect links | Only traverses `caused_by` relationships |

### What's Missing

1. **Field-Specific Queries**: Cannot search by outcome, tool name, duration, config used, etc.
2. **Compound Filters**: No AND/OR/NOT logic for combining conditions
3. **Aggregation**: No count, sum, average, min/max, group-by operations
4. **Performance Queries**: No way to find slow operations or duration patterns
5. **Error Analysis**: No dedicated error/failure querying
6. **CLI Access**: No command-line interface - all access via MCP tools only
7. **Output Formats**: No JSON/CSV export for external analysis
8. **Real-time Monitoring**: No watch/tail mode for live entries

## Requirements

### R1: Structured Field Queries

Query entries by any structured field, not just full-text search.

**Required Fields:**
| Field | Type | Examples |
|-------|------|----------|
| `author` | string | `author:claude`, `author:user` |
| `outcome` | enum | `outcome:success`, `outcome:failure`, `outcome:partial` |
| `entry_type` | enum | `type:entry`, `type:amendment` |
| `template` | string | `template:diagnostic`, `template:build` |
| `has_error` | boolean | `has_error:true` |
| `references` | string | `references:config/bootstrap.toml` |
| `caused_by` | entry_id | `caused_by:2026-01-17-003` |

**Diagnostic-Specific Fields (for mcp-cygwin integration):**
| Field | Type | Examples |
|-------|------|----------|
| `tool` | string | `tool:bash`, `tool:read_file`, `tool:find` |
| `duration_ms` | number | `duration_ms:>1000`, `duration_ms:<100` |
| `exit_code` | number | `exit_code:0`, `exit_code:!=0` |
| `error_type` | string | `error_type:timeout`, `error_type:permission` |
| `command` | string | `command:*make*` (glob match) |
| `status` | enum | `status:active`, `status:completed`, `status:failed` |

### R2: Compound Query Logic

Support combining conditions with boolean operators.

**Syntax Examples:**
```
# AND (implicit)
tool:bash outcome:failure

# AND (explicit)
tool:bash AND duration_ms:>5000

# OR
tool:bash OR tool:sh

# NOT
tool:bash NOT outcome:success

# Grouping
(tool:bash OR tool:sh) AND duration_ms:>1000

# Comparison operators
duration_ms:>1000
duration_ms:>=1000
duration_ms:<100
duration_ms:<=100
duration_ms:=500
duration_ms:!=0
```

### R3: Time-Based Queries

Query by absolute and relative time ranges.

**Examples:**
```
# Absolute date range
date:2026-01-17
date:2026-01-15..2026-01-17

# Relative time
time:last-hour
time:last-24h
time:today
time:yesterday
time:this-week

# Time of day
hour:09..17  # Working hours only
```

### R4: Aggregation Queries

Compute statistics across matching entries.

**Required Aggregations:**
| Aggregation | Description | Example Output |
|-------------|-------------|----------------|
| `count` | Number of matching entries | `127` |
| `count_by` | Group and count | `{bash: 45, read_file: 32, find: 28}` |
| `sum` | Sum of numeric field | `duration_ms sum: 45230` |
| `avg` | Average of numeric field | `duration_ms avg: 234.5` |
| `min` / `max` | Extremes | `duration_ms min: 12, max: 126757` |
| `percentile` | P50, P95, P99 | `duration_ms p95: 1250` |
| `histogram` | Distribution buckets | `<100ms: 45, 100-500ms: 32, >500ms: 12` |

**Example Queries:**
```
# Count failures by tool
count_by:tool outcome:failure

# Average duration per tool
avg:duration_ms group_by:tool

# Slowest 10 operations
sort:duration_ms order:desc limit:10

# Error rate by tool
count_by:tool,outcome
```

### R5: Active/In-Progress Query (Diagnostic-Specific)

Query currently running operations for hang detection.

**Requirements:**
- Return operations that started but haven't completed
- Include elapsed time since start
- Support threshold filtering (`elapsed:>30s`)
- Real-time refresh capability

**Example:**
```
status:active elapsed:>30s
```

**Output:**
```
TOOL      STARTED              ELAPSED   ARGS
bash      2026-01-17 16:43:12  45.2s     command='make -j12'
find      2026-01-17 16:44:01  12.1s     path='/home/user', pattern='*.md'
```

### R6: CLI Interface

Provide command-line access to all query capabilities.

**Command Structure:**
```bash
mcp-journal query [OPTIONS] [QUERY...]
mcp-journal search [OPTIONS] [TEXT...]
mcp-journal stats [OPTIONS]
mcp-journal active [OPTIONS]
mcp-journal watch [OPTIONS]
mcp-journal export [OPTIONS]
```

**Core Commands:**

```bash
# Structured query
mcp-journal query "tool:bash outcome:failure time:today"
mcp-journal query --tool bash --outcome failure --since today

# Text search (existing journal_search)
mcp-journal search "error loading config"

# Statistics
mcp-journal stats                          # Overall stats
mcp-journal stats --by tool                # Stats per tool
mcp-journal stats --by tool --since today  # Stats per tool today

# Active operations (diagnostic)
mcp-journal active                         # All active
mcp-journal active --threshold 30s         # Active > 30s

# Real-time monitoring
mcp-journal watch                          # Tail all entries
mcp-journal watch --filter "tool:bash"     # Tail matching entries

# Export
mcp-journal export --format json > entries.json
mcp-journal export --format csv --since yesterday > entries.csv
```

**Output Format Options:**
```bash
--format table    # Human-readable table (default)
--format json     # JSON array
--format jsonl    # JSON Lines (one object per line)
--format csv      # CSV with headers
--format compact  # Single-line summaries
```

**Common Options:**
```bash
--project PATH    # Project root (default: current directory)
--since DATE      # Start date/time
--until DATE      # End date/time
--limit N         # Maximum results
--offset N        # Skip first N results
--sort FIELD      # Sort by field
--order asc|desc  # Sort order
--no-header       # Omit headers (for scripting)
```

### R7: Enhanced MCP Tools

New and enhanced MCP tools for AI access.

**New Tool: `journal_query`**
```json
{
  "tool": "journal_query",
  "arguments": {
    "query": "tool:bash outcome:failure",
    "fields": ["tool", "outcome", "duration_ms"],
    "date_from": "2026-01-17",
    "date_to": "2026-01-17",
    "limit": 20,
    "offset": 0,
    "sort_by": "duration_ms",
    "sort_order": "desc"
  }
}
```

**New Tool: `journal_stats`**
```json
{
  "tool": "journal_stats",
  "arguments": {
    "query": "tool:*",
    "group_by": "tool",
    "aggregations": ["count", "avg:duration_ms", "max:duration_ms"],
    "date_from": "2026-01-17"
  }
}
```

**New Tool: `journal_active` (for diagnostics)**
```json
{
  "tool": "journal_active",
  "arguments": {
    "threshold_ms": 30000,
    "tool_filter": "bash"
  }
}
```

**Enhanced `journal_search`:**
Add structured field filters as optional parameters:
```json
{
  "tool": "journal_search",
  "arguments": {
    "query": "config error",
    "outcome": "failure",
    "tool": "bash",
    "duration_min_ms": 1000,
    "date_from": "2026-01-17"
  }
}
```

### R8: Diagnostic Entry Template

Standard template for diagnostic entries (used by mcp-cygwin and other tools).

**Template: `diagnostic`**
```yaml
name: diagnostic
description: Tool call diagnostic entry
required_fields:
  - tool          # Tool name (bash, read_file, etc.)
  - status        # active, completed, failed
optional_fields:
  - command       # Command or primary argument
  - args_summary  # Truncated argument summary
  - duration_ms   # Execution time in milliseconds
  - exit_code     # Process exit code (if applicable)
  - error_type    # Classification of error
  - error_message # Error details
  - result_summary # Truncated result
  - parent_id     # Parent operation entry ID (causality)
  - session_id    # Session identifier for grouping
```

**Example Diagnostic Entry:**
```markdown
## 2026-01-17-042 [16:43:16]

**Author**: mcp-cygwin
**Template**: diagnostic

### Tool
bash

### Status
completed

### Command
make -j12

### Args Summary
command='make -j12', cwd='/home/user/project'

### Duration (ms)
126757

### Exit Code
0

### Outcome
success

### Caused By
- 2026-01-17-041 (build session start)
```

### R9: Performance Considerations

**Indexing:**
- Index commonly queried fields (tool, outcome, date, duration_ms)
- Consider SQLite or similar for large journals
- Maintain index incrementally on append

**Caching:**
- Cache aggregation results with TTL
- Invalidate on new entries
- Optional: in-memory index for recent entries

**Batching:**
- Support batch append for high-volume diagnostics
- Configurable batch size and flush interval
- Async write to avoid blocking callers

**Thresholds:**
- Configurable minimum duration to log (skip trivial calls)
- Sampling for very high-volume scenarios
- Separate "active" tracking from full logging

### R10: Configuration

**New Configuration Options:**
```toml
[query]
# Default query options
default_limit = 100
max_limit = 1000

[diagnostics]
# Minimum duration to log (ms), 0 = log all
min_duration_ms = 0
# Batch size for diagnostic writes
batch_size = 10
# Flush interval (seconds)
flush_interval = 5
# Track active operations
track_active = true
# Active operation timeout warning (seconds)
active_timeout_warn = 60

[index]
# Enable indexing for faster queries
enabled = true
# Fields to index
fields = ["tool", "outcome", "author", "date"]
```

## Use Cases

### UC1: Debug Hanging Operation

**Scenario**: Claude Code appears stuck, user wants to know what's running.

**CLI:**
```bash
mcp-journal active
```

**MCP:**
```json
{"tool": "journal_active", "arguments": {}}
```

**Output:**
```
TOOL   STARTED              ELAPSED  ARGS
bash   2026-01-17 16:43:12  245.2s   command='make -j12'
```

### UC2: Investigate Slow Performance

**Scenario**: Build seems slower than usual, want to identify bottlenecks.

**CLI:**
```bash
mcp-journal stats --by tool --since today --sort avg_duration
```

**MCP:**
```json
{"tool": "journal_stats", "arguments": {"group_by": "tool", "aggregations": ["count", "avg:duration_ms"], "date_from": "2026-01-17"}}
```

**Output:**
```
TOOL        COUNT  AVG_MS    MAX_MS    TOTAL_MS
bash        45     2340      126757    105300
find        28     450       1200      12600
read_file   156    45        890       7020
```

### UC3: Find All Failures

**Scenario**: Something failed, want to see all recent errors.

**CLI:**
```bash
mcp-journal query "outcome:failure time:last-hour" --format table
```

**MCP:**
```json
{"tool": "journal_query", "arguments": {"query": "outcome:failure", "date_from": "2026-01-17T15:00:00"}}
```

### UC4: Real-Time Monitoring

**Scenario**: Watching a long build, want live updates.

**CLI:**
```bash
mcp-journal watch --filter "tool:bash OR tool:daemon_info"
```

**Output (streaming):**
```
[16:43:16.134] [START] bash command='make -j12'
[16:43:45.891] [CHECK] daemon_info daemon_id='build' → running
[16:44:15.234] [CHECK] daemon_info daemon_id='build' → running
[16:45:22.891] [DONE]  bash 126757ms exit=0
```

### UC5: Export for External Analysis

**Scenario**: Want to analyze patterns in spreadsheet or custom tool.

**CLI:**
```bash
mcp-journal export --format csv --since last-week --filter "tool:bash" > bash_calls.csv
```

### UC6: Causality Analysis

**Scenario**: A failure occurred, want to trace what led to it.

**CLI:**
```bash
mcp-journal query "caused_by:2026-01-17-041" --recursive
```

**MCP:**
```json
{"tool": "trace_causality", "arguments": {"entry_id": "2026-01-17-041", "direction": "forward", "depth": 5}}
```

## Implementation Priority

### Phase 1: Core Query Infrastructure
1. Query parser for structured field queries
2. Field-specific search in engine
3. Basic CLI scaffolding (`mcp-journal query`, `mcp-journal search`)

### Phase 2: Diagnostic Support
1. Diagnostic entry template
2. Active operation tracking
3. `journal_active` tool and CLI command
4. Duration-based queries

### Phase 3: Aggregation & Statistics
1. Aggregation engine (count, sum, avg, min, max)
2. `journal_stats` tool and CLI command
3. Group-by support

### Phase 4: Advanced Features
1. Watch mode (real-time monitoring)
2. Export formats (JSON, CSV)
3. Indexing for performance
4. Batching for high-volume diagnostics

### Phase 5: Polish
1. Query syntax shortcuts
2. Configuration options
3. Performance optimization
4. Documentation

## Success Criteria

1. **CLI Parity**: All MCP query capabilities available via CLI
2. **Sub-second Queries**: Simple queries complete in <100ms for journals with <10K entries
3. **Diagnostic Integration**: mcp-cygwin can send diagnostics and query them effectively
4. **Active Detection**: Can identify hanging operations within 1 second
5. **Export Capability**: Can export full journal or filtered subset in JSON/CSV
6. **Backwards Compatible**: Existing journal_search and journal_read unchanged

## Related Issues

- mcp-cygwin diagnostic integration (depends on this)
- Session handoff improvements (could use query for summary generation)
- Build orchestration (RBO) log analysis

## References

- Current mcp-journal tools: `src/mcp_journal/tools.py`
- Current search implementation: `src/mcp_journal/engine.py` (journal_search method)
- mcp-cygwin diagnostics: `src/mcp_cygwin/diagnostics.py`
