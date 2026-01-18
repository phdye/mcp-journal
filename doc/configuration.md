# Configuration Reference

**Version**: 0.2.0
**Last Updated**: 2026-01-17

## Table of Contents

1. [Overview](#overview)
2. [Configuration File Discovery](#configuration-file-discovery)
3. [TOML Configuration](#toml-configuration)
4. [JSON Configuration](#json-configuration)
5. [Python Configuration](#python-configuration)
6. [Configuration Options](#configuration-options)
7. [Templates](#templates)
8. [Version Commands](#version-commands)
9. [Hooks](#hooks)
10. [Custom Tools](#custom-tools)
11. [Environment Variables](#environment-variables)
12. [Examples](#examples)

---

## Overview

MCP Journal supports three configuration formats with increasing levels of flexibility:

| Format | File | Use Case |
|--------|------|----------|
| TOML | `journal_config.toml` | Simple declarative configuration |
| JSON | `journal_config.json` | Machine-generated configuration |
| Python | `journal_config.py` | Advanced with hooks and custom tools |

Configuration files are optional. If not provided, sensible defaults are used.

---

## Configuration File Discovery

MCP Journal searches for configuration files in the following order:

1. `journal_config.py` - Python module (highest priority)
2. `journal_config.toml` - TOML file
3. `.journal_config.toml` - Hidden TOML file
4. `journal_config.json` - JSON file
5. `.journal_config.json` - Hidden JSON file

The first file found is used. Specify an explicit path with `--config`:

```bash
mcp-journal --config /path/to/custom-config.toml --project-root /path/to/project
```

---

## TOML Configuration

### Complete Reference

```toml
# =============================================================================
# MCP Journal Configuration - TOML Format
# =============================================================================

# -----------------------------------------------------------------------------
# Project Settings
# -----------------------------------------------------------------------------
[project]
# Project name (used in snapshots and handoffs)
# Type: string
# Default: directory name
name = "my-project"

# -----------------------------------------------------------------------------
# Directory Paths
# -----------------------------------------------------------------------------
[paths]
# Journal directory (relative to project root)
# Type: string
# Default: "journal"
journal = "journal"

# Configurations archive directory
# Type: string
# Default: "configs"
configs = "configs"

# Logs directory
# Type: string
# Default: "logs"
logs = "logs"

# Snapshots directory
# Type: string
# Default: "snapshots"
snapshots = "snapshots"

# -----------------------------------------------------------------------------
# Tracking Settings
# -----------------------------------------------------------------------------
[tracking]
# Glob patterns for configuration files to track
# Type: array of strings
# Default: ["*.toml", "*.json", "*.yaml", "*.yml"]
config_patterns = [
    "*.toml",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.ini",
    "*.cfg",
    ".env*"
]

# Categories for log preservation
# Type: array of strings
# Default: ["build", "test", "deploy"]
log_categories = [
    "build",
    "test",
    "deploy",
    "analysis",
    "debug"
]

# Environment variable patterns to capture (regex)
# Type: array of strings
# Default: [".*"] (all variables)
env_patterns = [
    "^PATH$",
    "^HOME$",
    "^USER$",
    "^LANG$",
    "^CC$",
    "^CXX$",
    "^RUSTFLAGS$",
    "^CARGO_.*",
    "^NPM_.*"
]

# Environment variable patterns to exclude (regex)
# Type: array of strings
# Default: ["^(AWS|AZURE|GCP|SECRET|PASSWORD|TOKEN|KEY).*"]
env_exclude_patterns = [
    "^AWS_.*",
    "^AZURE_.*",
    "^GCP_.*",
    "^SECRET.*",
    "^PASSWORD.*",
    "^TOKEN.*",
    "^API_KEY.*",
    "^PRIVATE_KEY.*"
]

# -----------------------------------------------------------------------------
# Version Commands
# -----------------------------------------------------------------------------
# Simple format: name = "command"
[versions]
python = "python --version"
pip = "pip --version"
node = "node --version"
npm = "npm --version"
rust = "rustc --version"
cargo = "cargo --version"
git = "git --version"

# Extended format with regex parsing
[versions.gcc]
command = "gcc --version"
parse_regex = "gcc \\(.*\\) (\\d+\\.\\d+\\.\\d+)"

[versions.cmake]
command = "cmake --version"
parse_regex = "cmake version (\\d+\\.\\d+\\.\\d+)"

# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
[[templates]]
name = "deployment"
description = "Deployment operation entry"
required_fields = ["environment", "version"]
optional_fields = ["rollback_plan", "validation_steps", "approver"]
default_outcome = "partial"

[[templates]]
name = "analysis"
description = "Data analysis entry"
required_fields = ["dataset", "method"]
optional_fields = ["parameters", "results", "figures"]

[[templates]]
name = "review"
description = "Code review entry"
required_fields = ["pr_number", "reviewer"]
optional_fields = ["comments", "status", "blockers"]

# -----------------------------------------------------------------------------
# Validation Settings
# -----------------------------------------------------------------------------
[validation]
# Require templates for all entries
# Type: boolean
# Default: false
require_templates = false

# Validate references exist
# Type: boolean
# Default: true
validate_references = true

# Require outcome on all entries
# Type: boolean
# Default: false
require_outcome = false

# Maximum entry size in bytes
# Type: integer
# Default: 1048576 (1MB)
max_entry_size = 1048576
```

### Minimal Configuration

```toml
[project]
name = "my-project"

[versions]
python = "python --version"
```

---

## JSON Configuration

### Complete Reference

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "project": {
    "name": "my-project"
  },
  "paths": {
    "journal": "journal",
    "configs": "configs",
    "logs": "logs",
    "snapshots": "snapshots"
  },
  "tracking": {
    "config_patterns": ["*.toml", "*.json", "*.yaml"],
    "log_categories": ["build", "test", "deploy"],
    "env_patterns": ["^PATH$", "^HOME$"],
    "env_exclude_patterns": ["^SECRET.*", "^PASSWORD.*"]
  },
  "versions": {
    "python": "python --version",
    "node": "node --version",
    "gcc": {
      "command": "gcc --version",
      "parse_regex": "gcc \\(.*\\) (\\d+\\.\\d+\\.\\d+)"
    }
  },
  "templates": [
    {
      "name": "deployment",
      "description": "Deployment operation entry",
      "required_fields": ["environment", "version"],
      "optional_fields": ["rollback_plan"],
      "default_outcome": "partial"
    }
  ],
  "validation": {
    "require_templates": false,
    "validate_references": true,
    "require_outcome": false,
    "max_entry_size": 1048576
  }
}
```

### Minimal Configuration

```json
{
  "project": {
    "name": "my-project"
  }
}
```

---

## Python Configuration

Python configuration provides maximum flexibility with hooks and custom tools.

### Complete Reference

```python
"""
MCP Journal Configuration - Python Format

This module is imported by the journal engine. Define variables and functions
to customize behavior.
"""

from typing import Any, Dict, Optional
from mcp_journal.models import JournalEntry
from mcp_journal.engine import JournalEngine

# =============================================================================
# Project Settings
# =============================================================================

# Project name (required)
project_name = "my-project"

# Directory paths (optional, relative to project root)
journal_dir = "journal"
configs_dir = "configs"
logs_dir = "logs"
snapshots_dir = "snapshots"

# =============================================================================
# Tracking Settings
# =============================================================================

# Configuration file patterns
config_patterns = [
    "*.toml",
    "*.json",
    "*.yaml",
    "*.yml",
    "Makefile",
    "Dockerfile",
]

# Log categories
log_categories = [
    "build",
    "test",
    "deploy",
    "analysis",
]

# Environment variable patterns (include)
env_patterns = [
    r"^PATH$",
    r"^HOME$",
    r"^CC$",
    r"^CXX$",
]

# Environment variable patterns (exclude)
env_exclude_patterns = [
    r"^SECRET.*",
    r"^PASSWORD.*",
    r"^TOKEN.*",
    r"^API_KEY.*",
]

# =============================================================================
# Version Commands
# =============================================================================

# Simple string format
version_commands = {
    "python": "python --version",
    "pip": "pip --version",
    "git": "git --version",
}

# Extended format with regex
from mcp_journal.config import VersionCommand

version_commands_extended = [
    VersionCommand(
        name="gcc",
        command="gcc --version",
        parse_regex=r"gcc \(.*\) (\d+\.\d+\.\d+)",
    ),
    VersionCommand(
        name="cmake",
        command="cmake --version",
        parse_regex=r"cmake version (\d+\.\d+\.\d+)",
    ),
]

# =============================================================================
# Templates
# =============================================================================

from mcp_journal.config import EntryTemplateConfig

templates = {
    "deployment": EntryTemplateConfig(
        name="deployment",
        description="Deployment operation entry",
        required_fields=["environment", "version"],
        optional_fields=["rollback_plan", "validation_steps"],
        default_outcome="partial",
    ),
    "analysis": EntryTemplateConfig(
        name="analysis",
        description="Data analysis entry",
        required_fields=["dataset", "method"],
        optional_fields=["parameters", "results"],
    ),
}

# =============================================================================
# Validation Settings
# =============================================================================

require_templates = False
validate_references = True
require_outcome = False
max_entry_size = 1048576

# =============================================================================
# Hooks
# =============================================================================

def hook_pre_append(entry: JournalEntry, custom_fields: Dict[str, Any]) -> JournalEntry:
    """
    Called before each journal entry is written.

    Use this to:
    - Validate entry content
    - Add computed fields
    - Transform data
    - Enforce business rules

    Args:
        entry: The entry about to be written
        custom_fields: Additional custom fields provided

    Returns:
        Modified entry (or original if no changes)

    Raises:
        Exception to abort the append operation
    """
    # Example: Enforce minimum context length
    if entry.context and len(entry.context) < 10:
        raise ValueError("Context must be at least 10 characters")

    # Example: Add computed field
    if custom_fields.get("auto_tag"):
        entry.context = f"[{custom_fields['auto_tag']}] {entry.context}"

    return entry


def hook_post_append(entry: JournalEntry) -> None:
    """
    Called after each journal entry is written.

    Use this to:
    - Send notifications
    - Sync to external systems
    - Update dashboards
    - Trigger workflows

    Args:
        entry: The entry that was written
    """
    # Example: Log to external system
    print(f"Entry created: {entry.entry_id}")

    # Example: Send notification on failure
    if entry.outcome == "failure":
        send_notification(f"Failure recorded: {entry.entry_id}")


def hook_pre_archive(file_path: str, reason: str) -> Optional[str]:
    """
    Called before archiving a configuration file.

    Use this to:
    - Validate archive operations
    - Add preprocessing
    - Modify the reason

    Args:
        file_path: Path to file being archived
        reason: Reason for archiving

    Returns:
        Modified reason, or None to use original

    Raises:
        Exception to abort the archive operation
    """
    # Example: Prevent archiving certain files
    if "secrets" in file_path.lower():
        raise ValueError(f"Cannot archive sensitive file: {file_path}")

    return reason


def hook_capture_versions(engine: JournalEngine) -> Dict[str, str]:
    """
    Called during state_snapshot to capture custom version information.

    Use this to:
    - Add custom tool versions
    - Capture dynamic version info
    - Query external systems

    Args:
        engine: The journal engine instance

    Returns:
        Dictionary of version name -> version string
    """
    import subprocess

    versions = {}

    # Example: Capture Docker version
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            versions["docker"] = result.stdout.strip()
    except Exception:
        versions["docker"] = "not installed"

    # Example: Capture custom tool version
    versions["internal_tool"] = get_internal_tool_version()

    return versions


def hook_session_handoff(
    engine: JournalEngine,
    entries: list,
    format: str,
) -> Optional[str]:
    """
    Called during session_handoff to customize the output.

    Args:
        engine: The journal engine instance
        entries: Entries included in handoff
        format: Output format (markdown or json)

    Returns:
        Custom handoff content, or None for default
    """
    # Return None to use default formatting
    return None

# =============================================================================
# Custom MCP Tools
# =============================================================================

def custom_tool_deploy_check(engine: JournalEngine, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check deployment readiness.

    This function becomes an MCP tool named "deploy_check".
    The docstring becomes the tool description.

    Args:
        engine: The journal engine instance
        params: Parameters passed to the tool
            - environment (str, required): Target environment
            - version (str, optional): Version to deploy

    Returns:
        Result dictionary
    """
    environment = params.get("environment", "staging")
    version = params.get("version", "latest")

    # Perform readiness checks
    checks = {
        "config_archived": check_config_archived(engine),
        "tests_passed": check_tests_passed(engine),
        "approvals": check_approvals(environment),
    }

    ready = all(checks.values())

    return {
        "ready": ready,
        "environment": environment,
        "version": version,
        "checks": checks,
    }


async def custom_tool_async_report(
    engine: JournalEngine,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate async report (supports async operations).

    This function becomes an MCP tool named "async_report".
    Async functions are awaited automatically.

    Args:
        engine: The journal engine instance
        params: Parameters passed to the tool
            - report_type (str, required): Type of report

    Returns:
        Report data
    """
    report_type = params.get("report_type", "summary")

    # Perform async operations
    data = await fetch_report_data(report_type)

    return {
        "report_type": report_type,
        "data": data,
    }


# Tool schema (optional, auto-generated if not provided)
custom_tool_deploy_check_schema = {
    "type": "object",
    "properties": {
        "environment": {
            "type": "string",
            "description": "Target environment (staging, production)",
            "enum": ["staging", "production"],
        },
        "version": {
            "type": "string",
            "description": "Version to deploy",
        },
    },
    "required": ["environment"],
}

# =============================================================================
# Helper Functions (not exposed as tools)
# =============================================================================

def send_notification(message: str) -> None:
    """Send notification (implementation depends on your system)."""
    pass

def get_internal_tool_version() -> str:
    """Get internal tool version."""
    return "1.0.0"

def check_config_archived(engine: JournalEngine) -> bool:
    """Check if current config is archived."""
    return True

def check_tests_passed(engine: JournalEngine) -> bool:
    """Check if tests passed."""
    return True

def check_approvals(environment: str) -> bool:
    """Check deployment approvals."""
    return environment != "production"

async def fetch_report_data(report_type: str) -> dict:
    """Fetch report data asynchronously."""
    return {"type": report_type}
```

### Minimal Python Configuration

```python
"""Minimal MCP Journal configuration."""

project_name = "my-project"

version_commands = {
    "python": "python --version",
}
```

---

## Configuration Options

### Project Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `project.name` | string | directory name | Project identifier |

### Path Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `paths.journal` | string | `"journal"` | Journal directory |
| `paths.configs` | string | `"configs"` | Config archive directory |
| `paths.logs` | string | `"logs"` | Log directory |
| `paths.snapshots` | string | `"snapshots"` | Snapshot directory |

### Tracking Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tracking.config_patterns` | array | `["*.toml", ...]` | Config file patterns |
| `tracking.log_categories` | array | `["build", ...]` | Log categories |
| `tracking.env_patterns` | array | `[".*"]` | Env vars to include |
| `tracking.env_exclude_patterns` | array | `["^SECRET.*", ...]` | Env vars to exclude |

### Validation Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `validation.require_templates` | boolean | `false` | Require templates |
| `validation.validate_references` | boolean | `true` | Validate references |
| `validation.require_outcome` | boolean | `false` | Require outcome |
| `validation.max_entry_size` | integer | `1048576` | Max entry size (bytes) |

---

## Templates

### Template Definition

```toml
[[templates]]
name = "template_name"           # Required: unique identifier
description = "Description"      # Required: human-readable description
required_fields = ["field1"]     # Required: fields that must be provided
optional_fields = ["field2"]     # Optional: additional allowed fields
default_outcome = "partial"      # Optional: default outcome value
```

### Built-in Templates

Three templates are always available:

#### diagnostic

For tool call tracking:

| Field | Required | Description |
|-------|----------|-------------|
| `tool` | Yes | Tool name |
| `status` | Yes | Execution status |
| `command` | No | Command executed |
| `duration_ms` | No | Duration in ms |
| `exit_code` | No | Exit code |
| `error_type` | No | Error type |
| `analysis` | No | Analysis |

#### build

For build operations:

| Field | Required | Description |
|-------|----------|-------------|
| `target` | Yes | Build target |
| `config` | No | Configuration |
| `flags` | No | Build flags |

#### test

For test execution:

| Field | Required | Description |
|-------|----------|-------------|
| `target` | Yes | Test target |
| `test_filter` | No | Test filter |
| `flags` | No | Test flags |

---

## Version Commands

### Simple Format

```toml
[versions]
name = "command to run"
```

The entire output becomes the version string.

### Extended Format

```toml
[versions.name]
command = "command to run"
parse_regex = "regex with (capture group)"
```

The first capture group becomes the version string.

### Examples

```toml
[versions]
# Simple: full output
python = "python --version"     # -> "Python 3.10.0"

# Extended: extract version number
[versions.gcc]
command = "gcc --version"
parse_regex = "(\\d+\\.\\d+\\.\\d+)"  # -> "12.2.0"

# Extended: extract specific match
[versions.node]
command = "node --version"
parse_regex = "v(\\d+\\.\\d+\\.\\d+)"  # -> "18.0.0"
```

---

## Hooks

### Available Hooks

| Hook | Signature | Purpose |
|------|-----------|---------|
| `hook_pre_append` | `(entry, custom_fields) -> entry` | Before journal entry |
| `hook_post_append` | `(entry) -> None` | After journal entry |
| `hook_pre_archive` | `(file_path, reason) -> reason` | Before config archive |
| `hook_capture_versions` | `(engine) -> {name: version}` | Custom versions |
| `hook_session_handoff` | `(engine, entries, format) -> content` | Custom handoff |

### Hook Guidelines

1. **Raise exceptions to abort operations**
2. **Return modified values or `None` for defaults**
3. **Keep hooks fast** - they run synchronously
4. **Handle errors gracefully** - log but don't crash

---

## Custom Tools

### Defining Custom Tools

In Python config, any function starting with `custom_tool_` becomes an MCP tool:

```python
def custom_tool_my_tool(engine, params):
    """Tool description shown to users."""
    return {"result": "value"}
```

The tool name is the function name without `custom_tool_` prefix.

### Tool Schema

Optionally define input schema:

```python
custom_tool_my_tool_schema = {
    "type": "object",
    "properties": {
        "param1": {
            "type": "string",
            "description": "Parameter description",
        },
    },
    "required": ["param1"],
}
```

### Async Tools

Async functions are supported:

```python
async def custom_tool_async_operation(engine, params):
    """Async tool description."""
    result = await some_async_operation()
    return {"result": result}
```

---

## Environment Variables

### Runtime Variables

| Variable | Description |
|----------|-------------|
| `MCP_JOURNAL_PROJECT_ROOT` | Override project root |
| `MCP_JOURNAL_CONFIG` | Config file path |
| `MCP_JOURNAL_DEBUG` | Enable debug logging |
| `PYTHONUNBUFFERED` | Recommended for MCP servers |

### Usage

```bash
export MCP_JOURNAL_PROJECT_ROOT=/path/to/project
export MCP_JOURNAL_CONFIG=/path/to/config.toml
export MCP_JOURNAL_DEBUG=1
mcp-journal
```

---

## Examples

### Minimal TOML

```toml
[project]
name = "my-project"
```

### Development Project

```toml
[project]
name = "web-app"

[tracking]
config_patterns = [
    "*.toml",
    "*.json",
    "*.yaml",
    "package.json",
    "tsconfig.json",
    ".env*"
]
log_categories = ["build", "test", "lint", "deploy"]

[versions]
node = "node --version"
npm = "npm --version"
typescript = "tsc --version"

[[templates]]
name = "feature"
description = "Feature implementation entry"
required_fields = ["feature_name", "ticket"]
optional_fields = ["dependencies", "tests_added"]
```

### Data Science Project

```toml
[project]
name = "ml-experiment"

[tracking]
config_patterns = [
    "*.yaml",
    "*.json",
    "requirements*.txt",
    "*.ipynb"
]
log_categories = ["train", "evaluate", "preprocess", "export"]

[versions]
python = "python --version"
pytorch = "python -c 'import torch; print(torch.__version__)'"
cuda = "nvcc --version"

[[templates]]
name = "experiment"
description = "ML experiment entry"
required_fields = ["model", "dataset"]
optional_fields = ["hyperparameters", "metrics", "notes"]
default_outcome = "partial"
```

### CI/CD Pipeline

```toml
[project]
name = "pipeline"

[tracking]
config_patterns = [".gitlab-ci.yml", "Jenkinsfile", "*.yaml"]
log_categories = ["build", "test", "security-scan", "deploy"]
env_exclude_patterns = [
    "^CI_.*TOKEN.*",
    "^DOCKER_.*",
    "^AWS_.*"
]

[versions]
docker = "docker --version"
kubectl = "kubectl version --client"

[[templates]]
name = "pipeline_stage"
description = "CI/CD pipeline stage"
required_fields = ["stage", "job"]
optional_fields = ["artifacts", "duration"]
```

---

## See Also

- [User Guide](user-guide.md)
- [CLI Reference](cli-reference.md)
- [Python Configuration API](api/README.md)
