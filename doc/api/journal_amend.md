# journal_amend(3) - Add Amendment to Entry

## NAME

**journal_amend** - Add an amendment to a previous journal entry

## SYNOPSIS

```
journal_amend(
    references_entry: str,
    correction: str,
    actual: str,
    impact: str,
    author: str
) -> dict
```

## DESCRIPTION

The **journal_amend** tool adds an amendment that references and corrects a previous journal entry. Amendments are a core principle of the journal system - rather than editing or deleting entries, corrections are recorded as new entries that link to the original.

This preserves the complete history of observations and corrections, essential for scientific reproducibility and understanding how conclusions evolved.

The amendment is written as a new entry with `entry_type: amendment` and a reference to the original entry via `references_entry`.

## PARAMETERS

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `references_entry` | string | Entry ID being amended (e.g., "2026-01-17-001") |
| `correction` | string | What was incorrect in the original entry |
| `actual` | string | What is actually true |
| `impact` | string | How this changes understanding |
| `author` | string | Who is making this amendment |

## RETURN VALUE

Returns a dictionary with the created amendment details:

```json
{
  "status": "success",
  "entry_id": "2026-01-17-002",
  "entry_type": "amendment",
  "references_entry": "2026-01-17-001",
  "timestamp": "2026-01-17T15:00:00+00:00",
  "file_path": "journal/2026-01-17.md"
}
```

## ERRORS

| Error | Cause |
|-------|-------|
| `ValueError` | references_entry is empty or invalid format |
| `ValueError` | correction, actual, or impact is empty |
| `ValueError` | author is empty |
| `EntryNotFoundError` | Referenced entry does not exist |
| `IOError` | Cannot write to journal file |

## EXAMPLES

### Basic Amendment

```json
{
  "references_entry": "2026-01-17-001",
  "correction": "Stated build time was 30 seconds",
  "actual": "Build time was actually 45 seconds (misread output)",
  "impact": "Performance baseline needs adjustment",
  "author": "claude"
}
```

### Correcting Analysis

```json
{
  "references_entry": "2026-01-17-005",
  "correction": "Analysis concluded timeout was due to network issues",
  "actual": "Root cause was actually a deadlock in the connection pool",
  "impact": "Investigation should focus on threading, not network config",
  "author": "claude"
}
```

### Correcting Observation

```json
{
  "references_entry": "2026-01-16-012",
  "correction": "Reported test count as 352 passing",
  "actual": "Actual count was 352 passing, 5 skipped (skipped tests not mentioned)",
  "impact": "Need to investigate why 5 tests are being skipped",
  "author": "claude"
}
```

## NOTES

### Entry Format

Amendments are written with a special format:

```markdown
## 2026-01-17-002

**Timestamp**: 2026-01-17T15:00:00+00:00
**Author**: claude
**Type**: Amendment
**References**: 2026-01-17-001

### Correction
Stated build time was 30 seconds

### Actual
Build time was actually 45 seconds (misread output)

### Impact
Performance baseline needs adjustment

---
```

### When to Amend

Use amendments for:
- Factual errors in observations
- Incorrect analysis or conclusions
- Missing information that changes understanding
- Clarifications that affect interpretation

Do NOT use amendments for:
- Adding follow-up information (use regular entry with `caused_by`)
- Recording new observations (use regular entry)
- Style or formatting corrections (not needed)

### Amendment vs New Entry

| Situation | Use |
|-----------|-----|
| Previous entry was wrong | `journal_amend` |
| New information builds on previous | `journal_append` with `caused_by` |
| Continuing work from previous | `journal_append` with `references` |

### Querying Amendments

Amendments can be found with:
```json
{
  "filters": {"entry_type": "amendment"}
}
```

Or find all amendments to a specific entry:
```json
{
  "text_search": "References: 2026-01-17-001"
}
```

## SEE ALSO

- [journal_append(3)](journal_append.md) - Create regular entry
- [journal_read(3)](journal_read.md) - Read entries
- [journal_query(3)](journal_query.md) - Query entries
- [trace_causality(3)](trace_causality.md) - Trace entry relationships
