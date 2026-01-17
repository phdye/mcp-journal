# journal-checkpoint

Create a quick journal entry documenting current progress.

## Usage

```
/journal-checkpoint <what just happened or was discovered>
```

## Instructions

When this skill is invoked:

1. Call the `journal_append` MCP tool with the user's description:
   ```json
   {
     "author": "claude",
     "context": "[Current state/what we're working on]",
     "action": "[What was just done]",
     "observation": "[What was discovered or resulted]",
     "outcome": "partial"
   }
   ```

   If there are relevant previous entry IDs from this session, include them in `caused_by` to maintain causality.

2. Briefly confirm the entry was created and show the entry ID.

## When to Use

- After discovering something important
- After completing a significant step
- Before taking a different approach
- When hitting a blocker or error
- To document a decision and its rationale

## Example

User: `/journal-checkpoint Found the bug - race condition in token refresh`

Claude actions:
1. Creates journal entry documenting the discovery
2. Reports entry ID: "2026-01-06-005"
3. Continues with the work
