# list_templates(3) - List Available Templates

## NAME

**list_templates** - List available entry templates

## SYNOPSIS

```
list_templates() -> dict
```

## DESCRIPTION

The **list_templates** tool returns a list of all available entry templates. Templates provide structured formats for journal entries, ensuring consistent information capture for specific use cases.

Templates include both built-in defaults and any custom templates defined in the project configuration.

## PARAMETERS

None.

## RETURN VALUE

```json
{
  "count": 5,
  "templates": [
    {
      "name": "diagnostic",
      "description": "Tool call diagnostic entry",
      "required_fields": ["tool", "outcome"],
      "optional_fields": ["command", "duration_ms", "exit_code", "error_type", "context", "observation"]
    },
    {
      "name": "build",
      "description": "Build process entry",
      "required_fields": ["context", "outcome"],
      "optional_fields": ["intent", "action", "observation", "analysis", "duration_ms"]
    },
    {
      "name": "test",
      "description": "Test execution entry",
      "required_fields": ["context", "outcome"],
      "optional_fields": ["action", "observation", "analysis", "duration_ms"]
    },
    {
      "name": "investigation",
      "description": "Problem investigation entry",
      "required_fields": ["context"],
      "optional_fields": ["observation", "analysis", "next_steps"]
    },
    {
      "name": "decision",
      "description": "Decision documentation",
      "required_fields": ["context", "analysis"],
      "optional_fields": ["intent", "observation", "next_steps", "outcome"]
    }
  ]
}
```

## ERRORS

This tool does not produce errors under normal operation.

## EXAMPLES

### List All Templates

```json
{}
```

## NOTES

### Built-in Templates

The system includes default templates:

**diagnostic**: For recording tool calls
```json
{
  "template": "diagnostic",
  "tool": "bash",
  "command": "make build",
  "duration_ms": 45000,
  "exit_code": 0,
  "outcome": "success"
}
```

**build**: For build process entries
```json
{
  "template": "build",
  "context": "Building release version",
  "outcome": "success",
  "duration_ms": 180000
}
```

**test**: For test execution
```json
{
  "template": "test",
  "context": "Running full test suite",
  "action": "pytest tests/ -v",
  "outcome": "success",
  "observation": "352 passed, 5 skipped"
}
```

### Custom Templates

Define custom templates in configuration:

**TOML**:
```toml
[templates.deploy]
description = "Deployment entry"
required_fields = ["context", "outcome"]
optional_fields = ["intent", "action", "observation"]

[templates.deploy.field_descriptions]
context = "What is being deployed and to where"
outcome = "Deployment result"
```

**Python**:
```python
from mcp_journal.config import EntryTemplateConfig

TEMPLATES = {
    "deploy": EntryTemplateConfig(
        name="deploy",
        description="Deployment entry",
        required_fields=["context", "outcome"],
        optional_fields=["intent", "action", "observation"],
        field_descriptions={
            "context": "What is being deployed and to where",
            "outcome": "Deployment result"
        }
    )
}
```

### Using Templates

When creating entries with templates:

1. **Specify template**:
   ```json
   {"template": "diagnostic", "author": "claude", ...}
   ```

2. **Include required fields** - Entry creation fails if missing

3. **Add optional fields** as needed

### Template Validation

Templates are validated at:
- Entry creation time (required fields checked)
- Configuration load time (template structure validated)

### Discovery Pattern

For AI agents:

```
1. list_templates()           # See available templates
2. get_template("diagnostic") # Get details of one template
3. journal_append(template="diagnostic", ...)  # Use template
```

## SEE ALSO

- [get_template(3)](get_template.md) - Get template details
- [journal_append(3)](journal_append.md) - Create entries with templates
- [Configuration](../configuration.md) - Define custom templates
