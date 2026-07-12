from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.atomic_json import atomic_write_json, read_json_file, require_json_list
from storage.paths import LIFECYCLE_DECISIONS_JSON, PROJECT_ROOT


def _relative(path: str | Path, workspace_root: str | Path) -> str:
    candidate = Path(path).resolve(strict=False)
    root = Path(workspace_root).resolve(strict=False)
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Lifecycle decisions are restricted to workspace-relative paths.") from exc


def load_duplicate_decisions(path: Path = LIFECYCLE_DECISIONS_JSON) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    return [item for item in require_json_list(read_json_file(path, store_name="Lifecycle decision store"), path, store_name="Lifecycle decision store") if isinstance(item, dict)]


def ignore_exact_duplicate(
    filepath: str | Path,
    pdf_sha256: str,
    *,
    size_bytes: int,
    modified_at: str,
    decision_path: Path = LIFECYCLE_DECISIONS_JSON,
    workspace_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    relative = _relative(filepath, workspace_root)
    decisions = load_duplicate_decisions(decision_path)
    decision = {
        "decision_type": "ignore_exact_duplicate",
        "workspace_relative_path": relative,
        "pdf_sha256": str(pdf_sha256),
        "size_bytes": int(size_bytes),
        "modified_at": str(modified_at),
        "decided_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    decisions = [item for item in decisions if not (item.get("decision_type") == decision["decision_type"] and item.get("workspace_relative_path") == relative)]
    decisions.append(decision)
    atomic_write_json(decision_path, decisions, indent=2, ensure_ascii=False, trailing_newline=True)
    return decision


def is_exact_duplicate_ignored(filepath: str | Path, pdf_sha256: str, *, decision_path: Path = LIFECYCLE_DECISIONS_JSON, workspace_root: Path = PROJECT_ROOT) -> bool:
    relative = _relative(filepath, workspace_root)
    return any(item.get("decision_type") == "ignore_exact_duplicate" and item.get("workspace_relative_path") == relative and item.get("pdf_sha256") == pdf_sha256 for item in load_duplicate_decisions(decision_path))


def unignore_exact_duplicate(filepath: str | Path, *, decision_path: Path = LIFECYCLE_DECISIONS_JSON, workspace_root: Path = PROJECT_ROOT) -> bool:
    relative = _relative(filepath, workspace_root)
    decisions = load_duplicate_decisions(decision_path)
    retained = [item for item in decisions if not (item.get("decision_type") == "ignore_exact_duplicate" and item.get("workspace_relative_path") == relative)]
    if len(retained) == len(decisions):
        return False
    atomic_write_json(decision_path, retained, indent=2, ensure_ascii=False, trailing_newline=True)
    return True
