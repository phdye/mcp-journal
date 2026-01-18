# index_rebuild(3) - Rebuild INDEX.md Files

## NAME

**index_rebuild** - Rebuild INDEX.md files from actual files

## SYNOPSIS

```
index_rebuild(
    directory: str,
    dry_run: bool = False
) -> dict
```

## DESCRIPTION

The **index_rebuild** tool reconstructs the INDEX.md file for a managed directory (configs, logs, or snapshots) by scanning the actual files present. This is a recovery tool for when INDEX.md becomes out of sync with the actual contents.

The SQLite journal index can be rebuilt using the CLI command `mcp-journal rebuild-index`.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | string | - | Directory to rebuild ("configs", "logs", "snapshots") |
| `dry_run` | bool | False | Preview without writing |

### Directory Values

| Value | Description |
|-------|-------------|
| `configs` | Rebuild configs/INDEX.md |
| `logs` | Rebuild logs/INDEX.md |
| `snapshots` | Rebuild snapshots/INDEX.md |

## RETURN VALUE

### Normal Mode

```json
{
  "status": "success",
  "directory": "configs",
  "index_path": "configs/INDEX.md",
  "files_indexed": 15,
  "previous_entries": 12,
  "entries_added": 3,
  "entries_removed": 0
}
```

### Dry Run Mode

```json
{
  "status": "dry_run",
  "directory": "configs",
  "files_found": 15,
  "current_entries": 12,
  "would_add": 3,
  "would_remove": 0,
  "changes": [
    {"action": "add", "file": "configs/bootstrap.toml/2026-01-17T14-30-00.toml"},
    {"action": "add", "file": "configs/bootstrap.toml/2026-01-17T15-00-00.toml"},
    {"action": "add", "file": "configs/config.json/2026-01-17T10-00-00.json"}
  ]
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Invalid directory value |
| `FileNotFoundError` | Directory does not exist |
| `IOError` | Cannot write INDEX.md |

## EXAMPLES

### Rebuild Configs Index

```json
{
  "directory": "configs"
}
```

### Preview Logs Rebuild

```json
{
  "directory": "logs",
  "dry_run": true
}
```

### Rebuild Snapshots Index

```json
{
  "directory": "snapshots"
}
```

## NOTES

### When to Rebuild

Use index_rebuild when:
- INDEX.md is missing or corrupted
- Files were added/removed manually
- INDEX.md is out of sync with actual files
- After recovering from backup

### INDEX.md Format

Each directory has a specific INDEX.md format:

**configs/INDEX.md**:
```markdown
# Configuration Archives

## bootstrap.toml

| Timestamp | Reason | Journal Entry | Stage |
|-----------|--------|---------------|-------|
| 2026-01-17T14:30:00 | pre-build | 2026-01-17-005 | stage2 |
```

**logs/INDEX.md**:
```markdown
# Preserved Logs

## build

| Timestamp | Outcome | Original Path | Size |
|-----------|---------|---------------|------|
| 2026-01-17T14:30:00 | success | /path/to/build.log | 45KB |
```

**snapshots/INDEX.md**:
```markdown
# State Snapshots

| Timestamp | Name | Components |
|-----------|------|------------|
| 2026-01-17T14:30:00 | pre-build | configs, env, versions |
```

### Metadata Extraction

When rebuilding, metadata is extracted from:
- Filename (timestamp, reason/outcome)
- File content (where possible)
- File size

Some metadata may be incomplete if files were added manually without using the proper tools.

### SQLite Index Rebuild

To rebuild the SQLite journal index (separate from INDEX.md files):

```bash
mcp-journal rebuild-index --verbose
```

Or programmatically:
```python
engine._index.rebuild(engine.config.journal_dir)
```

### Backup Recommendation

Before rebuilding, consider backing up the current INDEX.md:

```bash
cp configs/INDEX.md configs/INDEX.md.bak
```

### Verification

After rebuilding, verify the contents:

```bash
cat configs/INDEX.md
```

Compare file count:
```bash
find configs -type f -name "*.toml" | wc -l
```

## SEE ALSO

- [config_archive(3)](config_archive.md) - Archive configs
- [log_preserve(3)](log_preserve.md) - Preserve logs
- [state_snapshot(3)](state_snapshot.md) - Create snapshots
- [CLI Reference](../cli-reference.md) - rebuild-index command
