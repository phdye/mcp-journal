# Test Traceability Matrix - Query and Search Feature

**Project**: mcp-journal
**Version**: 0.2.0
**Feature**: SQLite Index with Query and Search Capabilities
**Date**: 2026-01-17
**Methodology**: Based on comprehensive-testing.md §4.2

---

## 1. Overview

This document maps each API function to its corresponding test cases, ensuring complete test coverage of the Query and Search feature.

### Coverage Summary

| Module | Statements | Branch | Coverage |
|--------|------------|--------|----------|
| index.py | 220 | 78 | 98% |
| engine.py (query methods) | ~60 | ~30 | 98% |
| tools.py (query tools) | 111 | 44 | 100% |
| models.py (diagnostic fields) | 188 | 54 | 100% |

---

## 2. JournalIndex Class (index.py)

### 2.1 Initialization

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `__init__` | test_index.py | `TestJournalIndexInit::test_creates_db_file`, `test_creates_schema` |
| `_init_schema` | test_index.py | `TestJournalIndexInit::test_creates_schema` |
| `_migrate_schema` | test_index_coverage.py | `TestSchemaVersionMigration::test_migrate_from_version_zero`, `test_migrate_from_old_version` |
| `close` | test_index.py | `TestIndexClose::test_close_connection` |

### 2.2 Entry Operations

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `index_entry` | test_index.py | `TestIndexEntry::test_index_entry_basic`, `test_index_entry_with_diagnostic_fields`, `test_index_amendment` |
| `index_entry_from_dict` | test_index.py | Via `rebuild_from_markdown` tests |
| `delete_entry` | test_index_coverage.py | `TestDeleteEntry::test_delete_existing_entry`, `test_delete_nonexistent_entry` |
| `get_entry` | test_index.py | `TestIndexEntry::test_index_entry_basic` |
| `get_entry` (None) | test_index_coverage.py | `TestGetEntry::test_get_nonexistent_entry_returns_none` |

### 2.3 Query Operations

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `query` (basic) | test_index.py | `TestQuery::test_query_all` |
| `query` (filters) | test_index.py | `TestQuery::test_query_with_filter`, `test_query_with_author_filter`, `test_query_with_tool_filter` |
| `query` (date range) | test_index.py | `TestQuery::test_query_with_date_range` |
| `query` (pagination) | test_index.py | `TestQuery::test_query_with_limit`, `test_query_with_offset` |
| `query` (ordering) | test_index.py | `TestQuery::test_query_order_desc`, `test_query_order_asc` |
| `query` (invalid filter) | test_index_coverage.py | `TestQueryEdgeCases::test_query_with_invalid_filter_field_ignored` |
| `query` (invalid order_by) | test_index_coverage.py | `TestQueryEdgeCases::test_query_with_invalid_order_by_defaults_to_timestamp` |
| `query` (None filter) | test_index_coverage.py | `TestQueryEdgeCases::test_query_filter_with_none_value_skipped` |

### 2.4 Text Search

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `query` (text_search) | test_index.py | `TestTextSearch::test_search_finds_content`, `test_search_across_fields`, `test_search_combined_with_filter` |
| `search_text` | test_index_coverage.py | `TestSearchText::test_search_text_delegates_to_query` |
| `_escape_fts_query` | test_index_coverage.py | `TestFTSQueryEscaping::test_fts_escapes_quotes`, `test_fts_phrase_with_spaces`, `test_fts_with_operators_not_quoted` |

### 2.5 Aggregation

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `aggregate` (by outcome) | test_index.py | `TestAggregate::test_aggregate_by_outcome` |
| `aggregate` (by author) | test_index.py | `TestAggregate::test_aggregate_by_author` |
| `aggregate` (by tool) | test_index.py | `TestAggregate::test_aggregate_by_tool` |
| `aggregate` (date filter) | test_index.py | `TestAggregate::test_aggregate_with_date_filter` |
| `aggregate` (invalid group_by) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_invalid_group_by_raises` |
| `aggregate` (avg aggregation) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_avg_aggregation` |
| `aggregate` (invalid func) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_invalid_func_ignored` |
| `aggregate` (invalid field) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_invalid_field_name_ignored` |
| `aggregate` (all invalid) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_all_invalid_aggregations_falls_back` |
| `aggregate` (with filters) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_filters` |
| `aggregate` (with date_to) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_date_range` |
| `aggregate` (None filter) | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_filter_containing_none_value` |

### 2.6 Active Operations

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `get_active_operations` | test_index.py | `TestActiveOperations::test_find_long_running`, `test_find_by_tool` |
| `get_active_operations` (no match) | test_index_coverage.py | `TestGetActiveOperations::test_get_active_no_matching_entries` |
| `get_active_operations` (missing outcome) | test_index_coverage.py | `TestGetActiveOperations::test_get_active_finds_missing_outcome` |

### 2.7 Index Rebuild

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `rebuild_from_markdown` | test_index.py | `TestRebuildIndex::test_rebuild_indexes_existing_entries` |
| `rebuild_from_markdown` (INDEX.md) | test_index_coverage.py | `TestRebuildFromMarkdown::test_rebuild_skips_index_md` |
| `rebuild_from_markdown` (callback) | test_index_coverage.py | `TestRebuildFromMarkdown::test_rebuild_with_progress_callback` |
| `rebuild_from_markdown` (errors) | test_index_coverage.py | `TestRebuildFromMarkdown::test_rebuild_handles_parse_errors` |

### 2.8 Statistics

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `get_stats` | test_index.py | `TestAggregate::test_overall_stats` |

### 2.9 Internal Functions

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `_row_to_dict` | All query tests | Implicit in all query operations |
| `_row_to_dict` (invalid JSON) | test_index_coverage.py | `TestRowToDict::test_row_to_dict_handles_invalid_json` |

---

## 3. JournalEngine Query Methods (engine.py)

| Function | Test File | Test Cases |
|----------|-----------|------------|
| `journal_query` | test_index.py | All `TestQuery::*` tests via engine fixture |
| `journal_stats` | test_index.py | All `TestAggregate::*` tests via engine fixture |
| `journal_active` | test_index.py | All `TestActiveOperations::*` tests via engine fixture |
| `rebuild_sqlite_index` | test_index.py | `TestRebuildIndex::test_rebuild_indexes_existing_entries` |

---

## 4. MCP Tools (tools.py)

| Tool | Test File | Test Cases |
|------|-----------|------------|
| `journal_query` | test_query.py | `TestJournalQueryTool::test_query_returns_results`, `test_query_with_filters`, `test_query_with_text_search`, `test_query_with_date_range`, `test_query_with_pagination`, `test_query_with_ordering` |
| `journal_stats` | test_query.py | `TestJournalStatsTool::test_stats_overall`, `test_stats_group_by_outcome`, `test_stats_group_by_author`, `test_stats_group_by_tool`, `test_stats_with_date_filter` |
| `journal_active` | test_query.py | `TestJournalActiveTool::test_active_finds_long_running`, `test_active_filter_by_tool` |
| `rebuild_sqlite_index` | test_query.py | `TestRebuildSqliteIndexTool::test_rebuild_returns_stats` |
| Tool schemas | test_query.py | `TestToolDefinitions::test_make_tools_includes_new_tools`, `test_journal_query_schema`, `test_journal_stats_schema`, `test_journal_active_schema` |

---

## 5. Diagnostic Fields (models.py, tools.py)

| Feature | Test File | Test Cases |
|---------|-----------|------------|
| Diagnostic fields in append | test_query.py | `TestDiagnosticFieldsInAppend::test_append_with_diagnostic_fields`, `test_append_with_error_type` |
| Diagnostic template | test_query.py | `TestDefaultTemplates::test_diagnostic_template_available` |
| Build template | test_query.py | `TestDefaultTemplates::test_build_template_available` |
| Test template | test_query.py | `TestDefaultTemplates::test_test_template_available` |

---

## 6. Property-Based Tests

| Property | Test File | Test Cases |
|----------|-----------|------------|
| Query ordering invariant | test_properties.py | `TestQueryProperties::test_query_results_always_sorted` |
| Pagination limit invariant | test_properties.py | `TestQueryProperties::test_query_pagination_never_exceeds_limit` |
| Pagination offset invariant | test_properties.py | `TestQueryProperties::test_query_pagination_with_offset` |
| Filter correctness | test_properties.py | `TestQueryProperties::test_filter_returns_only_matching_results` |
| Aggregate totals | test_properties.py | `TestQueryProperties::test_aggregate_group_totals_equal_total` |
| Text search finds content | test_properties.py | `TestTextSearchProperties::test_text_search_finds_indexed_content` |
| Text search with filter | test_properties.py | `TestTextSearchProperties::test_text_search_combined_with_filter` |
| Index consistency | test_properties.py | `TestIndexConsistencyProperties::test_all_appended_entries_are_queryable`, `test_index_and_markdown_entry_count_match` |

---

## 7. Error Path Tests

| Error Scenario | Test File | Test Cases |
|----------------|-----------|------------|
| Invalid group_by | test_index_coverage.py | `TestAggregateValidation::test_aggregate_invalid_group_by_raises` |
| Invalid aggregation function | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_invalid_func_ignored` |
| SQL injection via filter | test_index_coverage.py | `TestQueryEdgeCases::test_query_with_invalid_filter_field_ignored` |
| SQL injection via aggregate field | test_index_coverage.py | `TestAggregateValidation::test_aggregate_with_invalid_field_name_ignored` |
| Invalid JSON in database | test_index_coverage.py | `TestRowToDict::test_row_to_dict_handles_invalid_json` |
| Parse errors during rebuild | test_index_coverage.py | `TestRebuildFromMarkdown::test_rebuild_handles_parse_errors` |

---

## 8. Test File Summary

| Test File | Test Count | Purpose |
|-----------|------------|---------|
| test_index.py | 26 | Core JournalIndex functionality |
| test_index_coverage.py | 26 | Coverage gaps in index.py |
| test_query.py | 23 | MCP tool tests |
| test_properties.py | 22 | Property-based tests (9 for queries) |
| **Subtotal (Query Feature)** | **97** | |

---

## 9. Coverage Gap Exceptions

The following partial branches are documented exceptions:

### 9.1 index.py

| Line | Reason | Risk |
|------|--------|------|
| 61->exit | Schema version check early exit when no migration needed | None - normal path |
| 166->exit | _migrate_schema early return when already at version 1 | None - defensive code |
| 474->470 | Aggregate loop continue on invalid func | None - input validation |
| 533->537 | get_active_operations OR condition branch | Low - alternative matching |
| 692->695 | _row_to_dict rename refs branch | None - field rename |

All exceptions are defensive code paths or alternative matching conditions with no security or correctness risk.

---

## 10. Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| index.py 100% line coverage | ✅ 100% | 220/220 statements |
| index.py 98% branch coverage | ✅ 98% | 5 partial branches documented |
| tools.py 100% coverage | ✅ 100% | All query tools covered |
| models.py 100% coverage | ✅ 100% | Diagnostic fields covered |
| Property-based tests pass | ✅ Pass | 22 tests, 100+ examples each |
| Error paths tested | ✅ Pass | All error scenarios covered |
| SQL injection prevention verified | ✅ Pass | Field validation tests pass |

---

*Document generated following comprehensive-testing.md §4.2: Coverage Documentation Requirements*
