# config_archive(3) - Archive Configuration File

## NAME

**config_archive** - Archive a configuration file before modification

## SYNOPSIS

```
config_archive(
    file_path: str,
    reason: str,
    journal_entry: str = None,
    stage: str = None
) -> dict
```

## DESCRIPTION

The **config_archive** tool creates a timestamped copy of a configuration file before it is modified. This preserves the complete history of configuration changes, enabling rollback and comparison.

The archive is stored in `configs/{filename}/` with a timestamped filename. If the exact same content has already been archived, the operation is refused to prevent duplicates.

## PARAMETERS

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | Yes | - | Path to config file to archive |
| `reason` | string | Yes | - | Why the file is being archived |
| `journal_entry` | string | No | None | Link to journal entry explaining change |
| `stage` | string | No | None | Build stage (e.g., "stage1", "analysis") |

## RETURN VALUE

```json
{
  "status": "success",
  "archive_path": "configs/bootstrap.toml/2026-01-17T14-30-00_pre-llvm-change.toml",
  "original_path": "/path/to/bootstrap.toml",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "reason": "pre-llvm-change",
  "content_hash": "sha256:abc123..."
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | file_path does not exist |
| `ValueError` | reason is empty |
| `DuplicateContentError` | Identical content already archived |
| `IOError` | Cannot create archive directory or file |

## EXAMPLES

### Basic Archive

```json
{
  "file_path": "/home/user/project/config.toml",
  "reason": "pre-update"
}
```

### Archive with Journal Link

```json
{
  "file_path": "/home/user/rust/bootstrap.toml",
  "reason": "changing-llvm-settings",
  "journal_entry": "2026-01-17-005"
}
```

### Archive with Stage

```json
{
  "file_path": "/home/user/rust/bootstrap.toml",
  "reason": "stage2-adjustments",
  "stage": "stage2"
}
```

## NOTES

### Archive Location

Archives are stored as:
```
configs/
└── {filename}/
    ├── 2026-01-17T14-30-00_{reason}.{ext}
    ├── 2026-01-17T15-00-00_{reason}.{ext}
    └── ...
```

The filename is sanitized and the reason is included in the archive filename.

### Duplicate Detection

The tool computes a SHA-256 hash of the file content. If an archive with identical content exists, the operation fails with `DuplicateContentError`. This prevents storing redundant copies.

To check if content differs from last archive, use **config_diff**(3).

### INDEX.md

Each archive operation updates `configs/INDEX.md`:

```markdown
# Configuration Archives

## bootstrap.toml

| Timestamp | Reason | Journal Entry | Stage |
|-----------|--------|---------------|-------|
| 2026-01-17T14:30:00 | pre-llvm-change | 2026-01-17-005 | stage2 |
| 2026-01-16T10:00:00 | initial-setup | 2026-01-16-001 | stage1 |
```

### Workflow

1. **Archive** before making changes:
   ```json
   {"file_path": "config.toml", "reason": "pre-change"}
   ```

2. **Make changes** to the configuration file

3. **Document** in journal:
   ```json
   {
     "author": "claude",
     "context": "Modified config.toml to enable feature X",
     "config_used": "configs/config.toml/2026-01-17T14-30-00_pre-change.toml"
   }
   ```

### Hooks

If configured:
- `hook_pre_archive(file_path, reason)` - Before archiving
- `hook_post_archive(archive)` - After successful archive

## SEE ALSO

- [config_activate(3)](config_activate.md) - Restore archived config
- [config_diff(3)](config_diff.md) - Compare config versions
- [journal_append(3)](journal_append.md) - Document config changes
