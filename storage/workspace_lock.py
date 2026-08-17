from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path


_LOCK_TIMEOUT_SECONDS = 10.0
_PROCESS_LOCK = threading.RLock()
_HELD_LOCKS = threading.local()
_WORKSPACE_GENERATIONS: dict[str, int] = {}


class WorkspaceLockUnavailable(OSError):
    """A local workspace write lock could not be acquired safely."""


def workspace_root_for_path(path: Path) -> Path:
    """Infer the workspace root for one app-owned file or directory path."""

    resolved = Path(path).resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        if candidate.name.casefold() in {"data", "notes", "papers", "config", "exports"}:
            return candidate.parent
    return resolved.parent


def workspace_state_generation(workspace_root: Path) -> int:
    root = Path(workspace_root).resolve(strict=False)
    lock_key = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()
    with _PROCESS_LOCK:
        return _WORKSPACE_GENERATIONS.get(lock_key, 0)


@contextmanager
def workspace_write_lock(workspace_root: Path):
    """Serialize one workspace write section across threads and local processes."""

    root = Path(workspace_root).resolve(strict=False)
    lock_key = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"blueprint-workspace-{lock_key}.lock"
    with _PROCESS_LOCK:
        held = getattr(_HELD_LOCKS, "counts", None)
        if held is None:
            held = {}
            _HELD_LOCKS.counts = held
        if held.get(lock_key, 0):
            held[lock_key] += 1
            try:
                yield
            finally:
                held[lock_key] -= 1
            return

        try:
            handle = lock_path.open("a+b")
        except OSError:
            raise WorkspaceLockUnavailable from None

        try:
            if os.name == "nt":
                import msvcrt

                try:
                    handle.seek(0, os.SEEK_END)
                    if handle.tell() == 0:
                        handle.write(b"\0")
                        handle.flush()
                    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
                    while True:
                        handle.seek(0)
                        try:
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise WorkspaceLockUnavailable from None
                            time.sleep(0.05)
                except WorkspaceLockUnavailable:
                    raise
                except OSError:
                    raise WorkspaceLockUnavailable from None

                held[lock_key] = 1
                try:
                    yield
                finally:
                    held.pop(lock_key, None)
                    _WORKSPACE_GENERATIONS[lock_key] = _WORKSPACE_GENERATIONS.get(lock_key, 0) + 1
                    try:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
            else:
                import fcntl

                deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
                while True:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise WorkspaceLockUnavailable from None
                        time.sleep(0.05)

                held[lock_key] = 1
                try:
                    yield
                finally:
                    held.pop(lock_key, None)
                    _WORKSPACE_GENERATIONS[lock_key] = _WORKSPACE_GENERATIONS.get(lock_key, 0) + 1
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        finally:
            handle.close()
