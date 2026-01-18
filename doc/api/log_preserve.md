# log_preserve(3) - Preserve Log File

## NAME

**log_preserve** - Preserve a log file with timestamp and outcome

## SYNOPSIS

```
log_preserve(
    file_path: str,
    category: str = None,
    outcome: str = None
) -> dict
```

## DESCRIPTION

The **log_preserve** tool moves a log file to the preserved logs directory with a timestamp and outcome indicator. This ensures that important log files are not overwritten or lost.

The original file is **moved** (not copied), preventing duplicate storage and ensuring the log is no longer in its original location where it might be overwritten.

## PARAMETERS

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | Yes | - | Path to log file to preserve |
| `category` | string | No | "general" | Log category (e.g., "build", "test") |
| `outcome` | string | No | "unknown" | Outcome (success/failure/interrupted/unknown) |

### Outcome Values

| Value | Description |
|-------|-------------|
| `success` | Operation completed successfully |
| `failure` | Operation failed |
| `interrupted` | Operation was interrupted |
| `unknown` | Outcome not determined |

## RETURN VALUE

```json
{
  "status": "success",
  "preserved_path": "logs/build/2026-01-17T14-30-00_success.log",
  "original_path": "/home/user/project/build.log",
  "category": "build",
  "outcome": "success",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "size_bytes": 45678
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | file_path does not exist |
| `ValueError` | Invalid outcome value |
| `IOError` | Cannot create logs directory or move file |

## EXAMPLES

### Basic Preserve

```json
{
  "file_path": "/home/user/project/output.log"
}
```

### Preserve Build Log

```json
{
  "file_path": "/home/user/rust/build.log",
  "category": "build",
  "outcome": "failure"
}
```

### Preserve Test Log

```json
{
  "file_path": "/home/user/project/test-results.log",
  "category": "test",
  "outcome": "success"
}
```

### Preserve with Interrupted Status

```json
{
  "file_path": "/home/user/rust/stage2.log",
  "category": "build",
  "outcome": "interrupted"
}
```

## NOTES

### Log Location

Preserved logs are stored as:
```
logs/
└── {category}/
    ├── 2026-01-17T14-30-00_success.log
    ├── 2026-01-17T15-00-00_failure.log
    └── ...
```

### INDEX.md

Each preserve operation updates `logs/INDEX.md`:

```markdown
# Preserved Logs

## build

| Timestamp | Outcome | Original Path | Size |
|-----------|---------|---------------|------|
| 2026-01-17T14:30:00 | success | /home/user/rust/build.log | 45KB |
| 2026-01-17T10:00:00 | failure | /home/user/rust/build.log | 12KB |

## test

| Timestamp | Outcome | Original Path | Size |
|-----------|---------|---------------|------|
| 2026-01-17T15:00:00 | success | /home/user/project/test.log | 8KB |
```

### Categories

Suggested categories:
- `build` - Build process logs
- `test` - Test execution logs
- `analysis` - Analysis tool output
- `deploy` - Deployment logs
- `general` - Uncategorized logs

### Integration with Journal

Document log preservation in journal entries:

```json
{
  "author": "claude",
  "context": "Build failed with linker errors",
  "log_produced": "logs/build/2026-01-17T14-30-00_failure.log",
  "outcome": "failure"
}
```

### Workflow

1. **Run operation** that produces log
2. **Preserve** the log:
   ```json
   {"file_path": "build.log", "category": "build", "outcome": "failure"}
   ```
3. **Document** in journal with `log_produced`
4. **Analyze** preserved log later

### File Movement

The original file is **moved**, not copied:
- Prevents duplicate storage
- Ensures log isn't overwritten by next run
- Original location is now empty

If you need to keep the original, copy it first before preserving.

### Hooks

If configured:
- `hook_pre_preserve(file_path, category)` - Before preserving
- `hook_post_preserve(log_record)` - After successful preserve

## SEE ALSO

- [journal_append(3)](journal_append.md) - Document with log_produced
- [state_snapshot(3)](state_snapshot.md) - Capture complete state
- [timeline(3)](timeline.md) - View logs in timeline
