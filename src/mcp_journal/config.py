"""Configuration loading for MCP Journal.

Supports three tiers:
1. Simple config via .toml or .json - most users
2. Python config via .py - power users with custom tools/hooks
3. Full override via subclassing - rare cases
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# Python 3.11+ has tomllib in stdlib; fall back to tomli for older versions
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Python <3.11
    except ImportError:  # pragma: no cover
        tomllib = None


@dataclass
class VersionCommand:
    """Command to capture a tool version."""
    name: str
    command: str
    parse_regex: Optional[str] = None  # Extract version from output


@dataclass
class EntryTemplateConfig:
    """Template configuration from config file."""
    name: str
    description: str = ""
    context: Optional[str] = None
    intent: Optional[str] = None
    action: Optional[str] = None
    observation: Optional[str] = None
    analysis: Optional[str] = None
    next_steps: Optional[str] = None
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    default_outcome: Optional[str] = None


# Default templates available to all projects
DEFAULT_TEMPLATES = {
    "diagnostic": EntryTemplateConfig(
        name="diagnostic",
        description="Tool call diagnostic entry for tracking command execution",
        context="Executing {tool} command",
        action="{command}",
        observation="Exit code: {exit_code}, Duration: {duration_ms}ms",
        analysis="{analysis}",
        required_fields=["tool", "status"],
        optional_fields=["command", "duration_ms", "exit_code", "error_type", "analysis"],
        default_outcome=None,  # Will be set based on status
    ),
    "build": EntryTemplateConfig(
        name="build",
        description="Build operation entry",
        context="Building {target}",
        intent="Compile and link {target} with {config}",
        action="Running build command",
        required_fields=["target"],
        optional_fields=["config", "flags"],
        default_outcome=None,
    ),
    "test": EntryTemplateConfig(
        name="test",
        description="Test execution entry",
        context="Running tests for {target}",
        intent="Verify {target} functionality",
        required_fields=["target"],
        optional_fields=["test_filter", "flags"],
        default_outcome=None,
    ),
}


@dataclass
class ProjectConfig:
    """Configuration for a project's journal."""

    # Project identification
    project_name: str = "unnamed"
    project_root: Path = field(default_factory=Path.cwd)

    # Directory structure (relative to project_root)
    # All directories under a/ for minimal footprint
    journal_dir: str = "a/journal"
    configs_dir: str = "a/configs"
    logs_dir: str = "a/logs"
    snapshots_dir: str = "a/snapshots"

    # What to track
    config_patterns: list[str] = field(default_factory=lambda: ["*.toml", "*.json", "*.yaml", "*.yml"])
    log_categories: list[str] = field(default_factory=list)
    version_commands: list[VersionCommand] = field(default_factory=list)

    # Optional build stages (empty = no stage concept)
    stages: list[str] = field(default_factory=list)

    # Custom metadata schema (additional fields for entries)
    custom_fields: dict[str, str] = field(default_factory=dict)  # name -> description

    # Templates (includes default templates unless overridden)
    templates: dict[str, EntryTemplateConfig] = field(default_factory=lambda: dict(DEFAULT_TEMPLATES))
    require_templates: bool = False  # If True, all entries must use a template

    # Hooks (populated from Python config)
    hooks: dict[str, Callable] = field(default_factory=dict)

    # Custom tools (populated from Python config)
    custom_tools: dict[str, Callable] = field(default_factory=dict)

    def get_journal_path(self) -> Path:
        return self.project_root / self.journal_dir

    def get_configs_path(self) -> Path:
        return self.project_root / self.configs_dir

    def get_logs_path(self) -> Path:
        return self.project_root / self.logs_dir

    def get_snapshots_path(self) -> Path:
        return self.project_root / self.snapshots_dir

    def get_template(self, name: str) -> Optional[EntryTemplateConfig]:
        """Get a template by name."""
        return self.templates.get(name)

    def list_templates(self) -> list[str]:
        """List available template names."""
        return list(self.templates.keys())


def load_toml_config(path: Path) -> dict[str, Any]:
    """Load configuration from TOML file."""
    if tomllib is None:
        raise ImportError("tomli required for TOML config: pip install tomli")
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_json_config(path: Path) -> dict[str, Any]:
    """Load configuration from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_python_config(path: Path) -> tuple[dict[str, Any], dict[str, Callable], dict[str, Callable]]:
    """Load configuration from Python file.

    Returns:
        Tuple of (config_dict, hooks_dict, custom_tools_dict)

    Convention:
        - CONFIG dict or config dict for static configuration
        - Functions named hook_* become hooks
        - Functions named custom_tool_* become MCP tools
    """
    spec = importlib.util.spec_from_file_location("journal_config", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Python config from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["journal_config"] = module
    spec.loader.exec_module(module)

    # Extract static config
    config_dict = {}
    if hasattr(module, "CONFIG"):
        config_dict = module.CONFIG
    elif hasattr(module, "config"):
        config_dict = module.config

    # Extract hooks
    hooks = {}
    for name in dir(module):
        if name.startswith("hook_"):
            hook_name = name[5:]  # Remove "hook_" prefix
            hooks[hook_name] = getattr(module, name)

    # Extract custom tools
    custom_tools = {}
    for name in dir(module):
        if name.startswith("custom_tool_"):
            tool_name = name[12:]  # Remove "custom_tool_" prefix
            custom_tools[tool_name] = getattr(module, name)

    return config_dict, hooks, custom_tools


def dict_to_config(data: dict[str, Any], project_root: Path) -> ProjectConfig:
    """Convert dictionary to ProjectConfig."""
    config = ProjectConfig(project_root=project_root)

    if "project" in data:
        proj = data["project"]
        if "name" in proj:
            config.project_name = proj["name"]

    if "directories" in data:
        dirs = data["directories"]
        if "journal" in dirs:
            config.journal_dir = dirs["journal"]
        if "configs" in dirs:
            config.configs_dir = dirs["configs"]
        if "logs" in dirs:
            config.logs_dir = dirs["logs"]
        if "snapshots" in dirs:
            config.snapshots_dir = dirs["snapshots"]

    if "tracking" in data:
        track = data["tracking"]
        if "config_patterns" in track:
            config.config_patterns = track["config_patterns"]
        if "log_categories" in track:
            config.log_categories = track["log_categories"]
        if "stages" in track:
            config.stages = track["stages"]

    if "versions" in data:
        for name, cmd_data in data["versions"].items():
            if isinstance(cmd_data, str):
                config.version_commands.append(VersionCommand(name=name, command=cmd_data))
            elif isinstance(cmd_data, dict):
                config.version_commands.append(VersionCommand(
                    name=name,
                    command=cmd_data.get("command", ""),
                    parse_regex=cmd_data.get("regex")
                ))

    if "custom_fields" in data:
        config.custom_fields = data["custom_fields"]

    # Parse templates (merge with defaults, user templates override defaults)
    if "templates" in data:
        templates_data = data["templates"]
        if "require" in templates_data:
            config.require_templates = templates_data["require"]
        for name, tmpl_data in templates_data.items():
            if name == "require":
                continue
            if isinstance(tmpl_data, dict):
                config.templates[name] = EntryTemplateConfig(
                    name=name,
                    description=tmpl_data.get("description", ""),
                    context=tmpl_data.get("context"),
                    intent=tmpl_data.get("intent"),
                    action=tmpl_data.get("action"),
                    observation=tmpl_data.get("observation"),
                    analysis=tmpl_data.get("analysis"),
                    next_steps=tmpl_data.get("next_steps"),
                    required_fields=tmpl_data.get("required_fields", []),
                    optional_fields=tmpl_data.get("optional_fields", []),
                    default_outcome=tmpl_data.get("default_outcome"),
                )

        # Allow disabling default templates by setting them to null/false in config
        if "disable_defaults" in templates_data and templates_data["disable_defaults"]:
            # Remove default templates
            for name in list(DEFAULT_TEMPLATES.keys()):
                if name not in templates_data:
                    config.templates.pop(name, None)

    return config


def find_config_file(project_root: Path) -> Optional[Path]:
    """Find configuration file in project root.

    Search order:
    1. journal_config.py (most flexible)
    2. journal_config.toml
    3. journal_config.json
    4. .journal.toml
    5. .journal.json
    """
    candidates = [
        "journal_config.py",
        "journal_config.toml",
        "journal_config.json",
        ".journal.toml",
        ".journal.json",
    ]

    for name in candidates:
        path = project_root / name
        if path.exists():
            return path

    return None


def load_config(project_root: Path, config_path: Optional[Path] = None) -> ProjectConfig:
    """Load project configuration.

    Args:
        project_root: Root directory of the project
        config_path: Optional explicit path to config file

    Returns:
        ProjectConfig instance
    """
    if config_path is None:
        config_path = find_config_file(project_root)

    if config_path is None:
        # No config file - use defaults
        return ProjectConfig(project_root=project_root)

    suffix = config_path.suffix.lower()

    if suffix == ".py":
        config_dict, hooks, custom_tools = load_python_config(config_path)
        config = dict_to_config(config_dict, project_root)
        config.hooks = hooks
        config.custom_tools = custom_tools
        return config

    elif suffix == ".toml":
        config_dict = load_toml_config(config_path)
        return dict_to_config(config_dict, project_root)

    elif suffix == ".json":
        config_dict = load_json_config(config_path)
        return dict_to_config(config_dict, project_root)

    else:
        raise ValueError(f"Unsupported config file type: {suffix}")
