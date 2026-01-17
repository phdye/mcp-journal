"""MCP tool definitions wrapping the journal engine."""

from __future__ import annotations

from typing import Any, Optional

from .engine import (
    AppendOnlyViolation,
    DuplicateContentError,
    InvalidReferenceError,
    JournalEngine,
    JournalError,
    TemplateNotFoundError,
    TemplateRequiredError,
)
from .models import format_timestamp


def make_tools(engine: JournalEngine) -> dict[str, dict]:
    """Create MCP tool definitions for the journal engine.

    Returns:
        Dict mapping tool names to their definitions.
    """

    tools = {}

    # ========== journal_append ==========
    tools["journal_append"] = {
        "name": "journal_append",
        "description": "Append a new entry to the daily journal. Never edits existing entries. Supports templates and causality tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author": {
                    "type": "string",
                    "description": "Who/what is making this entry",
                },
                "context": {
                    "type": "string",
                    "description": "Current state, what we're trying to accomplish",
                },
                "intent": {
                    "type": "string",
                    "description": "What action we're about to take and why",
                },
                "action": {
                    "type": "string",
                    "description": "Commands executed, files modified (after the fact)",
                },
                "observation": {
                    "type": "string",
                    "description": "What happened, output received",
                },
                "analysis": {
                    "type": "string",
                    "description": "What does this mean, what did we learn",
                },
                "next_steps": {
                    "type": "string",
                    "description": "What should happen next",
                },
                "references": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Cross-references to files or other entries",
                },
                "caused_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entry IDs that caused/led to this entry (causality tracking)",
                },
                "config_used": {
                    "type": "string",
                    "description": "Config archive path used for this operation",
                },
                "log_produced": {
                    "type": "string",
                    "description": "Log path produced by this operation",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["success", "failure", "partial"],
                    "description": "Outcome of the operation",
                },
                "template": {
                    "type": "string",
                    "description": "Template name to use for this entry",
                },
                "template_values": {
                    "type": "object",
                    "description": "Values to fill template placeholders",
                },
            },
            "required": ["author"],
        },
    }

    # ========== journal_amend ==========
    tools["journal_amend"] = {
        "name": "journal_amend",
        "description": "Add an amendment to a previous entry (does NOT edit the original).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "references_entry": {
                    "type": "string",
                    "description": "Entry ID being amended (e.g., 2026-01-06-003)",
                },
                "correction": {
                    "type": "string",
                    "description": "What was incorrect in the original entry",
                },
                "actual": {
                    "type": "string",
                    "description": "What is actually true",
                },
                "impact": {
                    "type": "string",
                    "description": "How this changes understanding",
                },
                "author": {
                    "type": "string",
                    "description": "Who is making this amendment",
                },
            },
            "required": ["references_entry", "correction", "actual", "impact", "author"],
        },
    }

    # ========== config_archive ==========
    tools["config_archive"] = {
        "name": "config_archive",
        "description": "Archive a configuration file before modification. Refuses if identical content already archived.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the config file to archive",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the file is being archived",
                },
                "stage": {
                    "type": "string",
                    "description": "Build stage (optional, e.g., 'stage1', 'analysis')",
                },
                "journal_entry": {
                    "type": "string",
                    "description": "Link to journal entry explaining the change",
                },
            },
            "required": ["file_path", "reason"],
        },
    }

    # ========== config_activate ==========
    tools["config_activate"] = {
        "name": "config_activate",
        "description": "Set an archived config as active. Archives current target first if it exists.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_path": {
                    "type": "string",
                    "description": "Path to the archived config to activate",
                },
                "target_path": {
                    "type": "string",
                    "description": "Where to place the active copy",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this config is being activated",
                },
                "journal_entry": {
                    "type": "string",
                    "description": "Required link to journal entry",
                },
            },
            "required": ["archive_path", "target_path", "reason", "journal_entry"],
        },
    }

    # ========== log_preserve ==========
    tools["log_preserve"] = {
        "name": "log_preserve",
        "description": "Preserve a log file by moving it with timestamp. Never deletes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the log file to preserve",
                },
                "category": {
                    "type": "string",
                    "description": "Log category (e.g., 'build', 'test', 'analysis')",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["success", "failure", "interrupted", "unknown"],
                    "description": "Outcome of the logged operation",
                },
            },
            "required": ["file_path"],
        },
    }

    # ========== state_snapshot ==========
    tools["state_snapshot"] = {
        "name": "state_snapshot",
        "description": "Capture complete state atomically including configs, environment, and tool versions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Snapshot name (e.g., 'pre-build', 'post-analysis')",
                },
                "include_configs": {
                    "type": "boolean",
                    "description": "Include config file contents",
                    "default": True,
                },
                "include_env": {
                    "type": "boolean",
                    "description": "Include environment variables",
                    "default": True,
                },
                "include_versions": {
                    "type": "boolean",
                    "description": "Include tool versions",
                    "default": True,
                },
                "include_build_dir_listing": {
                    "type": "boolean",
                    "description": "Include build directory file listing",
                    "default": False,
                },
                "build_dir": {
                    "type": "string",
                    "description": "Build directory to list (if include_build_dir_listing is True)",
                },
            },
            "required": ["name"],
        },
    }

    # ========== journal_search ==========
    tools["journal_search"] = {
        "name": "journal_search",
        "description": "Search journal entries by text, date range, author, or entry type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find in entries",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)",
                },
                "author": {
                    "type": "string",
                    "description": "Filter by author",
                },
                "entry_type": {
                    "type": "string",
                    "enum": ["entry", "amendment"],
                    "description": "Filter by entry type",
                },
            },
            "required": ["query"],
        },
    }

    # ========== index_rebuild ==========
    tools["index_rebuild"] = {
        "name": "index_rebuild",
        "description": "Rebuild INDEX.md from actual files (recovery tool).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "enum": ["configs", "logs", "snapshots"],
                    "description": "Which directory to rebuild index for",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview without writing",
                    "default": False,
                },
            },
            "required": ["directory"],
        },
    }

    # ========== journal_read ==========
    tools["journal_read"] = {
        "name": "journal_read",
        "description": "Read journal entries by ID or date range. Returns full entry content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {
                    "type": "string",
                    "description": "Specific entry ID (e.g., 2026-01-06-003)",
                },
                "date": {
                    "type": "string",
                    "description": "All entries for a specific date (YYYY-MM-DD)",
                },
                "date_from": {
                    "type": "string",
                    "description": "Range start date (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Range end date (YYYY-MM-DD)",
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include full content (default: true)",
                    "default": True,
                },
            },
        },
    }

    # ========== timeline ==========
    tools["timeline"] = {
        "name": "timeline",
        "description": "Get unified chronological view of all events (entries, configs, logs, snapshots).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)",
                },
                "event_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["entry", "amendment", "config", "log", "snapshot"],
                    },
                    "description": "Filter to specific event types",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum events to return",
                },
            },
        },
    }

    # ========== config_diff ==========
    tools["config_diff"] = {
        "name": "config_diff",
        "description": "Show diff between two config files. Use 'current:path' for active config.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path_a": {
                    "type": "string",
                    "description": "First config path (archive path or 'current:path/to/file')",
                },
                "path_b": {
                    "type": "string",
                    "description": "Second config path",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context around changes (default: 3)",
                    "default": 3,
                },
            },
            "required": ["path_a", "path_b"],
        },
    }

    # ========== session_handoff ==========
    tools["session_handoff"] = {
        "name": "session_handoff",
        "description": "Generate session summary for AI context transfer between sessions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Start of session (default: today)",
                },
                "date_to": {
                    "type": "string",
                    "description": "End of session (default: today)",
                },
                "include_configs": {
                    "type": "boolean",
                    "description": "Include config change summary",
                    "default": True,
                },
                "include_logs": {
                    "type": "boolean",
                    "description": "Include log outcome summary",
                    "default": True,
                },
                "format": {
                    "type": "string",
                    "enum": ["markdown", "json"],
                    "description": "Output format (default: markdown)",
                    "default": "markdown",
                },
            },
        },
    }

    # ========== trace_causality ==========
    tools["trace_causality"] = {
        "name": "trace_causality",
        "description": "Trace causality links from an entry to find causes and effects.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {
                    "type": "string",
                    "description": "Starting entry ID",
                },
                "direction": {
                    "type": "string",
                    "enum": ["forward", "backward", "both"],
                    "description": "Trace direction (default: both)",
                    "default": "both",
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth to trace (default: 10)",
                    "default": 10,
                },
            },
            "required": ["entry_id"],
        },
    }

    # ========== list_templates ==========
    tools["list_templates"] = {
        "name": "list_templates",
        "description": "List available entry templates for this project.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    }

    # ========== get_template ==========
    tools["get_template"] = {
        "name": "get_template",
        "description": "Get details of a specific template.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name",
                },
            },
            "required": ["name"],
        },
    }

    # ========== journal_help ==========
    tools["journal_help"] = {
        "name": "journal_help",
        "description": "Get documentation about the journal system, tools, and workflows. Call with no arguments for overview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "overview",
                        "principles",
                        "workflow",
                        "tools",
                        "causality",
                        "templates",
                        "errors",
                    ],
                    "description": "Documentation topic (default: overview)",
                },
                "tool": {
                    "type": "string",
                    "description": "Get detailed help for a specific tool (e.g., 'journal_append')",
                },
                "detail": {
                    "type": "string",
                    "enum": ["brief", "full", "examples"],
                    "description": "Level of detail (default: full)",
                },
            },
        },
    }

    return tools


async def execute_tool(engine: JournalEngine, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a journal tool and return the result.

    Args:
        engine: JournalEngine instance
        name: Tool name
        arguments: Tool arguments

    Returns:
        Result dict with success status and data or error
    """
    try:
        if name == "journal_append":
            entry = engine.journal_append(
                author=arguments["author"],
                context=arguments.get("context"),
                intent=arguments.get("intent"),
                action=arguments.get("action"),
                observation=arguments.get("observation"),
                analysis=arguments.get("analysis"),
                next_steps=arguments.get("next_steps"),
                references=arguments.get("references"),
                caused_by=arguments.get("caused_by"),
                config_used=arguments.get("config_used"),
                log_produced=arguments.get("log_produced"),
                outcome=arguments.get("outcome"),
                template=arguments.get("template"),
                template_values=arguments.get("template_values"),
            )
            return {
                "success": True,
                "entry_id": entry.entry_id,
                "timestamp": format_timestamp(entry.timestamp),
                "template": entry.template,
                "outcome": entry.outcome,
                "message": f"Entry {entry.entry_id} added to journal",
            }

        elif name == "journal_amend":
            entry = engine.journal_amend(
                references_entry=arguments["references_entry"],
                correction=arguments["correction"],
                actual=arguments["actual"],
                impact=arguments["impact"],
                author=arguments["author"],
            )
            return {
                "success": True,
                "entry_id": entry.entry_id,
                "amends": entry.references_entry,
                "message": f"Amendment {entry.entry_id} added",
            }

        elif name == "config_archive":
            record = engine.config_archive(
                file_path=arguments["file_path"],
                reason=arguments["reason"],
                stage=arguments.get("stage"),
                journal_entry=arguments.get("journal_entry"),
            )
            return {
                "success": True,
                "archive_path": record.archive_path,
                "content_hash": record.content_hash,
                "message": f"Archived to {record.archive_path}",
            }

        elif name == "config_activate":
            old = engine.config_activate(
                archive_path=arguments["archive_path"],
                target_path=arguments["target_path"],
                reason=arguments["reason"],
                journal_entry=arguments["journal_entry"],
            )
            result = {
                "success": True,
                "target_path": arguments["target_path"],
                "message": f"Activated {arguments['archive_path']} as {arguments['target_path']}",
            }
            if old:
                result["previous_archive"] = old.archive_path
            return result

        elif name == "log_preserve":
            record = engine.log_preserve(
                file_path=arguments["file_path"],
                category=arguments.get("category"),
                outcome=arguments.get("outcome"),
            )
            return {
                "success": True,
                "preserved_path": record.preserved_path,
                "message": f"Log preserved to {record.preserved_path}",
            }

        elif name == "state_snapshot":
            snapshot = engine.state_snapshot(
                name=arguments["name"],
                include_configs=arguments.get("include_configs", True),
                include_env=arguments.get("include_env", True),
                include_versions=arguments.get("include_versions", True),
                include_build_dir_listing=arguments.get("include_build_dir_listing", False),
                build_dir=arguments.get("build_dir"),
            )
            return {
                "success": True,
                "snapshot_path": snapshot.snapshot_path,
                "timestamp": format_timestamp(snapshot.timestamp),
                "message": f"Snapshot saved to {snapshot.snapshot_path}",
            }

        elif name == "journal_search":
            results = engine.journal_search(
                query=arguments["query"],
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                author=arguments.get("author"),
                entry_type=arguments.get("entry_type"),
            )
            return {
                "success": True,
                "count": len(results),
                "results": results,
            }

        elif name == "index_rebuild":
            result = engine.index_rebuild(
                directory=arguments["directory"],
                dry_run=arguments.get("dry_run", False),
            )
            return {
                "success": True,
                **result,
            }

        elif name == "journal_read":
            entries = engine.journal_read(
                entry_id=arguments.get("entry_id"),
                date=arguments.get("date"),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                include_content=arguments.get("include_content", True),
            )
            return {
                "success": True,
                "count": len(entries),
                "entries": entries,
            }

        elif name == "timeline":
            events = engine.timeline(
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                event_types=arguments.get("event_types"),
                limit=arguments.get("limit"),
            )
            return {
                "success": True,
                "count": len(events),
                "events": events,  # Already dicts from engine
            }

        elif name == "config_diff":
            diff = engine.config_diff(
                path_a=arguments["path_a"],
                path_b=arguments["path_b"],
                context_lines=arguments.get("context_lines", 3),
            )
            return {
                "success": True,
                **diff,  # Spread the diff dict (includes identical, additions, deletions, diff_text)
            }

        elif name == "session_handoff":
            handoff = engine.session_handoff(
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                include_configs=arguments.get("include_configs", True),
                include_logs=arguments.get("include_logs", True),
                format=arguments.get("format", "markdown"),
            )
            return {
                "success": True,
                **handoff,  # Spread handoff dict (includes format, content)
            }

        elif name == "trace_causality":
            graph = engine.trace_causality(
                entry_id=arguments["entry_id"],
                direction=arguments.get("direction", "both"),
                depth=arguments.get("depth", 10),
            )
            return {
                "success": True,
                "entry_id": arguments["entry_id"],
                "direction": arguments.get("direction", "both"),
                **graph,
            }

        elif name == "list_templates":
            templates = engine.list_templates()
            return {
                "success": True,
                "templates": templates,
                "require_templates": engine.config.require_templates,
            }

        elif name == "get_template":
            template = engine.get_template(arguments["name"])
            if template is None:
                return {
                    "success": False,
                    "error": f"Template not found: {arguments['name']}",
                    "error_type": "template_not_found",
                }
            return {
                "success": True,
                "template": template,
            }

        elif name == "journal_help":
            result = engine.journal_help(
                topic=arguments.get("topic"),
                tool=arguments.get("tool"),
                detail=arguments.get("detail", "full"),
            )
            return {
                "success": result.get("type") != "error",
                **result,
            }

        else:
            return {
                "success": False,
                "error": f"Unknown tool: {name}",
            }

    except DuplicateContentError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "duplicate_content",
            "suggestion": "Content already archived - no action needed",
        }

    except InvalidReferenceError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "invalid_reference",
            "suggestion": "Check that the referenced entry or file exists",
        }

    except AppendOnlyViolation as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "append_only_violation",
            "suggestion": "Use journal_amend to correct entries instead of editing",
        }

    except TemplateRequiredError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "template_required",
            "suggestion": "This project requires templates. Use list_templates to see available templates.",
        }

    except TemplateNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "template_not_found",
            "suggestion": "Use list_templates to see available templates.",
        }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "file_not_found",
        }

    except JournalError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "journal_error",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }
