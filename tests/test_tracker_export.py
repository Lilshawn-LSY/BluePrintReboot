import ast
import csv
import json
from pathlib import Path

import pytest

from scripts.export_tracker_status import (
    ALLOWED_TASK_STATUSES,
    CSV_COLUMNS,
    DEFAULT_OUTPUT,
    PROJECT_ROOT,
    export_tracker_status,
    main,
    validated_rows,
)


TRACKER_PATH = PROJECT_ROOT / "docs" / "tracker_sync_status.json"


def read_tracker() -> dict:
    return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))


def test_tracker_mapping_has_controlled_complete_drive_task_set() -> None:
    rows = validated_rows(read_tracker())

    assert [row["task_id"] for row in rows] == [f"R-{number:03d}" for number in range(1, 26)]
    assert {row["status"] for row in rows} <= ALLOWED_TASK_STATUSES
    assert next(row for row in rows if row["task_id"] == "R-006")["status"] == "PARTIAL"
    assert next(row for row in rows if row["task_id"] == "R-017")["status"] == "NOT VERIFIED"
    assert next(row for row in rows if row["task_id"] == "R-025")["status"] == "NOT VERIFIED"


def test_tracker_export_is_deterministic_utf8_csv(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    export_tracker_status(TRACKER_PATH, first)
    export_tracker_status(TRACKER_PATH, second)

    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(CSV_COLUMNS)
    with first.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 25
    assert [row["task_id"] for row in rows] == sorted(row["task_id"] for row in rows)


def test_tracker_export_contains_no_private_metadata_or_environment_values(tmp_path: Path) -> None:
    output = tmp_path / "tracker.csv"
    export_tracker_status(TRACKER_PATH, output)
    text = output.read_text(encoding="utf-8").casefold()

    for forbidden in (
        ":\\users\\",
        "/users/",
        "/home/",
        "$env:",
        "os.environ",
        "paper_id",
        "paper title",
        "doi",
        "author",
        "note content",
    ):
        assert forbidden not in text


def test_tracker_export_rejects_unknown_status() -> None:
    tracker = read_tracker()
    tracker["external_tracker"]["tasks"][0]["status"] = "DONE"

    with pytest.raises(ValueError, match="not controlled"):
        validated_rows(tracker)


def test_tracker_export_rejects_private_values() -> None:
    tracker = read_tracker()
    tracker["external_tracker"]["tasks"][0]["evidence"] = "C:\\Users\\private\\result.txt"

    with pytest.raises(ValueError, match="private path"):
        validated_rows(tracker)


def test_tracker_export_cli_accepts_explicit_output(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "tracker.csv"

    assert main(["--input", str(TRACKER_PATH), "--output", str(output)]) == 0
    assert output.is_file()


def test_tracker_export_defaults_to_ignored_artifacts_path() -> None:
    assert DEFAULT_OUTPUT == PROJECT_ROOT / "artifacts" / "tracker_status.csv"
    assert "artifacts/" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_tracker_export_uses_only_python_standard_library() -> None:
    source_path = PROJECT_ROOT / "scripts" / "export_tracker_status.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    assert imports <= {"argparse", "csv", "datetime", "json", "pathlib", "re", "typing", "__future__"}
