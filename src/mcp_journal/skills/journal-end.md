# journal-end

End a journaled session with summary and handoff generation.

## Usage

```
/journal-end [optional summary of what was accomplished]
```

## Instructions

When this skill is invoked:

1. Call the `journal_append` MCP tool to document the session end:
   ```json
   {
     "author": "claude",
     "context": "Ending session",
     "action": "[Summary of what was done during the session]",
     "observation": "[Key outcomes and results]",
     "analysis": "[What was learned or decided]",
     "next_steps": "[Recommended follow-up actions]",
     "outcome": "success"
   }
   ```

   If you have the entry ID from `/journal-start`, include it in `caused_by`.

2. Call the `session_handoff` MCP tool to generate a handoff summary:
   ```json
   {
     "include_configs": true,
     "include_logs": true,
     "format": "markdown"
   }
   ```

3. Present the handoff summary to the user so they can:
   - Save it for the next session
   - Review what was accomplished
   - See pending items

## Example

User: `/journal-end Completed auth module, tests passing`

Claude actions:
1. Creates final journal entry with session summary
2. Generates session handoff with config changes and log outcomes
3. Presents the handoff markdown to the user
