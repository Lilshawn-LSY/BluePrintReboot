import ast
import copy
import json
from pathlib import Path

import pytest

from scripts.export_tracker_status import tracker_csv_bytes
from scripts.reconcile_release_state import (
    CURRENT_REFERENCE_DOCS,
    ReleaseStateError,
    check_release_state,
    render_current_status,
    render_output,
    validate_current_documents,
    validate_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "tracker_sync_status.json"


def read_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_schema_parsing_requires_all_top_level_fields_and_evidence() -> None:
    manifest = read_manifest()
    baseline = manifest["product_release_baseline"]
    change = manifest["completed_control_plane_change"]
    observation = manifest["repository_head_observation"]

    assert baseline["baseline_commit_sha"] == "09a02e3dd42fb3f0209a89be43cb7de77f0599d4"
    assert baseline["tag"]["name"] == "v1.4.0"
    assert change["number"] == 5
    assert change["merge_commit_sha"] == "ab01f79558facceaf9ff2e38a5a37fc3d329d481"
    assert change["merge_commit_sha"] != baseline["baseline_commit_sha"]
    assert observation["commit_sha"] is None
    assert observation["required_invariant"] is False
    validate_manifest(manifest)

    changed_merge = copy.deepcopy(manifest)
    changed_merge["completed_control_plane_change"]["merge_commit_sha"] = "b" * 40
    validate_manifest(changed_merge)

    pinned_head = copy.deepcopy(manifest)
    pinned_head["repository_head_observation"]["commit_sha"] = "a" * 40
    with pytest.raises(ReleaseStateError, match="commit_sha must be null"):
        validate_manifest(pinned_head)

    del manifest["product_version"]

    with pytest.raises(ReleaseStateError, match="top-level keys differ"):
        validate_manifest(manifest)

    manifest = read_manifest()
    manifest["completed_control_plane_change"]["evidence"]["reference"] = ""
    with pytest.raises(ReleaseStateError, match="evidence.reference"):
        validate_manifest(manifest)


def test_uncontrolled_status_is_rejected_anywhere_in_manifest() -> None:
    manifest = read_manifest()
    manifest["manual_validation"]["streamlit_regression"]["status"] = "NOT PERFORMED"

    with pytest.raises(ReleaseStateError, match="not controlled"):
        validate_manifest(manifest)


def test_render_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    manifest_path = tmp_path / "docs" / "tracker_sync_status.json"
    output_path = tmp_path / "docs" / "CURRENT_RELEASE_STATUS.md"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(MANIFEST_PATH.read_bytes())

    render_output(manifest_path, output_path, validate_documents=False)
    first = output_path.read_bytes()
    render_output(manifest_path, output_path, validate_documents=False)
    second = output_path.read_bytes()

    assert first == second
    assert first == render_current_status(read_manifest()).encode("utf-8")
    assert b"Generated evidence does not become stale" in first
    assert b"Verified `main` commit" not in first


def test_fresh_clone_post_merge_check_rejects_stale_then_accepts_rendered_output(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tracker_sync_status.json"
    output_path = tmp_path / "CURRENT_RELEASE_STATUS.md"
    manifest_path.write_bytes(MANIFEST_PATH.read_bytes())
    output_path.write_text("stale\n", encoding="utf-8")

    errors = check_release_state(manifest_path, output_path, validate_documents=False)

    assert errors
    assert "generated output is stale" in errors[0]
    render_output(manifest_path, output_path, validate_documents=False)
    assert check_release_state(manifest_path, output_path, validate_documents=False) == []
    assert "ab01f79558facceaf9ff2e38a5a37fc3d329d481" in output_path.read_text(encoding="utf-8")


def test_conflicting_smoke_evidence_is_explicit_and_not_collapsed() -> None:
    manifest = read_manifest()
    smoke = manifest["automated_validation"]["local_smoke"]
    records = manifest["historical_evidence"]["conflicting_smoke_records"]

    assert smoke["status"] == "VERIFIED"
    assert smoke["counts"] == {"passed": 101, "warnings": 0, "failed": 0}
    assert {tuple(record["counts"].values()) for record in records} == {
        (97, 1, 0),
        (98, 0, 0),
    }
    validate_manifest(manifest)

    collapsed = copy.deepcopy(manifest)
    collapsed["historical_evidence"]["conflicting_smoke_records"] = [records[0]]
    with pytest.raises(ReleaseStateError, match="exactly two"):
        validate_manifest(collapsed)


def test_partially_verified_reader_requires_passed_and_pending_checks() -> None:
    manifest = read_manifest()
    checks = manifest["manual_validation"]["reader_runtime"]["checks"]

    assert manifest["manual_validation"]["reader_runtime"]["status"] == "PARTIALLY VERIFIED"
    assert "VERIFIED" in {item["status"] for item in checks.values()}
    assert "NOT VERIFIED" in {item["status"] for item in checks.values()}
    assert checks["api_offline_restart_recovery"]["status"] == "NOT VERIFIED"
    assert checks["large_pdf_behavior"]["status"] == "NOT VERIFIED"
    assert checks["detailed_range_inspection"]["status"] == "NOT VERIFIED"
    assert manifest["manual_validation"]["streamlit_regression"]["status"] == "NOT VERIFIED"

    for item in checks.values():
        item["status"] = "VERIFIED"
    with pytest.raises(ReleaseStateError, match="passed and pending"):
        validate_manifest(manifest)


def test_tag_existence_does_not_imply_github_release_publication() -> None:
    manifest = read_manifest()

    assert manifest["product_release_baseline"]["tag"]["status"] == "VERIFIED"
    assert manifest["publication_state"]["github_release"]["status"] == "NOT VERIFIED"
    assert manifest["publication_state"]["github_release"]["url"] is None
    validate_manifest(manifest)

    contradiction = copy.deepcopy(manifest)
    contradiction["publication_state"]["github_release"]["status"] = "VERIFIED"
    with pytest.raises(ReleaseStateError, match="GitHub Release"):
        validate_manifest(contradiction)


def test_tag_target_must_match_immutable_product_baseline_commit() -> None:
    manifest = read_manifest()
    manifest["product_release_baseline"]["tag"]["target_commit_sha"] = "0" * 40

    with pytest.raises(ReleaseStateError, match="immutable product baseline"):
        validate_manifest(manifest)


def test_pr_head_ci_and_post_merge_main_ci_are_distinct() -> None:
    manifest = read_manifest()
    checks = manifest["automated_validation"]

    assert checks["pr_head_ci"]["status"] == "VERIFIED"
    assert checks["pr_head_ci"]["run_id"] == "30151090974"
    assert checks["pr_head_ci"]["event"] == "pull_request"
    assert checks["pr_head_ci"]["commit_sha"] == manifest["completed_control_plane_change"]["head_commit_sha"]
    assert checks["post_merge_main_ci"]["status"] == "NOT VERIFIED"
    assert checks["post_merge_main_ci"]["commit_sha"] is None
    assert checks["post_merge_main_ci"]["run_id"] is None

    contradiction = copy.deepcopy(manifest)
    contradiction["automated_validation"]["post_merge_main_ci"]["run_id"] = "30151090974"
    with pytest.raises(ReleaseStateError, match="run_id must be null"):
        validate_manifest(contradiction)


def test_historical_evidence_is_documented_only_and_not_rendered_as_current() -> None:
    manifest = read_manifest()
    rendered = render_current_status(manifest)

    assert manifest["historical_evidence"]["status"] == "DOCUMENTED ONLY"
    assert "v1.3.0 local full-stack baseline" not in rendered
    assert "historical release notes" in rendered.casefold()
    assert "101 passed, 0 warnings, 0 failed" in rendered
    assert "not the latest smoke result" in rendered


def test_tracker_csv_is_consistent_with_canonical_volatile_states() -> None:
    manifest = read_manifest()
    csv_text = tracker_csv_bytes(manifest).decode("utf-8")

    assert f"R-017,{manifest['recurring_operational_procedures']['clean_pc_restore']['status']}," in csv_text
    assert f"R-018,{manifest['manual_validation']['reader_runtime']['status']}," in csv_text
    assert f"R-019,{manifest['product_release_baseline']['implementation']['status']}," in csv_text
    assert f"R-025,{manifest['publication_state']['release_checkpoint']['status']}," in csv_text


def test_private_values_are_rejected_from_manifest_and_generated_evidence() -> None:
    manifest = read_manifest()
    manifest["product_release_baseline"]["evidence"]["summary"] = "Saved at C:\\Users\\private\\result.txt"

    with pytest.raises(ReleaseStateError, match="private path"):
        validate_manifest(manifest)


def test_current_documents_cannot_claim_manual_completion_without_evidence(tmp_path: Path) -> None:
    for relative_path in CURRENT_REFERENCE_DOCS:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "See [current](CURRENT_RELEASE_STATUS.md).\n"
        if relative_path == "README.md":
            text += "PDF.js canvas renderer is primary with a conditional native fallback.\n"
        path.write_text(text, encoding="utf-8")
    with (tmp_path / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("Reader runtime: VERIFIED.\n")

    with pytest.raises(ReleaseStateError, match="unsupported current-state claim"):
        validate_current_documents(tmp_path, read_manifest())


@pytest.mark.parametrize(
    ("relative_path", "allowed_imports"),
    [
        (
            "scripts/reconcile_release_state.py",
            {"__future__", "argparse", "json", "pathlib", "re", "typing"},
        ),
        (
            "scripts/export_tracker_status.py",
            {
                "__future__",
                "argparse",
                "csv",
                "datetime",
                "io",
                "json",
                "pathlib",
                "re",
                "scripts",
                "sys",
                "typing",
            },
        ),
    ],
)
def test_release_state_scripts_use_no_nonstandard_or_network_imports(
    relative_path: str,
    allowed_imports: set[str],
) -> None:
    tree = ast.parse((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    assert imports <= allowed_imports
