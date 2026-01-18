# config_diff(3) - Compare Configuration Versions

## NAME

**config_diff** - Show differences between configuration versions

## SYNOPSIS

```
config_diff(
    path_a: str,
    path_b: str,
    context_lines: int = 3
) -> str
```

## DESCRIPTION

The **config_diff** tool compares two configuration files and returns a unified diff showing the differences. It can compare:

- Two archived versions
- An archived version with the current active file
- Any two files

This is useful for understanding what changed between versions and for reviewing changes before activation.

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path_a` | string | - | First config path |
| `path_b` | string | - | Second config path |
| `context_lines` | integer | 3 | Lines of context around changes |

### Special Path Syntax

Use `current:` prefix to reference the active file:
- `current:/path/to/config.toml` - The current active file

## RETURN VALUE

Returns a unified diff string:

```diff
--- configs/bootstrap.toml/2026-01-16T10-00-00_initial.toml
+++ configs/bootstrap.toml/2026-01-17T14-30-00_llvm-change.toml
@@ -10,7 +10,7 @@
 [llvm]
 download-ci-llvm = false
-link-shared = false
+link-shared = true
 static-libstdcpp = true
```

If files are identical, returns empty string.

## ERRORS

| Error | Cause |
|-------|-------|
| `FileNotFoundError` | path_a or path_b does not exist |
| `ValueError` | Invalid path format |

## EXAMPLES

### Compare Two Archives

```json
{
  "path_a": "configs/bootstrap.toml/2026-01-16T10-00-00_initial.toml",
  "path_b": "configs/bootstrap.toml/2026-01-17T14-30-00_llvm-change.toml"
}
```

### Compare Archive with Current

```json
{
  "path_a": "configs/bootstrap.toml/2026-01-16T10-00-00_initial.toml",
  "path_b": "current:/home/user/rust/bootstrap.toml"
}
```

### More Context Lines

```json
{
  "path_a": "configs/config.json/2026-01-15.json",
  "path_b": "configs/config.json/2026-01-17.json",
  "context_lines": 10
}
```

### No Context (Changes Only)

```json
{
  "path_a": "configs/a.toml",
  "path_b": "configs/b.toml",
  "context_lines": 0
}
```

## NOTES

### Diff Format

The output uses unified diff format:
- `---` line shows the first file
- `+++` line shows the second file
- `@@` lines show line numbers
- `-` prefix for removed lines
- `+` prefix for added lines
- Space prefix for context lines

### Use Cases

**Before Activation**:
Check what will change when activating an archive:
```json
{
  "path_a": "current:/path/to/config.toml",
  "path_b": "configs/config.toml/2026-01-16_working.toml"
}
```

**Understanding History**:
See what changed between two points in time:
```json
{
  "path_a": "configs/config.toml/2026-01-10.toml",
  "path_b": "configs/config.toml/2026-01-17.toml"
}
```

**Reviewing Recent Changes**:
Compare current with most recent archive:
```json
{
  "path_a": "configs/config.toml/2026-01-17T14-30-00.toml",
  "path_b": "current:/path/to/config.toml"
}
```

### Integration with Workflow

1. **Archive** before changes: `config_archive`
2. **Make changes** to the file
3. **Compare** to see what changed: `config_diff`
4. **Document** in journal: `journal_append`

### Empty Diff

If the diff is empty (files are identical), consider:
- The files haven't actually changed
- You may not need to archive again (duplicate detection will prevent it)

## SEE ALSO

- [config_archive(3)](config_archive.md) - Archive config files
- [config_activate(3)](config_activate.md) - Restore archived config
- [journal_append(3)](journal_append.md) - Document changes
