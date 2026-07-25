from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.reconcile_release_state import CONTROLLED_STATUS_SET, validate_manifest


DEFAULT_INPUT = PROJECT_ROOT / "docs" / "tracker_sync_status.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "tracker_status.csv"
CSV_COLUMNS = ("task_id", "status", "evidence", "disposition", "last_verified")
ALLOWED_TASK_STATUSES = CONTROLLED_STATUS_SET
TASK_ID = re.compile(r"R-\d{3}")
PRIVATE_VALUE_PATTERNS = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),
    re.compile(r"/(?:Users|home)/", re.IGNORECASE),
    re.compile(r"\$env:|os\.environ|%[A-Za-z_][A-Za-z0-9_]*%", re.IGNORECASE),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
)
PRIVATE_EVIDENCE_TERMS = (
    "paper_id",
    "paper title",
    "doi",
    "author",
    "note content",
)


def load_tracker(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require_safe_text(value: object, field: str, task_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{task_id}.{field} must be a non-empty string")
    text = value.strip()
    if any(pattern.search(text) for pattern in PRIVATE_VALUE_PATTERNS):
        raise ValueError(f"{task_id}.{field} contains a private path, environment value, or email address")
    if field == "evidence" and any(term in text.casefold() for term in PRIVATE_EVIDENCE_TERMS):
        raise ValueError(f"{task_id}.{field} contains private-library terminology")
    return text


def validated_rows(tracker: dict[str, Any]) -> list[dict[str, str]]:
    validate_manifest(tracker)
    section = tracker.get("external_tracker")
    if not isinstance(section, dict) or section.get("schema_version") != "2.0":
        raise ValueError("external_tracker.schema_version must be 2.0")
    if section.get("status_values") != list(tracker["controlled_statuses"]):
        raise ValueError("external_tracker.status_values must list the controlled statuses")
    tasks = section.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("external_tracker.tasks must be a non-empty list")

    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != set(CSV_COLUMNS):
            raise ValueError(f"each external tracker task must contain exactly: {', '.join(CSV_COLUMNS)}")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or TASK_ID.fullmatch(task_id) is None:
            raise ValueError("external tracker task_id must match R-000")
        if task_id in seen_ids:
            raise ValueError(f"duplicate external tracker task_id: {task_id}")
        seen_ids.add(task_id)

        status = task.get("status")
        if status not in ALLOWED_TASK_STATUSES:
            raise ValueError(f"{task_id}.status is not controlled: {status!r}")
        evidence = _require_safe_text(task.get("evidence"), "evidence", task_id)
        disposition = _require_safe_text(task.get("disposition"), "disposition", task_id)
        last_verified = _require_safe_text(task.get("last_verified"), "last_verified", task_id)
        try:
            date.fromisoformat(last_verified)
        except ValueError as exc:
            raise ValueError(f"{task_id}.last_verified must be an ISO date") from exc

        rows.append(
            {
                "task_id": task_id,
                "status": status,
                "evidence": evidence,
                "disposition": disposition,
                "last_verified": last_verified,
            }
        )

    return sorted(rows, key=lambda row: row["task_id"])


def tracker_csv_bytes(tracker: dict[str, Any]) -> bytes:
    rows = validated_rows(tracker)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def export_tracker_status(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> Path:
    content = tracker_csv_bytes(load_tracker(input_path))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the canonical external tracker handoff as deterministic CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        destination = export_tracker_status(args.input, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Tracker export failed: {exc}")
        return 1
    print("Tracker status CSV written successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
