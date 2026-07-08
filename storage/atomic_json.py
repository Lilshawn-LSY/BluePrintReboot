from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_JSON_RECOVERY_ACTION = (
    "Do not overwrite this file. Restore it from a known-good backup snapshot or make a copy "
    "and repair the JSON manually before using related write actions."
)

_MISSING = object()


class JsonStoreError(ValueError):
    def __init__(
        self,
        path: str | Path,
        summary: str,
        *,
        suggested_action: str = DEFAULT_JSON_RECOVERY_ACTION,
        original_error: BaseException | None = None,
    ) -> None:
        self.path = Path(path)
        self.summary = str(summary)
        self.suggested_action = str(suggested_action)
        self.original_error = original_error
        super().__init__(f"{self.summary}: {self.path}")


class CorruptJsonError(JsonStoreError):
    pass


class JsonShapeError(JsonStoreError):
    pass


def atomic_write_json(
    path: str | Path,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    trailing_newline: bool = False,
) -> Path:
    target = Path(path)
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    if trailing_newline:
        text += "\n"

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
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
        os.replace(temporary_path, target)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return target


def read_json_file(
    path: str | Path,
    *,
    default: Any = _MISSING,
    store_name: str = "JSON file",
) -> Any:
    target = Path(path)
    if not target.exists():
        if default is _MISSING:
            raise FileNotFoundError(target)
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorruptJsonError(
            target,
            f"{store_name} is invalid JSON",
            original_error=exc,
        ) from exc
    except OSError as exc:
        raise JsonStoreError(
            target,
            f"{store_name} could not be read",
            suggested_action="Check file permissions and disk availability, then retry. Do not overwrite the file.",
            original_error=exc,
        ) from exc


def require_json_list(value: Any, path: str | Path, *, store_name: str = "JSON file") -> list[Any]:
    if not isinstance(value, list):
        raise JsonShapeError(Path(path), f"{store_name} must contain a JSON list")
    return value


def json_store_issue(error: JsonStoreError, *, severity: str = "error") -> dict[str, str]:
    return {
        "severity": severity,
        "category": "storage",
        "path": str(error.path.resolve(strict=False)),
        "issue": error.summary,
        "suggested_action": error.suggested_action,
    }
