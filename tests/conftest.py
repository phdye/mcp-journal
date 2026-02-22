"""Shared pytest fixtures for mcp-journal tests."""

import gc
import tempfile
import weakref
from pathlib import Path

import pytest

from mcp_journal.config import ProjectConfig
from mcp_journal.engine import JournalEngine


# Global tracking of engines via weak references
_engine_refs = []


# Patch JournalEngine.__init__ at import time to track all instances
_original_init = JournalEngine.__init__


def _tracking_init(self, *args, **kwargs):
    """Wrapper for JournalEngine.__init__ that tracks created engines."""
    _original_init(self, *args, **kwargs)
    _engine_refs.append(weakref.ref(self))


# Apply the patch immediately at import time
JournalEngine.__init__ = _tracking_init


def cleanup_all_engines():
    """Clean up all tracked engine instances."""
    global _engine_refs

    # Force garbage collection first to clean up unreferenced engines
    gc.collect()

    # Close all still-alive engines
    for ref in _engine_refs:
        eng = ref()
        if eng is not None:
            try:
                if eng._index is not None:
                    eng._index.close()
                    eng._index = None
            except Exception:
                pass  # Ignore cleanup errors

    # Clear the refs list
    _engine_refs = []

    # Force another GC pass to release file handles (important on Windows)
    gc.collect()


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    global _engine_refs
    # Clear any stale refs from previous tests
    _engine_refs = [ref for ref in _engine_refs if ref() is not None]

    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
        # Clean up engines BEFORE the temp directory is deleted
        cleanup_all_engines()


@pytest.fixture
def config(temp_project):
    """Create a test configuration."""
    return ProjectConfig(
        project_name="test-project",
        project_root=temp_project,
    )


@pytest.fixture
def engine(config):
    """Create a test engine with proper cleanup."""
    eng = JournalEngine(config)
    yield eng
    # Cleanup: close the index database connection
    if eng._index is not None:
        eng._index.close()


@pytest.fixture
def engine_factory(temp_project):
    """Factory fixture that creates engines and ensures cleanup.

    Usage:
        def test_example(engine_factory, temp_project):
            config = ProjectConfig(project_root=temp_project, ...)
            engine = engine_factory(config)
            # ... test code ...
            # Engine will be automatically cleaned up
    """
    engines = []

    def _create(config):
        eng = JournalEngine(config)
        engines.append(eng)
        return eng

    yield _create

    # Cleanup all created engines
    for eng in engines:
        if eng._index is not None:
            eng._index.close()
