from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable


ReplaceFile = Callable[[str | Path, str | Path], None]


def fsync_parent_directory(path: str | Path) -> None:
    """Best-effort directory fsync after atomic publication.

    POSIX filesystems need the directory entry flushed separately from the file.
    Windows and some virtual filesystems do not support opening directories this
    way, so unsupported operations are deliberately ignored.
    """

    parent = Path(path).resolve(strict=False).parent
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(parent, flags)
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    replace_file: ReplaceFile | None = None,
) -> Path:
    """Write UTF-8 text through a flushed same-directory temporary file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    replace = replace_file or os.replace
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        replace(temporary_path, target)
        fsync_parent_directory(target)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return target
