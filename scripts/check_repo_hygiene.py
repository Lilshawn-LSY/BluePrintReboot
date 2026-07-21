from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRIVATE_RUNTIME_PREFIXES = (
    ".pytest_cache/",
    ".streamlit/",
    ".venv/",
    "artifacts/",
    "frontend/node_modules/",
    "tests/_tmp/",
    "venv/",
)
PRIVATE_DATA_DIRECTORIES = {"data", "exports", "notes", "papers"}
ALLOWED_PRIVATE_PLACEHOLDERS = {
    "data/.gitkeep",
    "exports/.gitkeep",
    "notes/.gitkeep",
    "papers/.gitkeep",
}
ROOT_LOG_SUFFIXES = {".err", ".log", ".out", ".trace"}
GENERATED_EVIDENCE_NAME = re.compile(
    r"^(?:dev[-_]check[-_]evidence|pytest[-_]results?|smoke[-_]results?|"
    r"validation[-_](?:evidence|summary))(?:[-_.].*)?$",
    re.IGNORECASE,
)
SHELL_FLAG = re.compile(r"(?:^|\s)--?[a-z0-9][a-z0-9-]*(?:$|\s)", re.IGNORECASE)
COMMAND_FRAGMENT = re.compile(
    r"\b(?:git\s+(?:diff|log|show|status)|npm\s+(?:ci|run|test)|"
    r"python\s+-m|pytest(?:\s|$)|powershell\s+-|pwsh\s+-)\b",
    re.IGNORECASE,
)
SHELL_METACHARACTERS = re.compile(r"(?:&&|\|\||[<>]|\$\(|`)")


@dataclass(frozen=True)
class HygieneViolation:
    path: str
    reason: str


def list_tracked_entries(project_root: Path) -> list[str]:
    """Return repository-relative tracked paths without reading file contents."""
    root = Path(project_root).resolve()
    completed = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false", "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail or 'unknown Git error'}")
    entries = [
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    return [
        entry
        for entry in entries
        if (root.joinpath(*PurePosixPath(entry).parts).exists() or root.joinpath(*PurePosixPath(entry).parts).is_symlink())
    ]


def inspect_tracked_entries(entries: Iterable[str]) -> list[HygieneViolation]:
    violations: list[HygieneViolation] = []
    for raw_entry in entries:
        entry = raw_entry.replace("\\", "/")
        while entry.startswith("./"):
            entry = entry[2:]
        path = PurePosixPath(entry)
        basename = path.name
        lower_entry = entry.casefold()
        lower_basename = basename.casefold()

        if lower_entry == "tatus --short":
            violations.append(HygieneViolation(entry, "known accidental command-output artifact"))
            continue

        if entry in ALLOWED_PRIVATE_PLACEHOLDERS:
            continue

        top_level = path.parts[0].casefold() if path.parts else ""
        if top_level in PRIVATE_DATA_DIRECTORIES:
            violations.append(HygieneViolation(entry, "tracked private runtime/user-data path"))
            continue

        if any(lower_entry.startswith(prefix.casefold()) for prefix in PRIVATE_RUNTIME_PREFIXES):
            reason = (
                "generated validation evidence belongs under the ignored artifacts/ directory"
                if lower_entry.startswith("artifacts/")
                else "tracked private runtime or dependency path"
            )
            violations.append(HygieneViolation(entry, reason))
            continue

        if len(path.parts) == 1 and path.suffix.casefold() in ROOT_LOG_SUFFIXES:
            violations.append(HygieneViolation(entry, "unexpected tracked root log/output artifact"))
            continue

        if GENERATED_EVIDENCE_NAME.fullmatch(lower_basename):
            violations.append(
                HygieneViolation(
                    entry,
                    "generated validation evidence belongs under the ignored artifacts/ directory",
                )
            )
            continue

        if SHELL_FLAG.search(basename) or COMMAND_FRAGMENT.search(basename) or SHELL_METACHARACTERS.search(basename):
            violations.append(HygieneViolation(entry, "suspicious filename contains a shell flag or command fragment"))

    return sorted(violations, key=lambda violation: (violation.path.casefold(), violation.reason))


def check_repository(project_root: Path) -> tuple[list[str], list[HygieneViolation]]:
    entries = list_tracked_entries(project_root)
    return entries, inspect_tracked_entries(entries)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate tracked repository filenames without reading ignored or user-data contents."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)

    try:
        entries, violations = check_repository(args.project_root)
    except RuntimeError as exc:
        print(f"Repository hygiene check failed: {exc}")
        return 1

    if violations:
        print("Repository hygiene check failed:")
        for violation in violations:
            print(f"- {violation.path}: {violation.reason}")
        return 1

    print(f"Repository hygiene check passed: {len(entries)} tracked entries inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
