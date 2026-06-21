from __future__ import annotations

import os
from pathlib import Path


def get_inbox_path(user_value: str | Path | None = None) -> Path | None:
    environment_value = os.environ.get("BLUEPRINT_INBOX_DIR", "").strip()
    value = environment_value or str(user_value or "").strip()
    return Path(value).expanduser() if value else None
