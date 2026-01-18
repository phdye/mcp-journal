# Architecture

**Version**: 0.2.0
**Last Updated**: 2026-01-17

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [System Architecture](#system-architecture)
4. [Component Architecture](#component-architecture)
5. [Data Architecture](#data-architecture)
6. [Communication Flow](#communication-flow)
7. [Concurrency Model](#concurrency-model)
8. [Extension Points](#extension-points)
9. [Security Considerations](#security-considerations)
10. [Performance Characteristics](#performance-characteristics)

---

## Overview

MCP Journal Server is a Model Context Protocol (MCP) server that provides scientific lab journal discipline for software development and data analysis projects. It operates on the fundamental principle that all recorded data is immutable and append-only.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client                                │
│            (Claude Code, IDE Plugin, Custom Client)              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ MCP Protocol (JSON-RPC over stdio)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Journal Server                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Server    │  │    Tools    │  │        Engine           │  │
│  │  (server.py)│→│  (tools.py) │→│      (engine.py)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                                      │                 │
│  ┌──────┴──────┐                    ┌─────────┴─────────┐       │
│  │   Config    │                    │      Index        │       │
│  │ (config.py) │                    │    (index.py)     │       │
│  └─────────────┘                    └───────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ File System Operations
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       Project Directory                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐   │
│  │  journal/ │ │  configs/ │ │   logs/   │ │   snapshots/  │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────┘   │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │ journal/.index.db │                        │
│                    │  (SQLite Index)   │                        │
│                    └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Append-Only Immutability

**Principle**: Once written, data is never modified or deleted.

**Rationale**: Scientific reproducibility requires that all observations, decisions, and actions are preserved exactly as they occurred. Amendments and corrections reference original entries rather than overwriting them.

**Implementation**:
- Journal entries are appended to daily markdown files
- Config archives are timestamped copies, never overwrites
- Log preservation moves files with timestamps
- Amendments link to original entries via `references_entry`

### 2. Source of Truth: Markdown Files

**Principle**: Human-readable markdown files are the authoritative data source.

**Rationale**: Data must remain accessible without specialized tools. Plain text survives better than databases across time and system migrations.

**Implementation**:
- All journal entries stored in `journal/YYYY-MM-DD.md`
- SQLite index is a derived cache that can be rebuilt
- INDEX.md files provide human-navigable directories
- Standard text editors can read all data

### 3. Complete Attribution

**Principle**: Every entry must have a timestamp and author.

**Rationale**: Knowing who recorded what and when is essential for understanding the evolution of a project and for accountability.

**Implementation**:
- `author` is a required field on all entries
- `timestamp` is automatically generated in ISO 8601 format
- `entry_id` format includes date: `YYYY-MM-DD-NNN`

### 4. Atomic Operations

**Principle**: Operations either complete fully or have no effect.

**Rationale**: Partial writes can corrupt data and violate reproducibility guarantees.

**Implementation**:
- File locking via `portalocker` prevents concurrent modifications
- Entries are written atomically using Python's file operations
- Index updates happen after successful file writes
- Failed operations don't leave partial state

### 5. Causality Tracking

**Principle**: Relationships between entries, configs, and logs are preserved.

**Rationale**: Understanding why something happened requires knowing what preceded it.

**Implementation**:
- `caused_by` field links entries to their causes
- `config_used` and `log_produced` link entries to artifacts
- `trace_causality` tool navigates these relationships
- Amendments explicitly reference the entry being amended

---

## System Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   MCP Server    │  │      CLI        │  │  Python API     │  │
│  │   (stdio)       │  │   (argparse)    │  │   (direct)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Layer (tools.py)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Journal    │  │   Config    │  │    Log      │  ...         │
│  │  Tools      │  │   Tools     │  │   Tools     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Business Layer (engine.py)                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     JournalEngine                           ││
│  │  - Entry management    - Config archiving                   ││
│  │  - Log preservation    - State snapshots                    ││
│  │  - Query/Search        - Template management                ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Data Access Layer                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  JournalIndex   │  │   FileManager   │  │  LockManager    │  │
│  │  (index.py)     │  │  (engine.py)    │  │  (locking.py)   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │  Markdown Files │  │  SQLite Index   │                       │
│  │  (source)       │  │  (cache)        │                       │
│  └─────────────────┘  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Module Dependency Graph

```
server.py
    ├── tools.py
    │   └── engine.py
    │       ├── index.py
    │       ├── models.py
    │       ├── locking.py
    │       └── config.py
    │           └── models.py
    └── config.py
```

---

## Component Architecture

### Server Component (server.py)

**Responsibility**: MCP protocol handling and tool registration.

```python
class JournalServer:
    """MCP server implementing the journal protocol."""

    def __init__(self, config: ProjectConfig):
        self.engine = JournalEngine(config)
        self.tools = self._register_tools()

    def _register_tools(self) -> dict:
        """Register all MCP tools with the server."""
        # Built-in tools from tools.py
        # Custom tools from config.custom_tools
        pass

    async def handle_request(self, request: dict) -> dict:
        """Process incoming MCP requests."""
        pass
```

**Interfaces**:
- Input: MCP JSON-RPC messages over stdio
- Output: MCP JSON-RPC responses over stdio
- Dependencies: `JournalEngine`, `ProjectConfig`

### Tools Component (tools.py)

**Responsibility**: MCP tool definitions and parameter validation.

```python
# Tool definition structure
TOOLS = {
    "journal_append": {
        "description": "Append a new entry to the journal",
        "inputSchema": {...},
        "handler": journal_append_handler
    },
    # ... other tools
}

def journal_append_handler(engine: JournalEngine, params: dict) -> dict:
    """Handle journal_append tool calls."""
    # Validate parameters
    # Call engine method
    # Return result
    pass
```

**Tool Categories**:

| Category | Tools |
|----------|-------|
| Journal | `journal_append`, `journal_amend`, `journal_read`, `journal_query`, `journal_search`, `journal_stats`, `journal_active` |
| Config | `config_archive`, `config_activate`, `config_diff` |
| Log | `log_preserve` |
| State | `state_snapshot`, `timeline`, `trace_causality` |
| Session | `session_handoff` |
| Maintenance | `index_rebuild`, `rebuild_sqlite_index` |
| Templates | `list_templates`, `get_template` |
| Help | `journal_help` |

### Engine Component (engine.py)

**Responsibility**: Core business logic for all journal operations.

```python
class JournalEngine:
    """Core journal operations engine."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self._index = JournalIndex(config.journal_dir / ".index.db")
        self._ensure_directories()

    # Journal operations
    def journal_append(self, **kwargs) -> JournalEntry: ...
    def journal_amend(self, **kwargs) -> JournalEntry: ...
    def journal_read(self, **kwargs) -> list[dict]: ...
    def journal_query(self, **kwargs) -> dict: ...
    def journal_search(self, **kwargs) -> list[dict]: ...
    def journal_stats(self, **kwargs) -> dict: ...
    def journal_active(self, **kwargs) -> list[dict]: ...

    # Config operations
    def config_archive(self, **kwargs) -> ConfigArchive: ...
    def config_activate(self, **kwargs) -> dict: ...
    def config_diff(self, **kwargs) -> str: ...

    # Log operations
    def log_preserve(self, **kwargs) -> LogRecord: ...

    # State operations
    def state_snapshot(self, **kwargs) -> StateSnapshot: ...
    def timeline(self, **kwargs) -> list[dict]: ...
    def trace_causality(self, **kwargs) -> dict: ...

    # Session operations
    def session_handoff(self, **kwargs) -> str: ...
```

**Key Methods**:

| Method | Description |
|--------|-------------|
| `_get_next_entry_id()` | Generate sequential entry ID for today |
| `_write_entry_to_file()` | Atomically append entry to markdown |
| `_update_index()` | Update SQLite index after write |
| `_read_journal_file()` | Parse markdown file into entries |
| `_rebuild_index_from_files()` | Full index reconstruction |

### Index Component (index.py)

**Responsibility**: SQLite-based query and search indexing.

```python
class JournalIndex:
    """SQLite index for fast journal queries."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = self._connect()
        self._ensure_schema()

    def index_entry(self, entry: dict, file_path: Path) -> None:
        """Add or update an entry in the index."""
        pass

    def query(self, filters: dict, limit: int, offset: int,
              order_by: str, order_desc: bool) -> list[dict]:
        """Execute structured query with filters."""
        pass

    def search_text(self, query: str, **filters) -> list[dict]:
        """Full-text search using FTS5."""
        pass

    def aggregate(self, group_by: str, filters: dict) -> dict:
        """Compute aggregated statistics."""
        pass

    def rebuild(self, journal_dir: Path) -> None:
        """Rebuild entire index from markdown files."""
        pass

    def close(self) -> None:
        """Close database connection."""
        pass
```

**Schema**:

```sql
-- Main entries table
CREATE TABLE entries (
    entry_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    date TEXT NOT NULL,
    author TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    outcome TEXT,
    template TEXT,
    context TEXT,
    intent TEXT,
    action TEXT,
    observation TEXT,
    analysis TEXT,
    next_steps TEXT,
    config_used TEXT,
    log_produced TEXT,
    caused_by TEXT,
    tool TEXT,
    duration_ms INTEGER,
    exit_code INTEGER,
    command TEXT,
    error_type TEXT,
    file_path TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX idx_date ON entries(date);
CREATE INDEX idx_author ON entries(author);
CREATE INDEX idx_outcome ON entries(outcome);
CREATE INDEX idx_tool ON entries(tool);
CREATE INDEX idx_entry_type ON entries(entry_type);

-- Full-text search
CREATE VIRTUAL TABLE entries_fts USING fts5(
    entry_id,
    context,
    intent,
    action,
    observation,
    analysis,
    content='entries',
    content_rowid='rowid'
);
```

### Config Component (config.py)

**Responsibility**: Configuration loading and validation.

```python
@dataclass
class ProjectConfig:
    """Project configuration settings."""

    project_name: str
    project_root: Path
    journal_dir: Path
    configs_dir: Path
    logs_dir: Path
    snapshots_dir: Path
    templates: dict[str, EntryTemplateConfig]
    version_commands: dict[str, str]
    hooks: dict[str, Callable]
    custom_tools: dict[str, Callable]

    @classmethod
    def load(cls, project_root: Path, config_path: Path = None) -> "ProjectConfig":
        """Load configuration from file or use defaults."""
        pass

    @classmethod
    def from_toml(cls, path: Path) -> "ProjectConfig":
        """Load from TOML configuration file."""
        pass

    @classmethod
    def from_json(cls, path: Path) -> "ProjectConfig":
        """Load from JSON configuration file."""
        pass

    @classmethod
    def from_python(cls, path: Path) -> "ProjectConfig":
        """Load from Python configuration module."""
        pass
```

### Models Component (models.py)

**Responsibility**: Data structures for entries, archives, and snapshots.

```python
@dataclass
class JournalEntry:
    """A single journal entry."""
    entry_id: str
    timestamp: datetime
    author: str
    entry_type: str  # 'entry' or 'amendment'

    # Content fields
    context: str = None
    intent: str = None
    action: str = None
    observation: str = None
    analysis: str = None
    next_steps: str = None
    outcome: str = None

    # Links
    references: list[str] = None
    caused_by: list[str] = None
    config_used: str = None
    log_produced: str = None

    # Template
    template: str = None
    template_values: dict = None

    # Diagnostic fields
    tool: str = None
    command: str = None
    duration_ms: int = None
    exit_code: int = None
    error_type: str = None


@dataclass
class ConfigArchive:
    """An archived configuration file."""
    original_path: Path
    archive_path: Path
    timestamp: datetime
    reason: str
    journal_entry: str = None
    stage: str = None


@dataclass
class LogRecord:
    """A preserved log file record."""
    original_path: Path
    preserved_path: Path
    timestamp: datetime
    category: str
    outcome: str


@dataclass
class StateSnapshot:
    """A complete state snapshot."""
    name: str
    timestamp: datetime
    snapshot_path: Path
    configs: dict
    environment: dict
    versions: dict
    build_dir_listing: list = None
```

### Locking Component (locking.py)

**Responsibility**: File-level locking for concurrent access.

```python
class FileLock:
    """Context manager for file locking."""

    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = path
        self.timeout = timeout
        self._lock_file = None

    def __enter__(self):
        """Acquire lock."""
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._lock_file = open(lock_path, "w")
        portalocker.lock(self._lock_file, portalocker.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self._lock_file:
            portalocker.unlock(self._lock_file)
            self._lock_file.close()
        return False
```

---

## Data Architecture

### Directory Structure

```
{project_root}/
├── journal/                    # Journal entries
│   ├── .index.db              # SQLite index (hidden)
│   ├── 2026-01-15.md          # Daily journal files
│   ├── 2026-01-16.md
│   └── 2026-01-17.md
│
├── configs/                    # Archived configurations
│   ├── INDEX.md               # Human-readable index
│   └── {name}/                # Per-config directories
│       ├── 2026-01-15T10-30-00_{reason}.toml
│       └── 2026-01-16T14-45-00_{reason}.toml
│
├── logs/                       # Preserved logs
│   ├── INDEX.md               # Human-readable index
│   └── {category}/            # Per-category directories
│       ├── 2026-01-15T10-30-00_success.log
│       └── 2026-01-16T14-45-00_failure.log
│
└── snapshots/                  # State snapshots
    ├── INDEX.md               # Human-readable index
    └── 2026-01-15T10-30-00_pre-build.json
```

### Journal Entry Format

```markdown
## 2026-01-17-001

**Timestamp**: 2026-01-17T14:30:00+00:00
**Author**: claude
**Template**: diagnostic

### Context
Building release version of the application.

### Intent
Run the full build process to create distributable artifacts.

### Action
```bash
make build
```

### Observation
Build completed in 45 seconds with no errors.

### Outcome
success

### Tool
bash

### Duration
45000

### Exit Code
0

---
```

### Index Entry Format

The SQLite index stores parsed entry data:

| Column | Type | Source |
|--------|------|--------|
| entry_id | TEXT | Parsed from `## {id}` |
| timestamp | TEXT | Parsed from `**Timestamp**:` |
| date | TEXT | Extracted from timestamp |
| author | TEXT | Parsed from `**Author**:` |
| outcome | TEXT | Parsed from `### Outcome` |
| context | TEXT | Parsed from `### Context` |
| ... | ... | ... |

### Config Archive Format

Archives preserve the original file with metadata:

```
configs/bootstrap.toml/2026-01-17T14-30-00_pre-llvm-change.toml
```

The INDEX.md tracks all archives:

```markdown
# Configuration Archives

## bootstrap.toml

| Timestamp | Reason | Journal Entry |
|-----------|--------|---------------|
| 2026-01-17T14:30:00 | pre-llvm-change | 2026-01-17-005 |
| 2026-01-16T10:00:00 | initial-setup | 2026-01-16-001 |
```

### Snapshot Format

State snapshots are JSON files containing complete state:

```json
{
  "name": "pre-build",
  "timestamp": "2026-01-17T14:30:00+00:00",
  "configs": {
    "bootstrap.toml": "...<content>..."
  },
  "environment": {
    "PATH": "/usr/bin:...",
    "CC": "gcc"
  },
  "versions": {
    "rustc": "rustc 1.92.0",
    "gcc": "gcc 13.2.0"
  },
  "build_dir_listing": [
    "build/stage1/",
    "build/stage2/"
  ]
}
```

---

## Communication Flow

### MCP Tool Call Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │    │  Server  │    │  Tools   │    │  Engine  │    │  Index   │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │               │
     │ tool_call     │               │               │               │
     │──────────────>│               │               │               │
     │               │ dispatch      │               │               │
     │               │──────────────>│               │               │
     │               │               │ validate      │               │
     │               │               │───────┐       │               │
     │               │               │<──────┘       │               │
     │               │               │ call          │               │
     │               │               │──────────────>│               │
     │               │               │               │ acquire_lock  │
     │               │               │               │───────┐       │
     │               │               │               │<──────┘       │
     │               │               │               │ write_file    │
     │               │               │               │───────┐       │
     │               │               │               │<──────┘       │
     │               │               │               │ update_index  │
     │               │               │               │──────────────>│
     │               │               │               │<──────────────│
     │               │               │               │ release_lock  │
     │               │               │               │───────┐       │
     │               │               │<──────────────│<──────┘       │
     │               │<──────────────│               │               │
     │<──────────────│               │               │               │
     │               │               │               │               │
```

### Query Execution Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │    │  Engine  │    │  Index   │    │ SQLite   │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │
     │ journal_query │               │               │
     │──────────────>│               │               │
     │               │ query         │               │
     │               │──────────────>│               │
     │               │               │ build_sql     │
     │               │               │───────┐       │
     │               │               │<──────┘       │
     │               │               │ execute       │
     │               │               │──────────────>│
     │               │               │<──────────────│
     │               │               │ format        │
     │               │<──────────────│───────┐       │
     │<──────────────│               │<──────┘       │
     │               │               │               │
```

### Hook Execution Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Engine  │    │  Hooks   │    │ User Code│    │  Result  │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │
     │ pre_hook      │               │               │
     │──────────────>│               │               │
     │               │ invoke        │               │
     │               │──────────────>│               │
     │               │<──────────────│               │
     │               │ (may modify)  │               │
     │<──────────────│               │               │
     │ execute       │               │               │
     │───────┐       │               │               │
     │<──────┘       │               │               │
     │ post_hook     │               │               │
     │──────────────>│               │               │
     │               │ invoke        │               │
     │               │──────────────>│               │
     │               │<──────────────│               │
     │<──────────────│               │               │
     │               │               │               │
```

---

## Concurrency Model

### File Locking Strategy

MCP Journal uses pessimistic locking with file-level granularity:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Lock Hierarchy                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Journal File Lock                           │    │
│  │        (journal/YYYY-MM-DD.md.lock)                     │    │
│  │  - Acquired for: append, amend                          │    │
│  │  - Duration: entry write + index update                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Index Lock (implicit)                       │    │
│  │        (journal/.index.db SQLite lock)                  │    │
│  │  - Acquired for: index operations                       │    │
│  │  - Duration: transaction scope                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Config/Log Lock                             │    │
│  │        (file.lock)                                       │    │
│  │  - Acquired for: archive, preserve                       │    │
│  │  - Duration: file copy operation                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Lock Acquisition Rules

1. **Single Lock Rule**: One lock per operation
2. **Timeout**: Default 10 seconds, configurable
3. **No Deadlocks**: No nested lock acquisition
4. **Cleanup**: Locks released on exception

### SQLite Concurrency

- **WAL Mode**: Write-Ahead Logging for concurrent reads
- **Busy Timeout**: 5 seconds for lock acquisition
- **Transaction Scope**: Per-operation transactions

```python
# SQLite connection setup
conn = sqlite3.connect(
    db_path,
    isolation_level=None,  # Autocommit
    timeout=5.0
)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

---

## Extension Points

### Custom Tools

Python configuration can define custom MCP tools:

```python
# journal_config.py
def custom_tool_my_tool(engine, param1: str, param2: int = 10) -> dict:
    """My custom tool description.

    Args:
        param1: First parameter
        param2: Second parameter with default

    Returns:
        Tool result dictionary
    """
    # Access engine methods
    result = engine.journal_append(
        author="custom",
        context=f"Custom tool called with {param1}"
    )
    return {"status": "success", "entry_id": result.entry_id}
```

### Lifecycle Hooks

Hooks intercept operations at defined points:

| Hook | Timing | Can Modify | Can Cancel |
|------|--------|------------|------------|
| `hook_pre_append` | Before append | Yes | Yes |
| `hook_post_append` | After append | No | No |
| `hook_pre_archive` | Before archive | Yes | Yes |
| `hook_post_archive` | After archive | No | No |
| `hook_pre_preserve` | Before preserve | Yes | Yes |
| `hook_post_preserve` | After preserve | No | No |

```python
# journal_config.py
def hook_pre_append(entry_data: dict) -> dict:
    """Modify or validate entry before append."""
    # Add custom field
    entry_data["custom_field"] = "value"
    return entry_data  # Return modified data

def hook_post_append(entry: JournalEntry) -> None:
    """React to successful append."""
    if entry.outcome == "failure":
        send_notification(entry)
```

### Templates

Entry templates define required and optional fields:

```python
# Configuration-defined template
templates:
  build:
    description: "Build process entry"
    required_fields: ["context", "outcome"]
    optional_fields: ["intent", "action", "observation", "analysis"]
    field_descriptions:
      context: "What is being built and why"
      outcome: "Build result: success, failure, partial"
```

Templates are enforced at append time and guide AI agents in providing complete entries.

---

## Security Considerations

### File System Permissions

- Journal directories inherit parent permissions
- Lock files are created with restricted permissions
- Config archives preserve original file permissions

### Input Validation

- Path traversal prevention in file operations
- Entry ID format validation
- Template field validation

### Data Integrity

- SHA-256 content hashing for duplicates detection
- Atomic writes prevent partial entries
- Index rebuild verifies against source files

### No Deletion

- Append-only model prevents data loss
- No delete operations exposed
- Index rebuild recreates lost index data

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| `journal_append` | O(1) | Append to file end |
| `journal_query` (indexed) | O(log n) | SQLite B-tree lookup |
| `journal_search` (FTS) | O(n * log n) | FTS5 inverted index |
| `journal_stats` | O(n) | Full table scan with grouping |
| `index_rebuild` | O(n) | Parse all markdown files |
| `config_archive` | O(k) | k = file size |

### Space Complexity

| Component | Growth | Notes |
|-----------|--------|-------|
| Journal files | Linear | ~1KB per entry |
| SQLite index | Linear | ~500B per entry |
| Config archives | Per-archive | Original file size |
| Snapshots | Per-snapshot | Config sizes + metadata |

### Optimization Strategies

1. **Index Maintenance**: Incremental updates after each append
2. **Query Planning**: SQLite query optimizer leverages indexes
3. **FTS5 Tokenization**: Standard tokenizer for text search
4. **Lazy Loading**: Entries loaded on demand, not at startup
5. **Connection Pooling**: Single SQLite connection per engine

### Scalability Limits

| Dimension | Recommended Limit | Hard Limit |
|-----------|-------------------|------------|
| Entries per day | 1,000 | 10,000 |
| Total entries | 100,000 | 1,000,000 |
| Entry content | 10KB | 1MB |
| Snapshot size | 10MB | 100MB |

---

## See Also

- [User Guide](user-guide.md) - User documentation
- [Developer Guide](developer-guide.md) - Development practices
- [API Reference](api/README.md) - Tool documentation
- [Configuration Reference](configuration.md) - Configuration options
