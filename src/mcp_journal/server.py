"""MCP Journal Server - Main entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

# MCP imports are optional - only needed when running the server
try:
    from mcp.server import Server  # pragma: no cover
    from mcp.server.stdio import stdio_server  # pragma: no cover
    from mcp.types import Tool, TextContent  # pragma: no cover
    HAS_MCP = True  # pragma: no cover
except ImportError:
    HAS_MCP = False
    Server = None  # type: ignore
    Tool = None  # type: ignore
    TextContent = None  # type: ignore

from .config import ProjectConfig, load_config
from .engine import JournalEngine
from .tools import execute_tool, make_tools


def create_server(config: ProjectConfig) -> "Server":
    """Create and configure the MCP server.

    Args:
        config: Project configuration

    Returns:
        Configured MCP Server instance

    Raises:
        ImportError: If MCP package is not installed
    """
    if not HAS_MCP:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp-journal[mcp]"
        )

    server = Server("mcp-journal")
    engine = JournalEngine(config)
    tool_defs = make_tools(engine)

    # Add custom tools from Python config
    for tool_name, tool_func in config.custom_tools.items():
        # Custom tools should have a __doc__ string and type hints
        doc = tool_func.__doc__ or f"Custom tool: {tool_name}"

        # Try to extract schema from type hints or use generic
        tool_defs[tool_name] = {
            "name": tool_name,
            "description": doc.strip().split("\n")[0],  # First line of docstring
            "inputSchema": {
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "description": "Parameters for the custom tool",
                    }
                },
            },
        }

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of available tools."""
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in tool_defs.values()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool invocation."""

        # Check for custom tool first
        if name in config.custom_tools:
            try:
                result = config.custom_tools[name](engine, arguments.get("params", arguments))
                if asyncio.iscoroutine(result):
                    result = await result
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                error_result = {
                    "success": False,
                    "error": str(e),
                    "error_type": "custom_tool_error",
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

        # Execute built-in tool
        result = await execute_tool(engine, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    return server


async def run_server(config: ProjectConfig) -> None:
    """Run the MCP server with stdio transport."""
    if not HAS_MCP:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp-journal[mcp]"
        )

    server = create_server(config)  # pragma: no cover

    async with stdio_server() as (read_stream, write_stream):  # pragma: no cover
        await server.run(  # pragma: no cover
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def get_skills_source_dir() -> Path:
    """Get the directory containing bundled skill files."""
    return Path(__file__).parent / "skills"


def get_skills_target_dir() -> Path:
    """Get the Claude Code skills directory."""
    # Claude Code looks for skills in ~/.claude/skills/
    home = Path.home()
    return home / ".claude" / "skills"


def install_skills(force: bool = False) -> tuple[list[str], list[str]]:
    """Install mcp-journal skills to Claude Code skills directory.

    Args:
        force: Overwrite existing skills if True

    Returns:
        Tuple of (installed, skipped) skill names
    """
    source_dir = get_skills_source_dir()
    target_dir = get_skills_target_dir()

    if not source_dir.exists():
        raise FileNotFoundError(f"Skills source directory not found: {source_dir}")

    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    installed = []
    skipped = []

    for skill_file in source_dir.glob("*.md"):
        target_file = target_dir / skill_file.name

        if target_file.exists() and not force:
            skipped.append(skill_file.stem)
            continue

        shutil.copy2(skill_file, target_file)
        installed.append(skill_file.stem)

    return installed, skipped


def uninstall_skills() -> list[str]:
    """Remove mcp-journal skills from Claude Code skills directory.

    Returns:
        List of removed skill names
    """
    source_dir = get_skills_source_dir()
    target_dir = get_skills_target_dir()

    removed = []

    # Only remove skills that came from mcp-journal
    for skill_file in source_dir.glob("*.md"):
        target_file = target_dir / skill_file.name

        if target_file.exists():
            target_file.unlink()
            removed.append(skill_file.stem)

    return removed


def list_skills() -> list[dict[str, str]]:
    """List available mcp-journal skills.

    Returns:
        List of skill info dictionaries
    """
    source_dir = get_skills_source_dir()
    skills = []

    for skill_file in sorted(source_dir.glob("*.md")):
        # Read first line after the title for description
        content = skill_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Find first non-empty line after title
        description = ""
        for i, line in enumerate(lines):
            if i == 0:
                continue  # Skip title
            line = line.strip()
            if line and not line.startswith("#"):
                description = line
                break

        skills.append({
            "name": skill_file.stem,
            "file": skill_file.name,
            "description": description,
        })

    return skills


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Journal Server - Scientific lab journal discipline for software projects"
    )
    parser.add_argument(
        "--project-root",
        "-p",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Path to config file (default: auto-detect in project root)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize journal directories in project root",
    )

    # Skills management
    skills_group = parser.add_argument_group("skills", "Claude Code skills management")
    skills_group.add_argument(
        "--install-skills",
        action="store_true",
        help="Install mcp-journal skills to ~/.claude/skills/",
    )
    skills_group.add_argument(
        "--uninstall-skills",
        action="store_true",
        help="Remove mcp-journal skills from ~/.claude/skills/",
    )
    skills_group.add_argument(
        "--list-skills",
        action="store_true",
        help="List available mcp-journal skills",
    )
    skills_group.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing skills when installing",
    )

    args = parser.parse_args()

    # Handle skills commands first (they don't need project root)
    if args.list_skills:
        skills = list_skills()
        print("Available mcp-journal skills:")
        print()
        for skill in skills:
            print(f"  /{skill['name']}")
            print(f"      {skill['description']}")
        print()
        print(f"Install with: mcp-journal --install-skills")
        return

    if args.install_skills:
        try:
            installed, skipped = install_skills(force=args.force)
            target_dir = get_skills_target_dir()
            print(f"Skills directory: {target_dir}")
            print()
            if installed:
                print("Installed skills:")
                for name in installed:
                    print(f"  /{name}")
            if skipped:
                print()
                print("Skipped (already exist, use --force to overwrite):")
                for name in skipped:
                    print(f"  /{name}")
            if not installed and not skipped:
                print("No skills found to install.")
            print()
            print("Restart Claude Code to load the new skills.")
        except Exception as e:
            print(f"Error installing skills: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.uninstall_skills:
        removed = uninstall_skills()
        if removed:
            print("Removed skills:")
            for name in removed:
                print(f"  /{name}")
        else:
            print("No mcp-journal skills found to remove.")
        return

    project_root = args.project_root.resolve()

    if args.init:
        # Initialize journal structure
        config = ProjectConfig(project_root=project_root)
        engine = JournalEngine(config)
        print(f"Initialized journal directories in {project_root}")
        print(f"  - {config.journal_dir}/")
        print(f"  - {config.configs_dir}/")
        print(f"  - {config.logs_dir}/")
        print(f"  - {config.snapshots_dir}/")
        return

    # Check for MCP before loading config for server mode
    if not HAS_MCP:
        print("Error: MCP package not installed.", file=sys.stderr)
        print("Install with: pip install mcp-journal[mcp]", file=sys.stderr)
        print("Note: MCP requires Python 3.10+", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    try:
        config = load_config(project_root, args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Run server
    asyncio.run(run_server(config))


if __name__ == "__main__":  # pragma: no cover
    main()
