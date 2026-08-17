from __future__ import annotations

import unicodedata
from pathlib import PurePosixPath, PureWindowsPath


MAX_PAPER_ID_LENGTH = 200
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def is_safe_paper_id(value: object) -> bool:
    """Return whether a paper identity is safe as one cross-platform filename component."""

    if not isinstance(value, str) or not value or len(value) > MAX_PAPER_ID_LENGTH:
        return False
    if value in {".", ".."} or value != value.strip() or value.endswith((".", " ")):
        return False
    if "/" in value or "\\" in value or ":" in value:
        return False
    if any(unicodedata.category(character) == "Cc" for character in value):
        return False
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        return False

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    return (
        not posix_path.is_absolute()
        and not windows_path.is_absolute()
        and not windows_path.drive
        and not windows_path.root
        and posix_path.parts == (value,)
        and windows_path.parts == (value,)
    )


def require_safe_paper_id(value: object) -> str:
    if not is_safe_paper_id(value):
        raise ValueError("paper_id must be a safe, non-empty filename identity.")
    return str(value)
