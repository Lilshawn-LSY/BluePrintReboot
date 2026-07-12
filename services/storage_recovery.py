from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.contact import APP_VERSION
from storage.atomic_json import atomic_write_json


class StorageRecoveryError(RuntimeError):
    pass


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _available(directory: Path, name: str) -> Path:
    candidate = directory / name
    suffix = 2
    while candidate.exists() or candidate.with_suffix(candidate.suffix + ".manifest.json").exists():
        candidate = directory / f"{Path(name).stem}_{suffix}{Path(name).suffix}"
        suffix += 1
    return candidate


def _copy_manifest_path(copy_path: Path) -> Path:
    return copy_path.with_suffix(copy_path.suffix + ".manifest.json")


def export_recovery_copy(
    source: str | Path,
    *,
    workspace_root: str | Path,
    recovery_dir: str | Path,
    storage_class: str,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    source_path = Path(source).resolve(strict=False)
    root = Path(workspace_root).resolve(strict=False)
    if not _within(source_path, root):
        raise StorageRecoveryError("Recovery is restricted to app-owned workspace paths.")
    if not source_path.is_file():
        raise StorageRecoveryError("The diagnosed source file is absent or is not a regular file.")
    output_dir = Path(recovery_dir).resolve(strict=False)
    if not _within(output_dir, root):
        raise StorageRecoveryError("Recovery output is restricted to the workspace.")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now(now)
    relative = source_path.relative_to(root).as_posix()
    safe_name = relative.replace("/", "__").replace("\\", "__")
    destination = _available(output_dir, f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}__{safe_name}")
    try:
        with source_path.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        source_sha = _sha256(source_path)
        copy_sha = _sha256(destination)
        source_size = source_path.stat().st_size
        if source_sha != copy_sha or source_size != destination.stat().st_size:
            raise StorageRecoveryError("Recovery copy verification failed.")
        manifest = {
            "original_path": str(source_path),
            "workspace_relative_path": relative,
            "storage_class": storage_class,
            "byte_size": source_size,
            "sha256": source_sha,
            "operation_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "app_version": APP_VERSION,
            "reason": reason,
            "copy_path": str(destination),
        }
        manifest_path = _copy_manifest_path(destination)
        atomic_write_json(manifest_path, manifest, indent=2, ensure_ascii=False, trailing_newline=True)
    except Exception:
        if destination.exists():
            destination.unlink()
        manifest_path = _copy_manifest_path(destination)
        if manifest_path.exists():
            manifest_path.unlink()
        raise
    return {"copy_path": str(destination), "manifest_path": str(manifest_path), "manifest": manifest}


def quarantine_file(
    source: str | Path,
    *,
    workspace_root: str | Path,
    quarantine_dir: str | Path,
    storage_class: str,
    reason: str,
    rebuildable: bool,
    confirm: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    source_path = Path(source).resolve(strict=False)
    if not confirm:
        raise StorageRecoveryError("Quarantine requires explicit confirmation.")
    if not rebuildable:
        raise StorageRecoveryError("Quarantine is allowed by default only for rebuildable caches.")
    if not source_path.exists():
        return {"status": "already_absent", "original_path": str(source_path)}
    exported = export_recovery_copy(
        source_path,
        workspace_root=workspace_root,
        recovery_dir=quarantine_dir,
        storage_class=storage_class,
        reason=reason,
        now=now,
    )
    copy_path = Path(exported["copy_path"])
    if _sha256(copy_path) != exported["manifest"]["sha256"]:
        raise StorageRecoveryError("Quarantine verification failed; the active file was preserved.")
    if not source_path.is_file() or _sha256(source_path) != exported["manifest"]["sha256"] or source_path.stat().st_size != exported["manifest"]["byte_size"]:
        raise StorageRecoveryError("The active file changed during quarantine; it was preserved.")
    source_path.unlink()
    return {"status": "quarantined", "original_path": str(source_path), **exported}


def restore_quarantined_file(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    confirm: bool,
) -> dict[str, Any]:
    if not confirm:
        raise StorageRecoveryError("Restore requires explicit confirmation.")
    manifest_file = Path(manifest_path).resolve(strict=False)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageRecoveryError(f"Quarantine manifest could not be read: {exc}") from exc
    if not isinstance(manifest, dict):
        raise StorageRecoveryError("Quarantine manifest must contain a JSON object.")
    root = Path(workspace_root).resolve(strict=False)
    destination = Path(str(manifest.get("original_path", ""))).resolve(strict=False)
    copy_path = Path(str(manifest.get("copy_path", ""))).resolve(strict=False)
    if not _within(manifest_file, root) or not _within(copy_path, root) or _copy_manifest_path(copy_path).resolve(strict=False) != manifest_file:
        raise StorageRecoveryError("Restore requires a matching workspace-owned quarantine copy and manifest.")
    if not _within(destination, root):
        raise StorageRecoveryError("Restore destination is outside the workspace.")
    if destination.exists():
        raise StorageRecoveryError("Restore conflict: the active destination already exists.")
    if not copy_path.is_file() or _sha256(copy_path) != str(manifest.get("sha256", "")):
        raise StorageRecoveryError("Quarantine bytes do not match the manifest.")
    try:
        expected_size = int(manifest.get("byte_size", -1))
    except (TypeError, ValueError) as exc:
        raise StorageRecoveryError("Quarantine manifest byte size is invalid.") from exc
    if copy_path.stat().st_size != expected_size:
        raise StorageRecoveryError("Quarantine byte size does not match the manifest.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.restore.tmp")
    try:
        with copy_path.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        if _sha256(temporary) != manifest["sha256"]:
            raise StorageRecoveryError("Restored temporary bytes failed verification.")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"status": "restored", "destination_path": str(destination), "quarantine_copy_retained": True}
