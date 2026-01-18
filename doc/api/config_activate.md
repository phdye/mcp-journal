# config_activate(3) - Activate Archived Configuration

## NAME

**config_activate** - Set an archived configuration as active

## SYNOPSIS

```
config_activate(
    archive_path: str,
    target_path: str,
    reason: str,
    journal_entry: str
) -> dict
```

## DESCRIPTION

The **config_activate** tool restores a previously archived configuration file to its original location (or a specified target). Before overwriting, it first archives the current file at the target location.

This provides safe rollback capability while maintaining the complete history of all configuration versions.

## PARAMETERS

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `archive_path` | string | Yes | Path to archived config to activate |
| `target_path` | string | Yes | Where to place the active copy |
| `reason` | string | Yes | Why this config is being activated |
| `journal_entry` | string | Yes | Link to journal entry (required) |

## RETURN VALUE

```json
{
  "status": "success",
  "activated": "configs/bootstrap.toml/2026-01-16T10-00-00_initial.toml",
  "target": "/home/user/rust/bootstrap.toml",
  "previous_archived": "configs/bootstrap.toml/2026-01-17T15-00-00_pre-rollback.toml",
  "reason": "rollback-after-failure",
  "journal_entry": "2026-01-17-010"
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | archive_path does not exist |
| `ValueError` | reason is empty |
| `ValueError` | journal_entry is empty (required) |
| `IOError` | Cannot write to target_path |
| `DuplicateContentError` | Target already has identical content |

## EXAMPLES

### Rollback to Previous Version

```json
{
  "archive_path": "configs/bootstrap.toml/2026-01-16T10-00-00_initial.toml",
  "target_path": "/home/user/rust/bootstrap.toml",
  "reason": "rollback-stage2-failure",
  "journal_entry": "2026-01-17-010"
}
```

### Activate Specific Version

```json
{
  "archive_path": "configs/config.json/2026-01-15T14-30-00_working.json",
  "target_path": "/home/user/project/config.json",
  "reason": "restore-working-config",
  "journal_entry": "2026-01-17-015"
}
```

## NOTES

### Safety First

Before activating, the current target file (if it exists) is automatically archived. This ensures you never lose a configuration version.

Sequence:
1. Archive current `target_path` with reason "pre-activation"
2. Copy `archive_path` to `target_path`
3. Update INDEX.md

### Journal Entry Requirement

Unlike other tools, `journal_entry` is **required** for config_activate. This enforces documentation of why configuration changes are made.

Create the journal entry first:
```json
{
  "author": "claude",
  "context": "Stage 2 build failed with linker errors",
  "analysis": "Previous config worked, rolling back",
  "intent": "Restore last known working configuration"
}
```

Then activate:
```json
{
  "archive_path": "configs/bootstrap.toml/...",
  "target_path": "bootstrap.toml",
  "reason": "rollback-linker-errors",
  "journal_entry": "2026-01-17-010"
}
```

### Finding Archives

List available archives:
```bash
ls configs/{filename}/
```

Or check INDEX.md:
```bash
cat configs/INDEX.md
```

### Workflow

1. **Identify** the archive to restore (check INDEX.md or list directory)

2. **Document** why in journal:
   ```json
   {"author": "claude", "context": "Build failed, need to rollback"}
   ```

3. **Activate** the archive:
   ```json
   {
     "archive_path": "configs/config.toml/2026-01-16T10-00-00.toml",
     "target_path": "config.toml",
     "reason": "rollback",
     "journal_entry": "2026-01-17-010"
   }
   ```

4. **Verify** the change worked

### Hooks

If configured:
- `hook_pre_activate(archive_path, target_path)` - Before activation
- `hook_post_activate(result)` - After successful activation

## SEE ALSO

- [config_archive(3)](config_archive.md) - Archive config files
- [config_diff(3)](config_diff.md) - Compare config versions
- [journal_append(3)](journal_append.md) - Document changes
