from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from config.contact import APP_VERSION
from storage.paths import EXPORTS_DIR, PROJECT_ROOT


IGNORED_NAMES = {".git", ".pytest_cache", ".venv", "__pycache__", "venv"}
TAG_CONFIG_FILES = ("config/tag_rules.json", "config/canonical_tags.json")
LOCAL_SETTING_FILES = (".streamlit/config.toml", "config/settings.json", "data/settings.json")


def _timestamp(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _is_ignored(path: Path, project_root: Path) -> bool:
    relative = path.relative_to(project_root)
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return True
    return any(part in IGNORED_NAMES for part in relative.parts) or path.name == ".gitkeep"


def _files_under(directory: Path, project_root: Path, *, pdf_only: bool = False) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    files: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or _is_ignored(path, project_root):
            continue
        if pdf_only and path.suffix.lower() != ".pdf":
            continue
        files.append(path)
    return files


def collect_snapshot_files(
    project_root: Path = PROJECT_ROOT,
    *,
    include_pdfs: bool = False,
) -> list[Path]:
    project_root = Path(project_root).resolve()
    candidates: list[Path] = []
    index_path = project_root / "data" / "paper_index.csv"
    if index_path.is_file():
        candidates.append(index_path)
    for relative_directory in ("data/projects", "notes", "data/note_blocks"):
        candidates.extend(_files_under(project_root / relative_directory, project_root))
    for relative_file in (*TAG_CONFIG_FILES, *LOCAL_SETTING_FILES):
        path = project_root / relative_file
        if path.is_file() and not _is_ignored(path, project_root):
            candidates.append(path)
    if include_pdfs:
        candidates.extend(_files_under(project_root / "papers", project_root, pdf_only=True))
    return sorted(set(candidates), key=lambda path: path.relative_to(project_root).as_posix().lower())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_list_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return len(value) if isinstance(value, list) else 0


def _csv_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return sum(1 for _ in csv.DictReader(source))
    except OSError:
        return 0


def build_snapshot_manifest(
    files: list[Path],
    project_root: Path,
    *,
    include_pdfs: bool,
    created_at: datetime,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    included_files = [
        {
            "path": path.relative_to(project_root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in files
    ]
    paths = {item["path"] for item in included_files}
    return {
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "app_version": APP_VERSION,
        "snapshot_type": "full" if include_pdfs else "light",
        "includes_pdfs": include_pdfs,
        "included_files": included_files,
        "counts": {
            "included_files": len(included_files),
            "index_rows": _csv_row_count(project_root / "data" / "paper_index.csv"),
            "projects": _json_list_count(project_root / "data" / "projects" / "projects.json"),
            "project_links": _json_list_count(project_root / "data" / "projects" / "project_links.json"),
            "notes": sum(path.startswith("notes/") for path in paths),
            "note_block_files": sum(path.startswith("data/note_blocks/") for path in paths),
            "pdfs": sum(path.startswith("papers/") for path in paths),
        },
    }


def _available_snapshot_path(exports_dir: Path, base_name: str) -> Path:
    candidate = exports_dir / f"{base_name}.zip"
    suffix = 2
    while candidate.exists():
        candidate = exports_dir / f"{base_name}_{suffix}.zip"
        suffix += 1
    return candidate


def create_backup_snapshot(
    *,
    include_pdfs: bool = False,
    project_root: Path = PROJECT_ROOT,
    exports_dir: Path = EXPORTS_DIR,
    now: datetime | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    exports_dir = Path(exports_dir).resolve()
    exports_dir.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp(now)
    snapshot_type = "full" if include_pdfs else "light"
    base_name = f"blueprint_snapshot_{created_at.strftime('%Y%m%dT%H%M%SZ')}_{snapshot_type}"
    snapshot_path = _available_snapshot_path(exports_dir, base_name)
    files = collect_snapshot_files(project_root, include_pdfs=include_pdfs)
    manifest = build_snapshot_manifest(
        files,
        project_root,
        include_pdfs=include_pdfs,
        created_at=created_at,
    )

    try:
        with ZipFile(snapshot_path, mode="x", compression=ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, arcname=path.relative_to(project_root).as_posix())
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    except Exception:
        if snapshot_path.exists():
            snapshot_path.unlink()
        raise
    return {
        "snapshot_path": str(snapshot_path),
        "manifest": manifest,
    }
