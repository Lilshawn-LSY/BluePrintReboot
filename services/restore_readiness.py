from __future__ import annotations

from pathlib import Path
from typing import Any

from services.backup_snapshot import verify_backup_snapshot


def check_disposable_restore_target(
    snapshot_path: str | Path,
    target_dir: str | Path,
    *,
    protected_root: str | Path,
) -> dict[str, Any]:
    snapshot = Path(snapshot_path).resolve(strict=False)
    target = Path(target_dir).resolve(strict=False)
    protected = Path(protected_root).resolve(strict=False)
    errors: list[str] = []
    verification = verify_backup_snapshot(snapshot)
    entries: list[str] | None = None
    if not verification["valid"]:
        errors.append("Snapshot verification failed.")
    if not target.exists() or not target.is_dir():
        errors.append("Disposable restore target must already exist as a directory.")
    else:
        try:
            entries = sorted(path.name for path in target.iterdir())
        except OSError as exc:
            errors.append(f"Disposable restore target could not be inspected: {exc}")
            entries = []
        if entries:
            errors.append("Disposable restore target must be empty.")
    try:
        target.relative_to(protected)
    except ValueError:
        pass
    else:
        errors.append("Disposable restore target must be outside the active repository.")
    try:
        protected.relative_to(target)
    except ValueError:
        pass
    else:
        errors.append("Disposable restore target must not contain the active repository.")
    return {
        "ready": not errors,
        "snapshot_valid": bool(verification["valid"]),
        "snapshot_path": str(snapshot),
        "target_path": str(target),
        "target_empty": entries == [],
        "checked_files": int(verification.get("checked_files", 0)),
        "errors": errors,
        "read_only": True,
        "next_action": "Manually extract a copy of the snapshot into this disposable target." if not errors else "Resolve every reported issue before any manual extraction.",
    }
