# Contributing to MCP Journal

Thank you for your interest in contributing to MCP Journal! This document provides guidelines and information for contributors.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/phdyex/mcp-journal.git
   cd mcp-journal
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[all]"
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/mcp_journal --cov-report=term-missing

# Run specific test file
pytest tests/test_engine.py -v

# Run tests matching a pattern
pytest -k "test_append"
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Keep functions focused and single-purpose
- Document public APIs with docstrings

## Pull Request Process

1. **Fork and branch**: Create a feature branch from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes**: Implement your feature or fix

3. **Write tests**: Ensure new code has test coverage

4. **Run tests**: Make sure all tests pass
   ```bash
   pytest
   ```

5. **Update documentation**: Update README.md if needed

6. **Submit PR**: Open a pull request with a clear description

## Design Principles

When contributing, keep these core principles in mind:

1. **Append-Only**: Never delete, edit, or overwrite existing journal/config/log content
2. **Timestamped**: Every action must have a precise UTC timestamp
3. **Attributed**: Every entry must have an author
4. **Complete**: Capture full context, not just changes
5. **Reproducible**: Archive everything needed to reproduce state

## Adding New Features

### New MCP Tools

1. Define the tool in `src/mcp_journal/tools.py`
2. Implement the logic in `src/mcp_journal/engine.py`
3. Add comprehensive tests
4. Update documentation

### Configuration Options

1. Add to `src/mcp_journal/config.py`
2. Update example configs in `examples/`
3. Document in README.md

## Reporting Issues

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
