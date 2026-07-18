import json
import re
from pathlib import Path

from config.contact import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUSES = {"VERIFIED", "NOT VERIFIED", "NOT PERFORMED", "FAILED"}


def read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_version_contract_is_consistent() -> None:
    package = json.loads(read_text("frontend/package.json"))
    lock = json.loads(read_text("frontend/package-lock.json"))
    readme = read_text("README.md")

    assert APP_VERSION == "1.3.0"
    assert package["version"] == APP_VERSION
    assert lock["version"] == APP_VERSION
    assert lock["packages"][""]["version"] == APP_VERSION
    assert "v1.3.0-reader-pdf-readonly-vertical-slice" in readme


def test_primary_workflow_preserves_full_manual_and_automatic_gate() -> None:
    workflow = read_text(".github/workflows/tests.yml")

    assert re.search(r"(?m)^on:\s*$", workflow)
    for trigger in ("push", "pull_request", "workflow_dispatch"):
        assert re.search(rf"(?m)^  {trigger}:\s*$", workflow)
    assert re.search(r"(?m)^  python:\s*$", workflow)
    assert re.search(r"(?m)^  frontend:\s*$", workflow)
    for command in (
        "python scripts/smoke_check.py",
        "python -m pytest",
        "npm ci",
        "npm run lint",
        "npm test",
    ):
        assert command in workflow


def test_current_frontend_launch_instructions_use_one_canonical_url() -> None:
    for relative_path in (
        "README.md",
        "docs/DEV_WORKFLOW.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/checklists/new_pc_restore_checklist.md",
    ):
        text = read_text(relative_path)
        assert "http://127.0.0.1:3000" in text
        assert "http://localhost:3000" not in text

    launcher = read_text("scripts/run_frontend.ps1")
    assert '$bindAddress = "127.0.0.1"' in launcher
    assert '[int]$Port = 3000' in launcher
    assert '$canonicalBrowserUrl = "http://${bindAddress}:$Port"' in launcher
    assert "http://localhost:3000" not in launcher


def test_historical_release_note_uses_controlled_statuses() -> None:
    release_note = read_text("docs/release_notes/v1.2.1.md")

    for forbidden in ("NOT VERIFIED / PASS", "PASS?", "PARTIAL PASS", "assumed passed", "probably working"):
        assert forbidden not in release_note
    statuses = re.findall(r"\| (VERIFIED|NOT VERIFIED|NOT PERFORMED|FAILED) \|", release_note)
    assert statuses
    assert set(statuses) <= ALLOWED_STATUSES


def test_tracker_sync_status_contract() -> None:
    tracker = json.loads(read_text("docs/tracker_sync_status.json"))

    assert tracker["schema_version"] == "1.0"
    assert tracker["current_version"] == "1.3.0"
    assert tracker["release_name"] == "v1.3.0-reader-pdf-readonly-vertical-slice"
    assert isinstance(tracker["implemented_milestones"], list)
    assert isinstance(tracker["open_gates"], list)
    assert tracker["next_milestone"] == {
        "name": "Reader/PDF hardening and optional PDF.js evaluation",
        "status": "planned",
    }
    required_verification = {
        "local_smoke",
        "local_pytest",
        "frontend_lint",
        "frontend_test_build",
        "manual_runtime",
        "github_actions",
        "clean_pc_restore",
    }
    assert set(tracker["verification"]) == required_verification
    for item in tracker["verification"].values():
        assert item["status"] in ALLOWED_STATUSES
    github_actions = tracker["verification"]["github_actions"]
    assert github_actions["status"] == "NOT VERIFIED"
    assert github_actions["run_url"] is None
    assert github_actions["commit_sha"] is None
    assert "v1.3.0 GitHub-hosted CI" in tracker["open_gates"]
    assert "user-performed clean-PC restore rehearsal" in tracker["open_gates"]


def test_current_release_note_and_documentation_contract() -> None:
    release_note = read_text("docs/release_notes/v1.3.0.md")
    tracker = read_text("docs/tracker_sync_status.json")

    assert "v1.3.0-reader-pdf-readonly-vertical-slice" in release_note
    assert "GET /papers/{paper_id}/pdf" in release_note
    assert "/papers/{paper_id}/reader" in release_note
    assert "PDF.js is intentionally not included" in release_note
    statuses = re.findall(r"\| (VERIFIED|NOT VERIFIED|NOT PERFORMED|FAILED) \|", release_note)
    assert statuses
    assert set(statuses) <= ALLOWED_STATUSES

    private_user_path = re.compile(r"[A-Za-z]:\\Users\\(?!Public(?:\\|\b))[^\\\s]+", re.IGNORECASE)
    for text in (release_note, tracker):
        assert private_user_path.search(text) is None
