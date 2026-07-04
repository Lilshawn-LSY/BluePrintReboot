from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    "README.md",
    "docs/BLUEPRINT_PRINCIPLES.md",
    "docs/ROADMAP.md",
    "docs/BACKLOG.md",
    "docs/DEV_WORKFLOW.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/templates/blueprint_reading_note_template.md",
    "config/tag_rules.json",
    "config/canonical_tags.json",
    "docs/checklists/v1.0_smoke_test.md",
    "docs/checklists/new_pc_restore_checklist.md",
    "docs/release_notes/v1.0_draft.md",
)
REQUIRED_DIRECTORIES = ("data", "papers", "notes", "exports")
REQUIRED_DEPENDENCIES = {
    "pandas": "pandas",
    "streamlit": "streamlit",
    "requests": "requests",
    "urllib3": "urllib3",
    "certifi": "certifi",
    "pypdf": "pypdf",
}
KEY_MODULES = (
    "ui_streamlit.app",
    "storage.index_store",
    "services.backup_snapshot",
    "services.library_health",
    "services.metadata_fallback",
    "services.note_import",
    "services.pdf_inbox",
    "services.paper_file_hygiene",
    "services.reading_note_template",
)


@dataclass(frozen=True)
class SmokeCheckResult:
    name: str
    status: str
    detail: str


def check_required_paths(project_root: Path) -> list[SmokeCheckResult]:
    project_root = Path(project_root).resolve()
    results: list[SmokeCheckResult] = []
    for relative_path in REQUIRED_FILES:
        path = project_root / relative_path
        status = "pass" if path.is_file() and os.access(path, os.R_OK) else "fail"
        detail = "readable" if status == "pass" else "missing or unreadable"
        results.append(SmokeCheckResult(f"file:{relative_path}", status, detail))
    for relative_path in REQUIRED_DIRECTORIES:
        path = project_root / relative_path
        status = "pass" if path.is_dir() and os.access(path, os.R_OK) else "fail"
        detail = "available" if status == "pass" else "missing or unreadable"
        results.append(SmokeCheckResult(f"directory:{relative_path}", status, detail))
    return results


def check_dependencies() -> list[SmokeCheckResult]:
    results: list[SmokeCheckResult] = []
    for module_name, distribution_name in REQUIRED_DEPENDENCIES.items():
        try:
            importlib.import_module(module_name)
            version = metadata.version(distribution_name)
        except Exception as exc:
            results.append(SmokeCheckResult(f"dependency:{distribution_name}", "fail", str(exc)))
        else:
            results.append(SmokeCheckResult(f"dependency:{distribution_name}", "pass", version))
    try:
        importlib.import_module("markitdown")
        version = metadata.version("markitdown")
    except Exception:
        results.append(
            SmokeCheckResult(
                "dependency:markitdown",
                "warn",
                "optional dependency is not installed; pypdf fallback remains available",
            )
        )
    else:
        results.append(SmokeCheckResult("dependency:markitdown", "pass", f"optional {version}"))
    return results


def check_module_imports() -> list[SmokeCheckResult]:
    results: list[SmokeCheckResult] = []
    for module_name in KEY_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            results.append(SmokeCheckResult(f"module:{module_name}", "fail", str(exc)))
        else:
            results.append(SmokeCheckResult(f"module:{module_name}", "pass", "imported"))
    return results


def check_manifest_contract(project_root: Path) -> SmokeCheckResult:
    try:
        from config.contact import APP_VERSION
        from services.backup_snapshot import build_snapshot_manifest

        manifest = build_snapshot_manifest(
            [],
            Path(project_root),
            include_pdfs=False,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        required_keys = {
            "created_at",
            "app_version",
            "snapshot_type",
            "includes_pdfs",
            "included_files",
            "counts",
        }
        required_counts = {
            "included_files",
            "index_rows",
            "projects",
            "project_links",
            "notes",
            "note_block_files",
            "pdfs",
        }
        if not required_keys <= set(manifest):
            raise ValueError("manifest top-level keys are incomplete")
        if not required_counts <= set(manifest["counts"]):
            raise ValueError("manifest count keys are incomplete")
        if manifest["app_version"] != APP_VERSION:
            raise ValueError("manifest app version does not match the runtime version")
    except Exception as exc:
        return SmokeCheckResult("backup:manifest-contract", "fail", str(exc))
    return SmokeCheckResult("backup:manifest-contract", "pass", f"schema valid for {APP_VERSION}")


def run_smoke_check(project_root: Path = PROJECT_ROOT) -> list[SmokeCheckResult]:
    project_root = Path(project_root).resolve()
    return [
        *check_required_paths(project_root),
        *check_dependencies(),
        *check_module_imports(),
        check_manifest_contract(project_root),
    ]


def _print_report(results: Sequence[SmokeCheckResult]) -> None:
    for result in results:
        print(f"[{result.status.upper():4}] {result.name}: {result.detail}")
    passed = sum(result.status == "pass" for result in results)
    warnings = sum(result.status == "warn" for result in results)
    failures = sum(result.status == "fail" for result in results)
    print(f"\nReadiness summary: {passed} passed, {warnings} warnings, {failures} failed.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run non-destructive BluePrintReboot readiness checks.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    results = run_smoke_check(args.project_root)
    _print_report(results)
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
