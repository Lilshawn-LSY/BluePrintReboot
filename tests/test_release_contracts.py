import copy
import json
import re
from pathlib import Path

import pytest

from config.contact import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUSES = {"VERIFIED", "NOT VERIFIED", "NOT PERFORMED", "FAILED"}
ALLOWED_TASK_STATUSES = {"COMPLETED", "SUPERSEDED", "DEFERRED", "PARTIAL", "NOT VERIFIED"}
PR_CI_GATE = "PR #2 GitHub-hosted CI"
MAIN_CI_GATE = "post-merge main GitHub-hosted CI"
CLEAN_PC_GATE = "user-performed clean-PC restore rehearsal"
TAG_GATE = "v1.4.0 tag creation"
RELEASE_GATE = "v1.4.0 GitHub release publication"


def read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def read_tracker() -> dict:
    return json.loads(read_text("docs/tracker_sync_status.json"))


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_ci_state(item: dict, open_gates: set[str], gate: str) -> None:
    assert item["status"] in {"VERIFIED", "NOT VERIFIED", "FAILED"}
    has_run_locator = _has_text(item.get("run_id")) or _has_text(item.get("run_url"))
    has_commit = _has_text(item.get("commit_sha"))

    if item["status"] == "VERIFIED":
        assert has_run_locator
        assert has_commit
        assert gate not in open_gates
    elif item["status"] == "NOT VERIFIED":
        assert item.get("run_id") is None
        assert item.get("run_url") is None
        assert item.get("commit_sha") is None
        assert not item.get("jobs")
        assert gate in open_gates
    else:
        assert has_run_locator
        assert has_commit
        assert gate in open_gates


def validate_clean_pc_state(item: dict, open_gates: set[str]) -> None:
    assert item["status"] in {"VERIFIED", "NOT PERFORMED", "FAILED"}
    if item["status"] == "VERIFIED":
        assert _has_text(item.get("evidence"))
        assert CLEAN_PC_GATE not in open_gates
    elif item["status"] == "NOT PERFORMED":
        assert item.get("evidence") is None
    else:
        assert _has_text(item.get("evidence"))
        assert CLEAN_PC_GATE in open_gates


def validate_publication_state(item: dict, open_gates: set[str], gate: str, locator_key: str) -> None:
    assert item["status"] in {"VERIFIED", "NOT PERFORMED", "FAILED"}
    if item["status"] == "VERIFIED":
        assert _has_text(item.get(locator_key))
        assert _has_text(item.get("evidence"))
        assert gate not in open_gates
    elif item["status"] == "NOT PERFORMED":
        assert item.get(locator_key) is None
        assert item.get("evidence") is None
        assert gate in open_gates
    else:
        assert _has_text(item.get("evidence"))
        assert gate in open_gates


def validate_release_state(tracker: dict) -> None:
    open_gates = tracker["open_gates"]
    assert isinstance(open_gates, list)
    assert len(open_gates) == len(set(open_gates))
    gate_set = set(open_gates)

    verification = tracker["verification"]
    for item in verification.values():
        assert item["status"] in ALLOWED_STATUSES

    validate_ci_state(verification["github_actions"], gate_set, PR_CI_GATE)
    validate_ci_state(verification["post_merge_main_github_actions"], gate_set, MAIN_CI_GATE)
    validate_clean_pc_state(verification["clean_pc_restore"], gate_set)
    validate_publication_state(verification["tag"], gate_set, TAG_GATE, "tag_name")
    validate_publication_state(
        verification["github_release"], gate_set, RELEASE_GATE, "release_url"
    )


def test_version_contract_is_consistent() -> None:
    package = json.loads(read_text("frontend/package.json"))
    lock = json.loads(read_text("frontend/package-lock.json"))
    readme = read_text("README.md")

    assert APP_VERSION == "1.4.0"
    assert package["version"] == APP_VERSION
    assert lock["version"] == APP_VERSION
    assert lock["packages"][""]["version"] == APP_VERSION
    assert "v1.4.0-pdfjs-reader-foundation" in readme


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
    assert "[int]$Port = 3000" in launcher
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
    tracker = read_tracker()

    assert tracker["schema_version"] == "2.0"
    assert tracker["current_version"] == "1.4.0"
    assert tracker["release_name"] == "v1.4.0-pdfjs-reader-foundation"
    assert isinstance(tracker["implemented_milestones"], list)
    assert tracker["next_milestone"] == {
        "name": "PDF.js Reader runtime verification and future read-only hardening",
        "status": "planned",
    }
    required_verification = {
        "local_smoke",
        "local_pytest",
        "frontend_dependency_setup",
        "frontend_lint",
        "frontend_test_build",
        "repository_hygiene",
        "tracker_export",
        "manual_runtime",
        "streamlit_regression",
        "github_actions",
        "post_merge_main_github_actions",
        "clean_pc_restore",
        "tag",
        "github_release",
    }
    assert set(tracker["verification"]) == required_verification
    assert tracker["source_control"]["pr_2"]["status"] == "COMPLETED"
    assert set(tracker["source_control"]["pr_2"]["operations"].values()) == {"COMPLETED"}
    validate_release_state(tracker)


def test_external_tracker_mapping_is_versioned_and_controlled() -> None:
    external = read_tracker()["external_tracker"]

    assert external["schema_version"] == "1.0"
    assert external["status_values"] == sorted(ALLOWED_TASK_STATUSES)
    tasks = external["tasks"]
    assert [task["task_id"] for task in tasks] == [f"R-{number:03d}" for number in range(1, 26)]
    assert all(task["status"] in ALLOWED_TASK_STATUSES for task in tasks)
    assert all(set(task) == {"task_id", "status", "evidence", "disposition", "last_verified"} for task in tasks)


def _set_ci_not_verified(tracker: dict, key: str, gate: str) -> None:
    tracker["verification"][key].update(
        {
            "status": "NOT VERIFIED",
            "run_id": None,
            "run_url": None,
            "commit_sha": None,
            "event": None,
            "jobs": {},
        }
    )
    if gate not in tracker["open_gates"]:
        tracker["open_gates"].append(gate)


def test_release_invariants_accept_truthful_ci_state_transition() -> None:
    tracker = copy.deepcopy(read_tracker())
    _set_ci_not_verified(tracker, "github_actions", PR_CI_GATE)
    _set_ci_not_verified(tracker, "post_merge_main_github_actions", MAIN_CI_GATE)

    validate_release_state(tracker)
    assert tracker["verification"]["clean_pc_restore"]["status"] == "NOT PERFORMED"
    assert tracker["verification"]["tag"]["status"] == "NOT PERFORMED"
    assert tracker["verification"]["github_release"]["status"] == "NOT PERFORMED"


@pytest.mark.parametrize(
    ("changes", "gate_open"),
    [
        ({"status": "VERIFIED", "run_id": None, "run_url": None}, False),
        ({"status": "VERIFIED", "commit_sha": None}, False),
        ({"status": "VERIFIED"}, True),
        ({"status": "NOT VERIFIED", "run_id": "123", "run_url": None, "commit_sha": None}, True),
        ({"status": "NOT VERIFIED", "run_id": None, "run_url": None, "commit_sha": "abc"}, True),
        ({"status": "NOT VERIFIED", "run_id": None, "run_url": None, "commit_sha": None, "jobs": {}}, False),
    ],
)
def test_release_invariants_reject_contradictory_pr_ci(changes: dict, gate_open: bool) -> None:
    tracker = copy.deepcopy(read_tracker())
    tracker["verification"]["github_actions"].update(changes)
    if gate_open and PR_CI_GATE not in tracker["open_gates"]:
        tracker["open_gates"].append(PR_CI_GATE)
    if not gate_open and PR_CI_GATE in tracker["open_gates"]:
        tracker["open_gates"].remove(PR_CI_GATE)

    with pytest.raises(AssertionError):
        validate_release_state(tracker)


def test_clean_pc_state_is_independent_from_ci() -> None:
    tracker = copy.deepcopy(read_tracker())
    tracker["verification"]["clean_pc_restore"]["status"] = "VERIFIED"

    with pytest.raises(AssertionError):
        validate_release_state(tracker)


@pytest.mark.parametrize(("key", "gate", "locator"), [("tag", TAG_GATE, "tag_name"), ("github_release", RELEASE_GATE, "release_url")])
def test_publication_state_is_independent_from_ci(key: str, gate: str, locator: str) -> None:
    tracker = copy.deepcopy(read_tracker())
    tracker["verification"][key].update({"status": "VERIFIED", locator: None, "evidence": "claimed"})
    tracker["open_gates"].remove(gate)

    with pytest.raises(AssertionError):
        validate_release_state(tracker)


def test_uncontrolled_verification_status_is_rejected() -> None:
    tracker = copy.deepcopy(read_tracker())
    tracker["verification"]["local_smoke"]["status"] = "PASS"

    with pytest.raises(AssertionError):
        validate_release_state(tracker)


def test_current_release_note_and_documentation_contract() -> None:
    release_note = read_text("docs/release_notes/v1.4.0.md")
    prior_release_note = read_text("docs/release_notes/v1.3.1.md")
    tracker = read_text("docs/tracker_sync_status.json")

    assert "v1.4.0-pdfjs-reader-foundation" in release_note
    assert "pdfjs-dist" in release_note
    assert "pdf.worker.min.mjs?url" in release_note
    assert "Manual PDF.js Reader runtime | NOT PERFORMED" in release_note
    assert "Streamlit regression | NOT PERFORMED" in release_note
    assert "one-byte" in release_note
    assert "v1.3.1-release-state-convergence-and-repo-hygiene" in prior_release_note
    statuses = re.findall(r"\| (VERIFIED|NOT VERIFIED|NOT PERFORMED|FAILED) \|", release_note)
    assert statuses
    assert set(statuses) <= ALLOWED_STATUSES

    private_user_path = re.compile(r"[A-Za-z]:\\Users\\(?!Public(?:\\|\b))[^\\\s]+", re.IGNORECASE)
    for text in (release_note, prior_release_note, tracker):
        assert private_user_path.search(text) is None
