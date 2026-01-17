# journal-config

Archive a configuration file before modifying it.

## Usage

```
/journal-config <path-to-config-file> [reason for change]
```

## Instructions

When this skill is invoked:

1. Call the `config_archive` MCP tool:
   ```json
   {
     "file_path": "[path provided by user]",
     "reason": "[reason provided, or 'Pre-modification archive']"
   }
   ```

2. Report the result:
   - If successful: Show the archive path and confirm it's safe to edit
   - If duplicate: Inform user the config is already archived (no action needed)
   - If error: Report the error

3. After successful archive, you may proceed to edit the config file.

## Important

- ALWAYS use this skill before modifying any configuration file
- The archive includes a SHA-256 hash for integrity verification
- If the same content was already archived, you'll get a DuplicateContentError (this is safe to ignore)

## Example

User: `/journal-config pyproject.toml Adding new dependency`

Claude actions:
1. Archives pyproject.toml with reason "Adding new dependency"
2. Reports: "Archived to configs/pyproject.2026-01-06.143000.toml"
3. Proceeds to edit pyproject.toml
