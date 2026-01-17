# journal-trace

Trace causality chains to understand what led to an entry or what it caused.

## Usage

```
/journal-trace <entry-id> [direction: backward|forward|both]
```

## Instructions

When this skill is invoked:

1. Call the `trace_causality` MCP tool:
   ```json
   {
     "entry_id": "[entry ID provided]",
     "direction": "[backward|forward|both, default: both]",
     "depth": 10
   }
   ```

2. Present the results as a readable causality chain:
   - For backward: Show what entries caused this one
   - For forward: Show what entries were caused by this one
   - For both: Show the full graph

3. Format the output to show the chain clearly, including:
   - Entry IDs
   - Timestamps
   - Brief context from each entry

## Example

User: `/journal-trace 2026-01-06-005 backward`

Claude actions:
1. Traces backward from entry 005
2. Presents:
   ```
   Causality chain (backward from 2026-01-06-005):

   2026-01-06-005: Fixed authentication bug
     caused by:
     2026-01-06-003: Discovered token expiration issue
       caused by:
       2026-01-06-001: Session start - investigating auth failures
   ```
