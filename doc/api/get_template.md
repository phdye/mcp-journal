# get_template(3) - Get Template Details

## NAME

**get_template** - Get detailed information about a specific template

## SYNOPSIS

```
get_template(
    name: str
) -> dict
```

## DESCRIPTION

The **get_template** tool returns detailed information about a specific entry template, including its required and optional fields, field descriptions, and example usage.

This is useful for AI agents to understand exactly what information is needed for a particular type of entry.

## PARAMETERS

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Template name |

## RETURN VALUE

```json
{
  "name": "diagnostic",
  "description": "Tool call diagnostic entry for recording command execution",
  "required_fields": ["tool", "outcome"],
  "optional_fields": [
    "command",
    "duration_ms",
    "exit_code",
    "error_type",
    "context",
    "observation"
  ],
  "field_descriptions": {
    "tool": "Tool/command name (e.g., 'bash', 'read_file')",
    "outcome": "Result: 'success', 'failure', or 'partial'",
    "command": "The actual command that was executed",
    "duration_ms": "Execution time in milliseconds",
    "exit_code": "Command exit code (0 = success)",
    "error_type": "Type of error if failed (e.g., 'timeout', 'permission')",
    "context": "What was being attempted",
    "observation": "What happened, output received"
  },
  "example": {
    "author": "claude",
    "template": "diagnostic",
    "tool": "bash",
    "command": "make -j12",
    "context": "Building release version",
    "duration_ms": 45000,
    "exit_code": 0,
    "outcome": "success",
    "observation": "Build completed with 0 errors, 3 warnings"
  }
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | Template name is empty |
| `TemplateNotFoundError` | Template with given name not found |

## EXAMPLES

### Get Diagnostic Template

```json
{
  "name": "diagnostic"
}
```

### Get Build Template

```json
{
  "name": "build"
}
```

### Get Custom Template

```json
{
  "name": "deploy"
}
```

## NOTES

### Default Templates

**diagnostic**:
- Purpose: Record tool/command execution
- Required: `tool`, `outcome`
- Key fields: `command`, `duration_ms`, `exit_code`

**build**:
- Purpose: Document build processes
- Required: `context`, `outcome`
- Key fields: `duration_ms`, `observation`

**test**:
- Purpose: Record test execution
- Required: `context`, `outcome`
- Key fields: `action`, `observation`

### Field Descriptions

Each template includes descriptions for all fields:

```json
{
  "field_descriptions": {
    "tool": "Tool/command name (e.g., 'bash', 'read_file')",
    "outcome": "Result: 'success', 'failure', or 'partial'"
  }
}
```

Use these descriptions to understand what information to provide.

### Example Usage

The template includes an example of proper usage:

```json
{
  "example": {
    "author": "claude",
    "template": "diagnostic",
    "tool": "bash",
    "command": "pytest tests/",
    "outcome": "success"
  }
}
```

### Creating Entries with Templates

1. Get template details:
   ```json
   {"name": "diagnostic"}
   ```

2. Note required fields: `tool`, `outcome`

3. Create entry with required + optional fields:
   ```json
   {
     "author": "claude",
     "template": "diagnostic",
     "tool": "bash",
     "command": "make build",
     "outcome": "success",
     "duration_ms": 45000
   }
   ```

### Custom Template Details

Custom templates defined in configuration are returned with the same structure:

```toml
[templates.deploy]
description = "Deployment entry"
required_fields = ["context", "outcome"]
optional_fields = ["intent", "action"]

[templates.deploy.field_descriptions]
context = "What is being deployed"
outcome = "Deployment result"
```

Returns:
```json
{
  "name": "deploy",
  "description": "Deployment entry",
  "required_fields": ["context", "outcome"],
  "optional_fields": ["intent", "action"],
  "field_descriptions": {
    "context": "What is being deployed",
    "outcome": "Deployment result"
  }
}
```

### AI Agent Pattern

```python
# 1. Discover templates
templates = list_templates()

# 2. Find appropriate template
for t in templates["templates"]:
    if "diagnostic" in t["description"].lower():
        template_name = t["name"]
        break

# 3. Get details
details = get_template(template_name)

# 4. Create entry with all required fields
entry = journal_append(
    author="claude",
    template=template_name,
    **{field: value for field in details["required_fields"]}
)
```

## SEE ALSO

- [list_templates(3)](list_templates.md) - List all templates
- [journal_append(3)](journal_append.md) - Create entries
- [Configuration](../configuration.md) - Define templates
