# Future Features

Planned enhancements for MCP Journal Server, organized by priority and effort.

## High Value / Low Effort

### `journal_read`
Read entries by ID or date range.

```typescript
{
  entry_id?: string,      // Specific entry (e.g., "2026-01-06-003")
  date?: string,          // All entries for date (YYYY-MM-DD)
  date_from?: string,     // Range start
  date_to?: string,       // Range end
  include_content: bool   // Full content vs summary
}
```

**Rationale**: Currently search-only; direct access needed for reviewing specific entries.

---

### `config_diff`
Show diff between two archived configs.

```typescript
{
  path_a: string,         // First config (archive path or "current")
  path_b: string,         // Second config (archive path)
  context_lines?: number  // Lines of context (default: 3)
}
```

**Returns**: Unified diff format with additions/deletions highlighted.

**Rationale**: Essential for debugging "what changed between builds?"

---

### `config_list`
List archived configs with filters.

```typescript
{
  name_pattern?: string,  // Glob pattern (e.g., "bootstrap.*")
  stage?: string,         // Filter by stage
  date_from?: string,
  date_to?: string,
  include_superseded?: bool
}
```

**Rationale**: Navigate history without parsing INDEX.md manually.

---

### `log_tail`
Read last N lines of a preserved log.

```typescript
{
  log_path: string,       // Path to preserved log
  lines?: number,         // Number of lines (default: 100)
  grep?: string           // Optional filter pattern
}
```

**Rationale**: Quick inspection without reading entire multi-MB log files.

---

## Medium Value / Medium Effort

### `session_handoff`
Generate markdown summary for session handoff.

```typescript
{
  date_from?: string,     // Start of session (default: today)
  date_to?: string,       // End of session (default: now)
  include_configs?: bool, // Include config changes
  include_logs?: bool,    // Include log summaries
  format?: "markdown" | "json"
}
```

**Returns**:
```markdown
# Session Handoff - 2026-01-06

## Summary
- 5 journal entries
- 2 config changes
- 1 successful build, 2 failures

## Key Events
1. [14:30] Changed bootstrap.toml channel from stable to dev
2. [14:45] Build failed: missing crate 'core'
3. [15:20] Fixed with llvm.link-shared = true
...

## Current State
- Active config: configs/bootstrap.2026-01-06.1520.stage1.toml
- Last outcome: success

## Recommended Next Steps
[From last journal entry's next_steps field]
```

**Rationale**: Solves the original context-loss problem between sessions.

---

### `timeline`
Unified chronological view across journal/configs/logs/snapshots.

```typescript
{
  date_from?: string,
  date_to?: string,
  types?: ("entry" | "config" | "log" | "snapshot")[],
  limit?: number
}
```

**Returns**: Interleaved timeline of all events sorted by timestamp.

**Rationale**: See everything that happened in order, regardless of type.

---

### `config_activate_preview`
Show what `config_activate` would do without executing.

```typescript
{
  archive_path: string,
  target_path: string
}
```

**Returns**:
```json
{
  "will_archive_current": true,
  "current_path": "bootstrap.toml",
  "current_archive_name": "bootstrap.2026-01-06.1600.toml",
  "diff_from_current": "...",
  "warnings": []
}
```

**Rationale**: Safety check before state changes.

---

### `integrity_check`
Verify INDEX.md matches actual files and detect issues.

```typescript
{
  directory: "configs" | "logs" | "snapshots" | "all",
  fix?: bool  // Auto-fix minor issues (add missing entries)
}
```

**Returns**:
```json
{
  "status": "warnings",
  "issues": [
    {"type": "missing_from_index", "file": "..."},
    {"type": "orphaned_index_entry", "entry": "..."},
    {"type": "hash_mismatch", "file": "..."}
  ]
}
```

**Rationale**: Detect corruption or manual edits that break integrity.

---

### Git Integration
Optional auto-commit on journal operations.

**Configuration** (in `journal_config.toml`):
```toml
[git]
enabled = true
auto_commit = true
commit_message_template = "journal: {operation} - {summary}"
branch = "journal"  # Optional separate branch
```

**Behavior**:
- `journal_append` → commits journal file
- `config_archive` → commits archived config
- `state_snapshot` → commits snapshot
- Never auto-push (user controls remote sync)

**Rationale**: Version control without manual commits.

---

## High Value / Higher Effort

### Causality Links
Link configs → builds → logs → outcomes.

**New fields in journal entries**:
```typescript
{
  caused_by?: string[],   // Entry IDs that led to this
  causes?: string[],      // Entry IDs this leads to
  config_used?: string,   // Config archive path
  log_produced?: string,  // Log path produced
  outcome?: "success" | "failure" | "partial"
}
```

**New tool**: `trace_causality`
```typescript
{
  entry_id: string,
  direction: "forward" | "backward" | "both",
  depth?: number
}
```

**Returns**: Graph of related entries showing cause-effect chains.

**Rationale**: "This config caused this failure" - essential for debugging.

---

### Templates
Pre-defined entry templates per project.

**Configuration**:
```toml
[templates.build_start]
context = "Starting {stage} build"
intent = "Build stage {stage} with config {config}"
required_fields = ["stage", "config"]

[templates.build_complete]
context = "Completed {stage} build"
observation = "Exit code: {exit_code}"
required_fields = ["stage", "exit_code", "outcome"]
```

**New tool**: `journal_append_template`
```typescript
{
  template: string,
  values: { [key: string]: string },
  author: string
}
```

**Rationale**: Consistent structure for common operations.

---

### Notifications
Webhook/callback on events.

**Configuration**:
```toml
[notifications.slack]
url = "https://hooks.slack.com/..."
events = ["failure", "config_change"]
template = "Build {outcome}: {summary}"

[notifications.webhook]
url = "http://localhost:8080/journal"
events = ["*"]
format = "json"
```

**Hook-based alternative** (in `journal_config.py`):
```python
def hook_on_event(event_type: str, data: dict):
    if event_type == "log_preserve" and data["outcome"] == "failure":
        send_alert(f"Build failed: {data['category']}")
```

**Rationale**: Integration with external monitoring/alerting systems.

---

### Retention Policies
Manage disk usage over time (never delete, but compress/archive).

**Configuration**:
```toml
[retention]
compress_after_days = 30      # gzip old logs/snapshots
archive_after_days = 90       # Move to archive/ subdirectory
warn_at_size_mb = 1000        # Warn when journal exceeds size
```

**New tool**: `retention_apply`
```typescript
{
  dry_run?: bool,
  force?: bool  // Skip confirmation
}
```

**Behavior**:
- Compresses files older than threshold (`.log` → `.log.gz`)
- Moves very old files to `archive/` subdirectory
- Updates INDEX.md with new paths
- **Never deletes** - just reorganizes

**Rationale**: Long-running projects accumulate significant data.

---

## Additional Hooks

These hooks would be called at appropriate points if defined in `journal_config.py`:

| Hook | Called When | Parameters |
|------|-------------|------------|
| `hook_format_entry` | Before writing markdown | `(entry, custom_fields)` → `str` |
| `hook_validate_config` | Before archiving config | `(path, content)` → `list[str]` (errors) |
| `hook_on_failure` | When log with outcome=failure preserved | `(log_record)` |
| `hook_summarize` | When generating handoff | `(entries, configs, logs)` → `str` |
| `hook_on_event` | Any operation completes | `(event_type, data)` |

---

## Implementation Priority

Suggested order based on value/effort ratio:

1. **journal_read** - Simple, high utility
2. **config_diff** - Directly addresses debugging pain
3. **config_list** - Navigation convenience
4. **log_tail** - Quick inspection
5. **session_handoff** - Solves original context-loss problem
6. **integrity_check** - Safety/reliability
7. **timeline** - Unified view
8. **config_activate_preview** - Safety
9. **git integration** - Version control
10. **causality links** - Advanced debugging
11. **templates** - Consistency
12. **notifications** - External integration
13. **retention** - Long-term management

---

## Notes

- All features maintain append-only semantics
- No feature ever deletes user data
- Compression/archival preserves originals
- Git integration is opt-in and non-destructive
