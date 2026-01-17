# MCP Flexible Help Model

This document describes the design of a self-documenting help system for MCP servers, enabling AI clients to educate themselves about server capabilities, workflows, and best practices.

## Problem Statement

MCP servers expose tools via `list_tools()` with names, descriptions, and input schemas. However, this provides only **what** tools exist, not:

- **Why** the system exists (principles, philosophy)
- **How** to use tools effectively (workflows, patterns)
- **When** to use each tool (decision guidance)
- **Examples** of correct usage

An AI connecting to an MCP server can discover tools but cannot learn to use the system effectively without external documentation.

## Solution: `journal_help` Tool

A dedicated help tool that provides hierarchical, queryable documentation.

### Tool Definition

```python
tools["journal_help"] = {
    "name": "journal_help",
    "description": "Get documentation about the journal system, tools, and workflows.",
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
                    "errors"
                ],
                "description": "Documentation topic (default: overview)"
            },
            "tool": {
                "type": "string",
                "description": "Get detailed help for a specific tool (e.g., 'journal_append')"
            },
            "detail": {
                "type": "string",
                "enum": ["brief", "full", "examples"],
                "description": "Level of detail (default: full)"
            }
        }
    }
}
```

### Design Principles

1. **Domain-prefixed naming** (`journal_help`) - Follows existing tool naming convention
2. **Topic hierarchy** - Broad categories for navigation
3. **Tool-specific help** - Deep dive on any tool with usage examples
4. **Detail levels** - Adapts to context (quick lookup vs. learning)

## Topic Hierarchy

### `overview` (default)

High-level introduction to the journal system:

```
MCP Journal Server enforces scientific lab journal discipline for software projects.

Core principle: Append-only, timestamped, attributed, complete, reproducible.

Every action is recorded. Nothing is deleted. Full traceability from cause to effect.

Directory structure:
- journal/   - Daily markdown entries (YYYY-MM-DD.md)
- configs/   - Archived configurations with INDEX.md
- logs/      - Preserved logs with INDEX.md
- snapshots/ - State captures (JSON) with INDEX.md

Use `journal_help(topic="workflow")` for recommended usage patterns.
Use `journal_help(topic="tools")` for tool reference.
```

### `principles`

The five core principles with rationale:

1. **Append-Only** - Never delete, edit, or overwrite existing content
2. **Timestamped** - Every action has a precise UTC timestamp
3. **Attributed** - Every entry has an author
4. **Complete** - Capture full context, not just changes
5. **Reproducible** - Archive everything needed to reproduce state

### `workflow`

Recommended usage patterns:

```
Typical Session Workflow:
1. state_snapshot(name="session-start") - Capture initial state
2. journal_append(...) - Document intent before making changes
3. config_archive(...) - Archive configs before modification
4. [make changes]
5. log_preserve(...) - Preserve any logs produced
6. journal_append(..., caused_by=[...]) - Document results with causality
7. session_handoff(...) - Generate summary for next session

Error Recovery:
1. journal_amend(...) - Correct previous entries (never edit)
2. index_rebuild(...) - Recover corrupted INDEX.md files
```

### `tools`

Brief reference of all tools with one-line descriptions.

### `causality`

Explanation of causality tracking:

```
Causality Tracking:
- Use `caused_by` parameter to link entries
- Entry IDs: YYYY-MM-DD-NNN (e.g., 2026-01-06-003)
- trace_causality() traverses the graph forward/backward
- Enables "why did this happen?" analysis
```

### `templates`

Template system documentation:

```
Templates ensure consistent entry formats.
- list_templates() - See available templates
- get_template(name) - Get template details
- journal_append(template="...", template_values={...}) - Use template

Templates can be required via config: require_templates = true
```

### `errors`

Error handling guide:

```
Common Errors:
- DuplicateContentError: Config already archived (safe to ignore)
- InvalidReferenceError: Referenced entry/file doesn't exist
- AppendOnlyViolation: Attempted to edit existing content
- TemplateRequiredError: Template required but not provided

Recovery:
- Use journal_amend() to correct entries
- Use index_rebuild() to fix corrupted indexes
```

## Detail Levels

### `brief`

Single paragraph or bullet points. For quick reference during active work.

### `full` (default)

Complete documentation with explanations. For learning and understanding.

### `examples`

Concrete usage examples with sample calls and responses:

```json
// Example: journal_append with causality
{
    "author": "claude",
    "context": "Fixed authentication bug discovered in entry 2026-01-06-001",
    "action": "Modified auth.py to handle token expiration",
    "outcome": "success",
    "caused_by": ["2026-01-06-001"]
}

// Response:
{
    "success": true,
    "entry_id": "2026-01-06-003",
    "timestamp": "2026-01-06T14:30:00Z",
    "message": "Entry 2026-01-06-003 added to journal"
}
```

## Tool-Specific Help

When `tool` parameter is provided, returns detailed documentation for that specific tool:

```
journal_help(tool="config_archive")
```

Returns:
- Full description
- All parameters with types and descriptions
- Required vs optional parameters
- Usage examples
- Common errors and how to handle them
- Related tools

## Implementation Notes

### Content Storage

Help content can be:

1. **Embedded in code** - Simple, versioned with code
2. **External markdown files** - Easier to update, can be user-customized
3. **Hybrid** - Core docs embedded, extended docs in files

Recommended: Embed core content, allow `help_extensions_dir` config option.

### Response Format

Returns structured data that can be rendered appropriately:

```python
{
    "success": True,
    "topic": "workflow",
    "detail": "full",
    "content": "...",  # Markdown formatted
    "related_topics": ["tools", "causality"],
    "related_tools": ["journal_append", "state_snapshot"]
}
```

### Caching

Help content is static per server version. Clients may cache responses.

## Naming Conventions Observed

| Pattern | Example | Notes |
|---------|---------|-------|
| `get_help` | RBO MCP server | Generic, verb-prefixed |
| `<domain>_help` | `journal_help` | Domain-scoped, consistent with other tools |
| `describe` | Various | More formal, inspection-focused |
| `info` | Various | Typically for runtime state, not docs |

**Recommendation**: Use `journal_help` to match existing tool naming pattern (`journal_append`, `journal_search`, etc.).

## References

- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/)
- [MCP Servers Repository](https://github.com/modelcontextprotocol/servers)
