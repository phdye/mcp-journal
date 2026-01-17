# journal-start

Begin a journaled session with state capture and intent documentation.

## Usage

```
/journal-start [description of what you plan to work on]
```

## Instructions

When this skill is invoked:

1. First, call the `journal_help` MCP tool with no arguments to refresh your understanding of the journal system if you haven't already this session.

2. Call the `state_snapshot` MCP tool to capture the initial state:
   ```json
   {
     "name": "session-start",
     "include_configs": true,
     "include_env": true,
     "include_versions": true
   }
   ```

3. Call the `journal_append` MCP tool to document the session start:
   ```json
   {
     "author": "claude",
     "context": "[User's description or 'Starting new session']",
     "intent": "[What we plan to accomplish]",
     "outcome": "partial"
   }
   ```

4. Report to the user:
   - Confirm the snapshot was created
   - Confirm the journal entry was created with its ID
   - Remind them to use `/journal-end` when finishing

## Example

User: `/journal-start Implementing user authentication`

Claude actions:
1. Creates state snapshot "session-start"
2. Creates journal entry documenting intent to implement user authentication
3. Reports entry ID for future causality linking
