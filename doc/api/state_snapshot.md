# state_snapshot(3) - Capture System State

## NAME

**state_snapshot** - Capture complete system state atomically

## SYNOPSIS

```
state_snapshot(
    name: str,
    include_configs: bool = True,
    include_env: bool = True,
    include_versions: bool = True,
    include_build_dir_listing: bool = False,
    build_dir: str = None
) -> dict
```

## DESCRIPTION

The **state_snapshot** tool captures complete system state at a point in time. This includes configuration files, environment variables, and tool versions. Snapshots enable exact reproduction of conditions at any recorded point.

Snapshots are stored as JSON files in the `snapshots/` directory and are essential for:
- Reproducing builds
- Debugging environment-dependent issues
- Session handoffs
- Before/after comparisons

## PARAMETERS

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | - | Snapshot name (e.g., "pre-build", "session-start") |
| `include_configs` | bool | True | Include configuration file contents |
| `include_env` | bool | True | Include environment variables |
| `include_versions` | bool | True | Include tool versions |
| `include_build_dir_listing` | bool | False | Include build directory listing |
| `build_dir` | string | None | Build directory path (required if listing) |

## RETURN VALUE

```json
{
  "status": "success",
  "snapshot_path": "snapshots/2026-01-17T14-30-00_pre-build.json",
  "name": "pre-build",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "components": {
    "configs": true,
    "environment": true,
    "versions": true,
    "build_listing": false
  }
}
```

### Snapshot File Content

```json
{
  "name": "pre-build",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "configs": {
    "bootstrap.toml": "[build]\ntarget = ...",
    "config.json": "{\"key\": \"value\"}"
  },
  "environment": {
    "PATH": "/usr/bin:/usr/local/bin",
    "CC": "gcc",
    "RUSTFLAGS": "-C target-cpu=native"
  },
  "versions": {
    "rustc": "rustc 1.92.0 (abc123 2026-01-15)",
    "gcc": "gcc (GCC) 13.2.0",
    "python": "Python 3.11.5"
  },
  "build_dir_listing": null
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | name is empty |
| `ValueError` | include_build_dir_listing but no build_dir |
| `IOError` | Cannot create snapshot file |
| `IOError` | Cannot read config files |

## EXAMPLES

### Basic Snapshot

```json
{
  "name": "session-start"
}
```

### Pre-Build Snapshot

```json
{
  "name": "pre-stage2-build",
  "include_build_dir_listing": true,
  "build_dir": "/home/user/rust/build"
}
```

### Minimal Snapshot (Versions Only)

```json
{
  "name": "version-check",
  "include_configs": false,
  "include_env": false,
  "include_versions": true
}
```

### Environment-Focused Snapshot

```json
{
  "name": "env-debug",
  "include_configs": false,
  "include_env": true,
  "include_versions": false
}
```

## NOTES

### Snapshot Location

Snapshots are stored as:
```
snapshots/
├── INDEX.md
├── 2026-01-17T14-30-00_pre-build.json
├── 2026-01-17T16-00-00_post-build.json
└── ...
```

### INDEX.md

Each snapshot updates `snapshots/INDEX.md`:

```markdown
# State Snapshots

| Timestamp | Name | Components |
|-----------|------|------------|
| 2026-01-17T14:30:00 | pre-build | configs, env, versions |
| 2026-01-17T16:00:00 | post-build | configs, env, versions, build_listing |
```

### Config Discovery

The `configs` component captures files based on configuration:
- Default: Discovers common config files in project root
- Configurable: Specify paths in `journal_config.toml`

```toml
[snapshot]
config_files = [
    "bootstrap.toml",
    "config.json",
    ".env"
]
```

### Version Commands

Tool versions are captured using configured commands:

```toml
[version_commands]
rustc = "rustc --version"
gcc = "gcc --version | head -1"
python = "python --version"
```

### Environment Filtering

Some environment variables are filtered by default:
- Variables containing "SECRET", "PASSWORD", "TOKEN", "KEY"
- Can be configured via `env_filter_patterns`

### Use Cases

**Session Start**:
```json
{"name": "session-start"}
```

**Before Major Change**:
```json
{"name": "pre-llvm-upgrade", "include_build_dir_listing": true, "build_dir": "build"}
```

**Debugging**:
```json
{"name": "debug-env-issue", "include_configs": true, "include_env": true}
```

**Comparing Before/After**:
1. `state_snapshot(name="pre-change")`
2. Make changes
3. `state_snapshot(name="post-change")`
4. Compare the two JSON files

### Integration with Journal

Document snapshots in journal entries:

```json
{
  "author": "claude",
  "context": "Starting stage 2 build",
  "intent": "Build with new LLVM settings",
  "config_used": "configs/bootstrap.toml/2026-01-17T14-30-00.toml"
}
```

Then create snapshot:
```json
{"name": "pre-stage2"}
```

## SEE ALSO

- [session_handoff(3)](session_handoff.md) - Generate handoff summary
- [timeline(3)](timeline.md) - View snapshots in timeline
- [config_archive(3)](config_archive.md) - Archive individual configs
