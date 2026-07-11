from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from config.contact import APP_VERSION
from storage.paths import EXPORTS_DIR, PROJECT_ROOT


IGNORED_NAMES = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
IGNORED_FILE_NAMES = {"secrets.toml"}
IGNORED_SUFFIXES = {".log", ".tmp"}
TAG_CONFIG_FILES = (
    "config/tag_rules.json",
    "config/canonical_tags.json",
    "config/tag_book/tag_book.json",
    "config/tag_book/method_lexicon.json",
    "config/tag_book/normalization_rules.json",
    "config/tag_book/blocked_terms.json",
    "config/tag_book/candidate_patterns.json",
)
LOCAL_SETTING_FILES = (".streamlit/config.toml", "config/settings.json", "data/settings.json")
LOCAL_LIBRARY_FILES = ("data/note_imports.json",)
SNAPSHOT_INCLUDED_BY_DEFAULT = (
    "data/paper_index.csv",
    "data/projects/",
    "data/note_blocks/",
    "data/note_imports.json",
    "notes/",
    "config/tag_rules.json",
    "config/canonical_tags.json",
    "config/tag_book/",
    ".streamlit/config.toml",
)
SNAPSHOT_EXCLUDED_BY_DEFAULT = (
    ".git/",
    ".venv/",
    "venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".cache/",
    "node_modules/",
    "exports/",
    "data/extracted_text/",
    "data/paper_profiles/",
    ".streamlit/secrets.toml",
    "*.log",
    "*.tmp",
)


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
    return (
        any(part in IGNORED_NAMES for part in relative.parts)
        or path.name in IGNORED_FILE_NAMES
        or path.name == ".gitkeep"
        or path.suffix.lower() in IGNORED_SUFFIXES
    )


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
    for relative_file in (*TAG_CONFIG_FILES, *LOCAL_SETTING_FILES, *LOCAL_LIBRARY_FILES):
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
        "policy": {
            "purpose": "Backup private local library data. Source code remains in GitHub.",
            "included_by_default": list(SNAPSHOT_INCLUDED_BY_DEFAULT),
            "extra_when_full": ["papers/**/*.pdf"],
            "excluded_by_default": list(SNAPSHOT_EXCLUDED_BY_DEFAULT),
            "extracted_text_cache": {
                "included": False,
                "reason": "Extracted text and paper profile caches are regenerable and excluded from conservative snapshots.",
            },
            "restore": "Manual restore only; create or inspect backups before repair actions.",
        },
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


def _safe_snapshot_member_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and all(part not in ("", ".", "..") for part in path.parts)
        and ":" not in path.parts[0]
    )


def _json_list_count_bytes(content: bytes) -> int | None:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return len(value) if isinstance(value, list) else None


def _csv_row_count_bytes(content: bytes) -> int | None:
    try:
        lines = content.decode("utf-8-sig").splitlines()
        return sum(1 for _ in csv.DictReader(lines))
    except (UnicodeDecodeError, csv.Error):
        return None


def verify_backup_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
    """Verify a snapshot in place without extracting or modifying library data."""
    path = Path(snapshot_path)
    errors: list[str] = []
    manifest: dict[str, Any] | None = None
    checked_files = 0
    try:
        with ZipFile(path, mode="r") as archive:
            names = archive.namelist()
            name_set = set(names)
            if len(names) != len(name_set):
                errors.append("Archive contains duplicate member paths.")
            for name in names:
                if not _safe_snapshot_member_path(name):
                    errors.append(f"Archive member path is unsafe: {name!r}.")
            if "manifest.json" not in name_set:
                errors.append("manifest.json is missing from the archive root.")
            else:
                try:
                    loaded_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"manifest.json is not valid UTF-8 JSON: {exc}.")
                else:
                    if isinstance(loaded_manifest, dict):
                        manifest = loaded_manifest
                    else:
                        errors.append("manifest.json must contain a JSON object.")

            if manifest is not None:
                snapshot_type = manifest.get("snapshot_type")
                includes_pdfs = manifest.get("includes_pdfs")
                if snapshot_type not in ("light", "full"):
                    errors.append("snapshot_type must be 'light' or 'full'.")
                if type(includes_pdfs) is not bool:
                    errors.append("includes_pdfs must be a boolean.")
                elif snapshot_type in ("light", "full") and (snapshot_type == "full") != includes_pdfs:
                    errors.append("snapshot_type and includes_pdfs are inconsistent.")

                entries = manifest.get("included_files")
                if not isinstance(entries, list):
                    errors.append("included_files must be a list.")
                    entries = []
                listed_paths: list[str] = []
                content_by_path: dict[str, bytes] = {}
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        errors.append(f"included_files[{index}] must be an object.")
                        continue
                    member_path = entry.get("path")
                    if not _safe_snapshot_member_path(member_path):
                        errors.append(f"Included file path is unsafe at index {index}: {member_path!r}.")
                        continue
                    listed_paths.append(member_path)
                    if member_path not in name_set:
                        errors.append(f"Listed file is missing from the archive: {member_path}.")
                        continue
                    content = archive.read(member_path)
                    content_by_path[member_path] = content
                    checked_files += 1
                    size_bytes = entry.get("size_bytes")
                    if type(size_bytes) is not int or size_bytes < 0:
                        errors.append(f"Invalid size_bytes for {member_path}.")
                    elif size_bytes != len(content):
                        errors.append(f"size_bytes mismatch for {member_path}.")
                    expected_sha256 = entry.get("sha256")
                    actual_sha256 = hashlib.sha256(content).hexdigest()
                    if not isinstance(expected_sha256, str) or expected_sha256.lower() != actual_sha256:
                        errors.append(f"sha256 mismatch for {member_path}.")

                if len(listed_paths) != len(set(listed_paths)):
                    errors.append("included_files contains duplicate paths.")
                unlisted = name_set - {"manifest.json", *listed_paths}
                if unlisted:
                    errors.append(f"Archive contains unlisted files: {', '.join(sorted(unlisted))}.")
                if includes_pdfs is False and any(item.startswith("papers/") for item in listed_paths):
                    errors.append("A light snapshot must not list files under papers/.")

                computed_counts: dict[str, int | None] = {
                    "included_files": len(entries),
                    "index_rows": _csv_row_count_bytes(content_by_path["data/paper_index.csv"])
                    if "data/paper_index.csv" in content_by_path
                    else 0,
                    "projects": _json_list_count_bytes(content_by_path["data/projects/projects.json"])
                    if "data/projects/projects.json" in content_by_path
                    else 0,
                    "project_links": _json_list_count_bytes(content_by_path["data/projects/project_links.json"])
                    if "data/projects/project_links.json" in content_by_path
                    else 0,
                    "notes": sum(item.startswith("notes/") for item in listed_paths),
                    "note_block_files": sum(item.startswith("data/note_blocks/") for item in listed_paths),
                    "pdfs": sum(item.startswith("papers/") for item in listed_paths),
                }
                counts = manifest.get("counts")
                if not isinstance(counts, dict):
                    errors.append("counts must be an object.")
                else:
                    for count_name, expected_count in computed_counts.items():
                        actual_count = counts.get(count_name)
                        if expected_count is None:
                            errors.append(f"Could not validate {count_name} from its archived file.")
                        elif type(actual_count) is not int or actual_count != expected_count:
                            errors.append(
                                f"counts.{count_name} mismatch: expected {expected_count}, found {actual_count!r}."
                            )
    except (OSError, BadZipFile) as exc:
        errors.append(f"Snapshot archive could not be read: {exc}.")

    return {
        "valid": not errors,
        "snapshot_path": str(path),
        "checked_files": checked_files,
        "errors": errors,
        "manifest": manifest,
    }
