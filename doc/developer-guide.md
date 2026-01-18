# Developer Guide

**Version**: 0.2.0
**Last Updated**: 2026-01-17

## Table of Contents

1. [Development Environment](#development-environment)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Code Standards](#code-standards)
5. [Testing](#testing)
6. [Adding Features](#adding-features)
7. [Documentation](#documentation)
8. [Release Process](#release-process)
9. [Troubleshooting](#troubleshooting)

---

## Development Environment

### Prerequisites

- **Python**: 3.10 or later
- **Git**: For version control
- **pip**: For package management

### Setup

1. **Clone the repository**:

```bash
git clone https://github.com/phdyex/mcp-journal.git
cd mcp-journal
```

2. **Create virtual environment**:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

3. **Install in development mode**:

```bash
pip install -e ".[dev]"
```

This installs:
- The package in editable mode
- Development dependencies (pytest, mypy, etc.)

4. **Verify installation**:

```bash
pytest --version
mcp-journal --version
```

### IDE Configuration

#### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Python Test Explorer

`.vscode/settings.json`:
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.linting.enabled": true,
    "python.linting.mypyEnabled": true,
    "editor.formatOnSave": true,
    "python.formatting.provider": "black"
}
```

#### PyCharm

1. Mark `src` as Sources Root
2. Configure pytest as test runner
3. Enable mypy integration

---

## Project Structure

```
mcp-journal/
├── src/
│   └── mcp_journal/
│       ├── __init__.py      # Package init, version
│       ├── server.py        # MCP server, CLI entry point
│       ├── engine.py        # Core business logic
│       ├── tools.py         # MCP tool definitions
│       ├── index.py         # SQLite index management
│       ├── config.py        # Configuration loading
│       ├── models.py        # Data models
│       └── locking.py       # File locking
│
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── test_engine.py       # Engine tests
│   ├── test_tools.py        # Tool tests
│   ├── test_index.py        # Index tests
│   ├── test_query.py        # Query tests
│   ├── test_config.py       # Config tests
│   ├── test_server.py       # Server tests
│   ├── test_integration.py  # Integration tests
│   └── ...
│
├── doc/
│   ├── README.md            # Documentation index
│   ├── user-guide.md        # User documentation
│   ├── configuration.md     # Configuration reference
│   ├── cli-reference.md     # CLI reference
│   ├── architecture.md      # System architecture
│   ├── developer-guide.md   # This file
│   └── api/                 # API reference (man pages)
│       ├── README.md
│       ├── journal_append.md
│       └── ...
│
├── examples/
│   ├── journal_config.toml  # TOML config example
│   ├── journal_config.json  # JSON config example
│   └── journal_config.py    # Python config example
│
├── prompt/
│   └── handoff/
│       └── initial.md       # Original requirements
│
├── pyproject.toml           # Package configuration
├── CLAUDE.md                # AI assistant instructions
└── README.md                # Project readme
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `server.py` | MCP protocol handling, CLI commands |
| `engine.py` | Core journal operations, business logic |
| `tools.py` | MCP tool definitions, parameter schemas |
| `index.py` | SQLite index for queries and search |
| `config.py` | Configuration loading from TOML/JSON/Python |
| `models.py` | Data classes for entries, archives, etc. |
| `locking.py` | File locking for concurrent access |

---

## Development Workflow

### Branch Strategy

```
main
  │
  ├── feature/add-new-tool
  ├── fix/query-pagination
  └── docs/update-api-reference
```

- **main**: Stable, releasable code
- **feature/***: New features
- **fix/***: Bug fixes
- **docs/***: Documentation updates

### Development Cycle

1. **Create branch**:
```bash
git checkout -b feature/my-feature
```

2. **Make changes**: Edit code, add tests

3. **Run tests**:
```bash
pytest
```

4. **Check types** (optional but recommended):
```bash
mypy src/mcp_journal
```

5. **Commit changes**:
```bash
git add .
git commit -m "Add feature X"
```

6. **Push and create PR**:
```bash
git push origin feature/my-feature
```

### Commit Message Format

```
<type>: <short description>

<longer description if needed>

<references>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Test changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

Example:
```
feat: Add journal_active tool for finding long-running operations

Implements detection of active operations based on duration threshold.
Uses SQLite index for efficient queries.

Closes #42
```

---

## Code Standards

### Python Style

Follow PEP 8 with these specifics:

- **Line length**: 88 characters (Black default)
- **Imports**: Sorted with isort
- **Docstrings**: Google style
- **Type hints**: Required for public APIs

### Docstring Format

```python
def journal_append(
    self,
    author: str,
    context: str = None,
    intent: str = None,
    outcome: str = None,
    template: str = None,
) -> JournalEntry:
    """Append a new entry to the journal.

    Creates a new timestamped entry in today's journal file.
    The entry is atomic - either fully written or not at all.

    Args:
        author: Who is making this entry (required).
        context: Current state, what we're trying to accomplish.
        intent: What action we're about to take and why.
        outcome: Result of the operation (success/failure/partial).
        template: Template name to use for this entry.

    Returns:
        JournalEntry: The created entry with assigned ID.

    Raises:
        ValueError: If author is empty or template not found.
        IOError: If journal file cannot be written.

    Example:
        >>> entry = engine.journal_append(
        ...     author="claude",
        ...     context="Building release version",
        ...     outcome="success"
        ... )
        >>> print(entry.entry_id)
        2026-01-17-001
    """
```

### Type Annotations

```python
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime

def query(
    self,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "timestamp",
    order_desc: bool = True
) -> List[Dict[str, Any]]:
    ...
```

### Error Handling

```python
# Use specific exceptions
class JournalError(Exception):
    """Base exception for journal operations."""
    pass

class EntryNotFoundError(JournalError):
    """Entry with given ID does not exist."""
    pass

class ConfigurationError(JournalError):
    """Configuration is invalid or missing."""
    pass

# Raise with context
def get_entry(self, entry_id: str) -> JournalEntry:
    entry = self._find_entry(entry_id)
    if entry is None:
        raise EntryNotFoundError(f"Entry not found: {entry_id}")
    return entry
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Module | lowercase_underscore | `journal_engine.py` |
| Class | PascalCase | `JournalEngine` |
| Function | lowercase_underscore | `journal_append` |
| Constant | UPPERCASE_UNDERSCORE | `DEFAULT_TIMEOUT` |
| Private | _leading_underscore | `_internal_method` |

---

## Testing

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_engine.py           # Unit tests for engine
├── test_tools.py            # Unit tests for tools
├── test_index.py            # Unit tests for index
├── test_query.py            # Query-specific tests
├── test_config.py           # Configuration tests
├── test_server.py           # Server tests
├── test_integration.py      # Integration tests
├── test_edge_cases.py       # Edge case tests
├── test_error_paths.py      # Error handling tests
└── test_full_coverage.py    # Coverage gap tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific file
pytest tests/test_engine.py

# Run specific test
pytest tests/test_engine.py::test_journal_append

# Run by pattern
pytest -k "append"

# Run with coverage
pytest --cov=mcp_journal --cov-report=html
```

### Writing Tests

#### Basic Test Structure

```python
import pytest
from pathlib import Path

def test_journal_append_creates_entry(engine):
    """Test that journal_append creates a valid entry."""
    # Arrange
    author = "test-author"
    context = "Test context"

    # Act
    entry = engine.journal_append(author=author, context=context)

    # Assert
    assert entry.entry_id is not None
    assert entry.author == author
    assert entry.context == context
```

#### Using Fixtures

```python
# conftest.py provides these fixtures:
# - temp_project: Temporary directory
# - config: ProjectConfig for testing
# - engine: JournalEngine instance

def test_with_engine(engine):
    """Use the engine fixture."""
    entry = engine.journal_append(author="test")
    assert entry is not None

def test_with_custom_config(temp_project):
    """Create custom config for test."""
    config = ProjectConfig(
        project_name="custom",
        project_root=temp_project,
    )
    engine = JournalEngine(config)
    # ... test code ...
```

#### Testing Exceptions

```python
def test_append_requires_author(engine):
    """Test that journal_append requires author."""
    with pytest.raises(ValueError, match="author.*required"):
        engine.journal_append(author="")
```

#### Parametrized Tests

```python
@pytest.mark.parametrize("outcome,expected", [
    ("success", "success"),
    ("failure", "failure"),
    ("partial", "partial"),
    (None, None),
])
def test_outcomes(engine, outcome, expected):
    """Test various outcome values."""
    entry = engine.journal_append(author="test", outcome=outcome)
    assert entry.outcome == expected
```

#### Integration Tests

```python
def test_full_workflow(engine):
    """Test complete journal workflow."""
    # Create entries
    entry1 = engine.journal_append(
        author="claude",
        context="Starting build"
    )

    # Amend entry
    amendment = engine.journal_amend(
        references_entry=entry1.entry_id,
        correction="Wrong context",
        actual="Starting test",
        impact="Minor",
        author="claude"
    )

    # Query entries
    results = engine.journal_query(
        filters={"author": "claude"},
        limit=10
    )

    # Verify
    assert len(results["entries"]) >= 2
    assert entry1.entry_id in [e["entry_id"] for e in results["entries"]]
```

### Test Coverage

Aim for high coverage on critical paths:

| Module | Target Coverage |
|--------|-----------------|
| engine.py | 90%+ |
| index.py | 85%+ |
| tools.py | 85%+ |
| config.py | 80%+ |
| server.py | 75%+ |

Check coverage:
```bash
pytest --cov=mcp_journal --cov-report=term-missing
```

### Fixture Cleanup

Important: Always clean up resources to avoid test pollution:

```python
@pytest.fixture
def engine(config):
    """Create engine with cleanup."""
    eng = JournalEngine(config)
    yield eng
    # Cleanup: close database connection
    if eng._index is not None:
        eng._index.close()
```

The shared fixtures in `conftest.py` handle this automatically through engine tracking.

---

## Adding Features

### Adding a New MCP Tool

1. **Define the tool in `tools.py`**:

```python
# Add to TOOLS dictionary
"journal_my_tool": {
    "description": "Description of what the tool does",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "First parameter"
            },
            "param2": {
                "type": "integer",
                "description": "Second parameter",
                "default": 10
            }
        },
        "required": ["param1"]
    }
}
```

2. **Implement the handler in `engine.py`**:

```python
def journal_my_tool(
    self,
    param1: str,
    param2: int = 10
) -> dict:
    """Implement the tool logic.

    Args:
        param1: First parameter
        param2: Second parameter

    Returns:
        Result dictionary
    """
    # Implementation
    result = self._do_something(param1, param2)
    return {"status": "success", "data": result}
```

3. **Add tests in `tests/test_tools.py`**:

```python
def test_my_tool_basic(engine):
    """Test basic functionality."""
    result = engine.journal_my_tool(param1="value")
    assert result["status"] == "success"

def test_my_tool_with_param2(engine):
    """Test with optional parameter."""
    result = engine.journal_my_tool(param1="value", param2=20)
    assert result["status"] == "success"
```

4. **Update documentation**:
   - Add to `doc/api/journal_my_tool.md`
   - Update `doc/api/README.md`
   - Update help system if applicable

### Adding a New Configuration Option

1. **Add to `config.py`**:

```python
@dataclass
class ProjectConfig:
    # ... existing fields ...
    my_new_option: str = "default_value"
```

2. **Add parsing in configuration loaders**:

```python
@classmethod
def from_toml(cls, path: Path) -> "ProjectConfig":
    data = tomli.loads(path.read_text())
    return cls(
        # ... existing ...
        my_new_option=data.get("my_new_option", "default_value")
    )
```

3. **Document in `doc/configuration.md`**

4. **Add tests in `tests/test_config.py`**

### Adding a Database Field

1. **Update schema in `index.py`**:

```python
def _ensure_schema(self):
    # Add column to CREATE TABLE
    # Add migration for existing databases
    pass
```

2. **Update model in `models.py`**:

```python
@dataclass
class JournalEntry:
    # ... existing ...
    new_field: str = None
```

3. **Update index operations**:
   - `index_entry()`: Include new field
   - `query()`: Support filtering by new field

4. **Add tests for new field**

---

## Documentation

### Documentation Structure

| Directory | Purpose |
|-----------|---------|
| `doc/` | All documentation |
| `doc/api/` | API reference (man pages) |
| `examples/` | Example configurations |

### Writing Documentation

#### User Documentation

Focus on:
- Clear, step-by-step instructions
- Real-world examples
- Common use cases
- Troubleshooting guides

#### API Documentation

Use man(3) page style:
- NAME: Tool name and short description
- SYNOPSIS: Function signature
- DESCRIPTION: Detailed explanation
- PARAMETERS: Each parameter explained
- RETURN VALUE: What's returned
- ERRORS: What can go wrong
- EXAMPLES: Working code examples
- SEE ALSO: Related tools

#### Docstrings

All public functions must have docstrings:
- Summary line
- Extended description
- Args with types and descriptions
- Returns description
- Raises for exceptions
- Example if helpful

### Building Documentation

Documentation is in Markdown format and can be:
- Read directly on GitHub
- Converted to HTML with MkDocs or similar
- Accessed by AI through the help system

---

## Release Process

### Version Numbering

Follow Semantic Versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Checklist

1. **Update version**:
   - `src/mcp_journal/__init__.py`
   - `pyproject.toml`
   - `doc/` files

2. **Update CHANGELOG**

3. **Run full test suite**:
```bash
pytest
```

4. **Build package**:
```bash
python -m build
```

5. **Test installation**:
```bash
pip install dist/mcp_journal-X.Y.Z-py3-none-any.whl
```

6. **Create release tag**:
```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

7. **Publish to PyPI** (if applicable):
```bash
twine upload dist/*
```

---

## Troubleshooting

### Common Development Issues

#### Import Errors

```
ModuleNotFoundError: No module named 'mcp_journal'
```

**Solution**: Install in development mode:
```bash
pip install -e .
```

#### Test Database Errors

```
sqlite3.OperationalError: database is locked
```

**Solution**: Ensure engine cleanup in fixtures. Use shared fixtures from `conftest.py`.

#### Test Teardown Errors

```
OSError: [Errno 16] Device or resource busy
```

**Solution**: Close database connections before temp directory cleanup. The `conftest.py` fixtures handle this.

#### Type Checking Errors

```
error: Incompatible types in assignment
```

**Solution**: Add proper type annotations or use `# type: ignore` with explanation.

### Debugging Tips

1. **Use pytest -v** for verbose output
2. **Use pytest --pdb** to drop into debugger on failure
3. **Add print statements** (pytest captures them)
4. **Use pytest -s** to see print output
5. **Check log files** in test temp directories

### Getting Help

- **Issues**: GitHub Issues for bugs and feature requests
- **Discussions**: GitHub Discussions for questions
- **Code Review**: Request review on pull requests

---

## See Also

- [Architecture](architecture.md) - System design
- [User Guide](user-guide.md) - User documentation
- [API Reference](api/README.md) - Tool documentation
- [Configuration Reference](configuration.md) - Configuration options
