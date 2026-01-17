"""File locking utilities for concurrent access safety."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import portalocker


@contextmanager
def file_lock(path: Path, timeout: float = 10.0) -> Generator[None, None, None]:
    """Acquire an exclusive lock on a file.

    Creates a .lock file alongside the target file.

    Args:
        path: File to lock
        timeout: Seconds to wait for lock

    Raises:
        portalocker.LockException: If lock cannot be acquired
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Create lock file if it doesn't exist
    if not lock_path.exists():
        lock_path.touch()

    with portalocker.Lock(lock_path, timeout=timeout):
        yield


@contextmanager
def atomic_write(path: Path, mode: str = "w", encoding: str = "utf-8") -> Generator:
    """Write to a file atomically.

    Writes to a temporary file then renames to target path.
    Combined with file_lock for full safety.

    Args:
        path: Target file path
        mode: Write mode ('w' for text, 'wb' for binary)
        encoding: Text encoding (ignored for binary mode)

    Yields:
        File handle for writing
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if "b" in mode:
            with open(tmp_path, mode) as f:
                yield f
        else:
            with open(tmp_path, mode, encoding=encoding) as f:
                yield f

        # Atomic rename (on POSIX; Windows may need to remove first)
        if os.name == "nt" and path.exists():
            path.unlink()
        tmp_path.rename(path)

    except Exception:
        # Clean up temp file on failure
        if tmp_path.exists():
            tmp_path.unlink()
        raise


@contextmanager
def locked_atomic_write(path: Path, mode: str = "w", encoding: str = "utf-8", timeout: float = 10.0) -> Generator:
    """Combine file lock with atomic write for full safety.

    Args:
        path: Target file path
        mode: Write mode
        encoding: Text encoding
        timeout: Lock timeout in seconds

    Yields:
        File handle for writing
    """
    with file_lock(path, timeout=timeout):
        with atomic_write(path, mode=mode, encoding=encoding) as f:
            yield f
