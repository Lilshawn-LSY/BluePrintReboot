from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable


ReplaceFile = Callable[[str | Path, str | Path], None]


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
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return target
