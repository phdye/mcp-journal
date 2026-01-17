# journal-log

Preserve a log file with outcome classification.

## Usage

```
/journal-log <path-to-log-file> <outcome: success|failure|interrupted>
```

## Instructions

When this skill is invoked:

1. Call the `log_preserve` MCP tool:
   ```json
   {
     "file_path": "[path provided by user]",
     "category": "[inferred from filename or 'general']",
     "outcome": "[success|failure|interrupted as specified]"
   }
   ```

   Infer category from common patterns:
   - `build*.log` -> "build"
   - `test*.log` -> "test"
   - `deploy*.log` -> "deploy"
   - Otherwise -> "general"

2. Report where the log was preserved.

3. Optionally create a journal entry linking to the preserved log if the outcome was significant (especially for failures).

## Example

User: `/journal-log build/output.log failure`

Claude actions:
1. Preserves log to `logs/output.2026-01-06.143000.failure.log`
2. Reports the preserved path
3. Creates journal entry documenting the build failure for traceability
