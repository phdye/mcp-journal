"""MCP Journal Configuration - Advanced Python Example

Copy to your project root as journal_config.py for full extensibility.

Convention:
- CONFIG dict for static configuration (same structure as TOML)
- Functions named hook_* become lifecycle hooks
- Functions named custom_tool_* become MCP tools
"""

import subprocess
from pathlib import Path

# =============================================================================
# Static Configuration (same structure as TOML)
# =============================================================================

CONFIG = {
    "project": {
        "name": "rust-bootstrap",
    },
    "directories": {
        "journal": "journal",
        "configs": "configs",
        "logs": "logs",
        "snapshots": "snapshots",
    },
    "tracking": {
        "config_patterns": ["*.toml", "bootstrap.toml", "config.toml"],
        "log_categories": ["stage0", "stage1", "stage2", "test"],
        "stages": ["stage0", "stage1", "stage2"],
    },
    "versions": {
        "rustc": {"command": "rustc --version", "regex": r"rustc (\d+\.\d+\.\d+)"},
        "cargo": "cargo --version",
        "gcc": "gcc --version | head -1",
        "llvm-config": "llvm-config --version",
    },
}


# =============================================================================
# Hooks - Called during engine operations
# =============================================================================

def hook_capture_versions(engine) -> dict:
    """Called by state_snapshot to capture additional tool versions.

    Return a dict of {name: version_string}.
    """
    versions = {}

    # Example: capture RBO version if present
    rbo_version_file = engine.config.project_root / ".rbo" / "version"
    if rbo_version_file.exists():
        versions["rbo"] = rbo_version_file.read_text().strip()

    # Example: capture custom build tool version
    try:
        result = subprocess.run(
            ["my-build-tool", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            versions["my-build-tool"] = result.stdout.strip()
    except Exception:
        pass

    return versions


def hook_pre_append(entry, custom_fields):
    """Called before appending a journal entry.

    Can modify the entry or add custom fields.

    Args:
        entry: JournalEntry being appended
        custom_fields: Dict of custom field values from tool call

    Returns:
        Modified JournalEntry
    """
    # Example: auto-add stage from environment
    import os
    if "BUILD_STAGE" in os.environ:
        if entry.references is None:
            entry.references = []
        entry.references.append(f"stage:{os.environ['BUILD_STAGE']}")

    return entry


def hook_post_append(entry):
    """Called after a journal entry is appended.

    Useful for notifications, syncing, etc.

    Args:
        entry: JournalEntry that was appended
    """
    # Example: print notification
    print(f"[Journal] Entry {entry.entry_id} recorded")


def hook_validate_entry(entry) -> list[str]:
    """Validate a journal entry before appending.

    Returns list of validation errors (empty = valid).
    """
    errors = []

    # Example: require context for non-amendments
    if entry.entry_type.value == "entry" and not entry.context:
        errors.append("Context is required for journal entries")

    return errors


# =============================================================================
# Custom Tools - Exposed as additional MCP tools
# =============================================================================

def custom_tool_rbo_state(engine, params) -> dict:
    """Capture RBO-specific state.

    Returns current RBO build phase, pending requests, and config.
    """
    rbo_dir = engine.config.project_root / ".rbo"
    if not rbo_dir.exists():
        return {"success": False, "error": "RBO not initialized in this project"}

    state = {"success": True}

    # Read RBO state files
    state_file = rbo_dir / "state.json"
    if state_file.exists():
        import json
        state["rbo_state"] = json.loads(state_file.read_text())

    config_file = rbo_dir / "bootstrap.toml"
    if config_file.exists():
        state["config_path"] = str(config_file)

    return state


def custom_tool_build_summary(engine, params) -> dict:
    """Generate a summary of recent build activity.

    Analyzes journal entries and logs to provide build statistics.
    """
    # Search for build-related entries
    results = engine.journal_search(
        query="build",
        date_from=params.get("since"),
    )

    # Count outcomes from logs
    logs_dir = engine.config.get_logs_path()
    success_count = len(list(logs_dir.glob("*.success.log")))
    failure_count = len(list(logs_dir.glob("*.failure.log")))

    return {
        "success": True,
        "journal_entries": len(results),
        "successful_builds": success_count,
        "failed_builds": failure_count,
        "success_rate": f"{success_count / (success_count + failure_count) * 100:.1f}%"
        if (success_count + failure_count) > 0
        else "N/A",
    }


async def custom_tool_async_example(engine, params) -> dict:
    """Example async custom tool.

    Custom tools can be async if needed for I/O operations.
    """
    import asyncio
    await asyncio.sleep(0.1)  # Simulate async operation
    return {"success": True, "message": "Async tool completed"}
