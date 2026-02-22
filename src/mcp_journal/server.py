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
from .session_journal_watcher import SessionJournalWatcher


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

    server = Server("mcp-journal")  # pragma: no cover
    engine = JournalEngine(config)  # pragma: no cover
    tool_defs = make_tools(engine)  # pragma: no cover

    # Add custom tools from Python config
    for tool_name, tool_func in config.custom_tools.items():  # pragma: no cover
        # Custom tools should have a __doc__ string and type hints
        doc = tool_func.__doc__ or f"Custom tool: {tool_name}"  # pragma: no cover

        # Try to extract schema from type hints or use generic
        tool_defs[tool_name] = {  # pragma: no cover
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

    @server.list_tools()  # pragma: no cover
    async def list_tools() -> list[Tool]:  # pragma: no cover
        """Return list of available tools."""
        return [  # pragma: no cover
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in tool_defs.values()
        ]

    @server.call_tool()  # pragma: no cover
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:  # pragma: no cover
        """Handle tool invocation."""

        # Check for custom tool first
        if name in config.custom_tools:  # pragma: no cover
            try:  # pragma: no cover
                result = config.custom_tools[name](engine, arguments.get("params", arguments))
                if asyncio.iscoroutine(result):  # pragma: no cover
                    result = await result  # pragma: no cover
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]  # pragma: no cover
            except Exception as e:  # pragma: no cover
                error_result = {  # pragma: no cover
                    "success": False,
                    "error": str(e),
                    "error_type": "custom_tool_error",
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]  # pragma: no cover

        # Execute built-in tool
        result = await execute_tool(engine, name, arguments)  # pragma: no cover
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]  # pragma: no cover

    return server  # pragma: no cover


async def run_server(config: ProjectConfig) -> None:
    """Run the MCP server with stdio transport."""
    if not HAS_MCP:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp-journal[mcp]"
        )

    server = create_server(config)  # pragma: no cover

    # Start the session journal watcher in background
    watcher = SessionJournalWatcher()  # pragma: no cover
    watcher.start()  # pragma: no cover

    try:  # pragma: no cover
        async with stdio_server() as (read_stream, write_stream):  # pragma: no cover
            await server.run(  # pragma: no cover
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:  # pragma: no cover
        watcher.stop()  # pragma: no cover


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


def run_cli_command(args, config: ProjectConfig) -> int:
    """Run a CLI command and return exit code."""
    engine = JournalEngine(config)

    if args.command == "query":
        # Build filters from CLI args
        filters = {}
        if args.tool:
            filters["tool"] = args.tool
        if args.outcome:
            filters["outcome"] = args.outcome
        if args.author:
            filters["author"] = args.author

        results = engine.journal_query(
            filters=filters if filters else None,
            text_search=args.text if hasattr(args, "text") and args.text else None,
            date_from=args.since,
            date_to=args.until,
            limit=args.limit,
            order_desc=not args.asc if hasattr(args, "asc") else True,
        )

        if args.format == "json":
            print(json.dumps(results, indent=2, default=str))
        else:
            for entry in results:
                print(f"[{entry.get('entry_id', 'unknown')}] {entry.get('timestamp', '')} - {entry.get('author', '')}")
                if entry.get("outcome"):
                    print(f"  Outcome: {entry['outcome']}")
                if entry.get("tool"):
                    print(f"  Tool: {entry['tool']}")
                if entry.get("context"):
                    preview = entry["context"][:100] + "..." if len(entry.get("context", "")) > 100 else entry.get("context", "")
                    print(f"  Context: {preview}")
                print()

        print(f"Found {len(results)} entries")
        return 0

    elif args.command == "search":
        results = engine.journal_query(
            text_search=args.query,
            date_from=args.since,
            date_to=args.until,
            limit=args.limit,
        )

        if args.format == "json":
            print(json.dumps(results, indent=2, default=str))
        else:
            for entry in results:
                print(f"[{entry.get('entry_id', 'unknown')}] {entry.get('timestamp', '')} - {entry.get('author', '')}")
                # Show which fields matched (simple highlight)
                for field in ["context", "intent", "action", "observation", "analysis"]:
                    content = entry.get(field, "")
                    if content and args.query.lower() in content.lower():
                        preview = content[:150] + "..." if len(content) > 150 else content
                        print(f"  {field}: {preview}")
                print()

        print(f"Found {len(results)} matching entries")
        return 0

    elif args.command == "stats":
        stats = engine.journal_stats(
            group_by=args.by,
            date_from=args.since,
            date_to=args.until,
        )

        if args.format == "json":
            print(json.dumps(stats, indent=2, default=str))
        else:
            if args.by:
                print(f"Statistics grouped by: {args.by}")
                print("-" * 40)
                for group in stats.get("groups", []):
                    key = group.get(args.by, "unknown")
                    count = group.get("count", 0)
                    print(f"  {key}: {count}")
                print("-" * 40)
                print(f"Total: {stats.get('totals', {}).get('count', 0)}")
            else:
                print("Journal Statistics")
                print("-" * 40)
                print(f"Total entries: {stats.get('total_entries', 0)}")
                print(f"Date range: {stats.get('date_range', {}).get('min')} to {stats.get('date_range', {}).get('max')}")
                if stats.get("by_type"):
                    print("\nBy type:")
                    for t, c in stats.get("by_type", {}).items():
                        print(f"  {t}: {c}")
                if stats.get("by_outcome"):
                    print("\nBy outcome:")
                    for o, c in stats.get("by_outcome", {}).items():
                        print(f"  {o}: {c}")
                if stats.get("top_tools"):
                    print("\nTop tools:")
                    for t, c in list(stats.get("top_tools", {}).items())[:5]:
                        print(f"  {t}: {c}")
        return 0

    elif args.command == "active":
        results = engine.journal_active(
            threshold_ms=args.threshold * 1000 if args.threshold else 30000,
            tool_filter=args.tool,
        )

        if args.format == "json":
            print(json.dumps(results, indent=2, default=str))
        else:
            if not results:
                print("No potentially active/hanging operations found.")
            else:
                print(f"Found {len(results)} potentially active/hanging operations:")
                print("-" * 60)
                for entry in results:
                    print(f"[{entry.get('entry_id', 'unknown')}] {entry.get('timestamp', '')}")
                    if entry.get("tool"):
                        print(f"  Tool: {entry['tool']}")
                    if entry.get("duration_ms"):
                        print(f"  Duration: {entry['duration_ms']}ms")
                    if entry.get("command"):
                        cmd = entry["command"][:80] + "..." if len(entry.get("command", "")) > 80 else entry.get("command", "")
                        print(f"  Command: {cmd}")
                    print()
        return 0

    elif args.command == "export":
        # Export entries to stdout
        results = engine.journal_query(
            date_from=args.since,
            date_to=args.until,
            limit=10000,  # High limit for export
        )

        if args.format == "json":
            print(json.dumps(results, indent=2, default=str))
        elif args.format == "csv":
            import csv
            import sys
            if results:
                writer = csv.DictWriter(sys.stdout, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        else:
            # Default to JSON
            print(json.dumps(results, indent=2, default=str))
        return 0

    elif args.command == "rebuild-index":
        print("Rebuilding SQLite index from markdown files...")
        stats = engine.rebuild_sqlite_index()
        print(f"Files processed: {stats.get('files_processed', 0)}")
        print(f"Entries indexed: {stats.get('entries_indexed', 0)}")
        if stats.get("errors", 0) > 0:
            print(f"Errors: {stats['errors']}")
        print("Done.")
        return 0

    return 1


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Journal Server - Scientific lab journal discipline for software projects"
    )

    # Global options
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

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="CLI commands")

    # query command
    query_parser = subparsers.add_parser("query", help="Query journal entries")
    query_parser.add_argument("--tool", help="Filter by tool name")
    query_parser.add_argument("--outcome", choices=["success", "failure", "partial"], help="Filter by outcome")
    query_parser.add_argument("--author", help="Filter by author")
    query_parser.add_argument("--since", help="Start date (YYYY-MM-DD or 'today')")
    query_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    query_parser.add_argument("--limit", type=int, default=50, help="Maximum results (default: 50)")
    query_parser.add_argument("--asc", action="store_true", help="Sort ascending (default: descending)")
    query_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # search command
    search_parser = subparsers.add_parser("search", help="Full-text search in entries")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--author", help="Filter by author")
    search_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    search_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    search_parser.add_argument("--limit", type=int, default=50, help="Maximum results")
    search_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show journal statistics")
    stats_parser.add_argument("--by", choices=["tool", "outcome", "author", "entry_type", "date"], help="Group by field")
    stats_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    stats_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    stats_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # active command
    active_parser = subparsers.add_parser("active", help="Find active/hanging operations")
    active_parser.add_argument("--threshold", type=int, default=30, help="Duration threshold in seconds (default: 30)")
    active_parser.add_argument("--tool", help="Filter by tool name")
    active_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # export command
    export_parser = subparsers.add_parser("export", help="Export entries")
    export_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    export_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format")

    # rebuild-index command
    subparsers.add_parser("rebuild-index", help="Rebuild SQLite index from markdown files")

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
        # Initialize journal structure - explicitly create all directories
        config = ProjectConfig(project_root=project_root)
        # Create all directories (engine only creates journal/ lazily now)
        config.get_journal_path().mkdir(parents=True, exist_ok=True)
        config.get_configs_path().mkdir(parents=True, exist_ok=True)
        config.get_logs_path().mkdir(parents=True, exist_ok=True)
        config.get_snapshots_path().mkdir(parents=True, exist_ok=True)
        print(f"Initialized journal directories in {project_root}")
        print(f"  - {config.journal_dir}/")
        print(f"  - {config.configs_dir}/")
        print(f"  - {config.logs_dir}/")
        print(f"  - {config.snapshots_dir}/")
        return

    # Handle CLI subcommands
    if args.command:
        try:
            config = load_config(project_root, args.config)
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(run_cli_command(args, config))

    # Check for MCP before loading config for server mode
    if not HAS_MCP:
        print("Error: MCP package not installed.", file=sys.stderr)
        print("Install with: pip install mcp-journal[mcp]", file=sys.stderr)
        print("Note: MCP requires Python 3.10+", file=sys.stderr)
        sys.exit(1)

    # Load configuration for server mode (requires MCP)
    try:  # pragma: no cover
        config = load_config(project_root, args.config)  # pragma: no cover
    except Exception as e:  # pragma: no cover
        print(f"Error loading config: {e}", file=sys.stderr)  # pragma: no cover
        sys.exit(1)  # pragma: no cover

    # Run server
    asyncio.run(run_server(config))  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    main()
