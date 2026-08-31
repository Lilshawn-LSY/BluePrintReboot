from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "tracker_sync_status.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "CURRENT_RELEASE_STATUS.md"
SCHEMA_VERSION = "5.0"
CONTROLLED_STATUSES = (
    "VERIFIED",
    "PARTIALLY VERIFIED",
    "DOCUMENTED ONLY",
    "NOT VERIFIED",
    "BLOCKED",
)
CONTROLLED_STATUS_SET = frozenset(CONTROLLED_STATUSES)
CURRENT_REFERENCE_DOCS = (
    "README.md",
    "docs/ROADMAP.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/BACKLOG.md",
    "docs/checklists/regression_checklist.md",
    "docs/release_notes/v1.4.3.md",
    "docs/release_notes/v1.5.0.md",
    "docs/release_notes/v1.5.1.md",
    "docs/release_notes/v1.5.2.md",
    "docs/release_notes/v1.5.3.md",
    "docs/release_notes/v1.5.4.md",
    "docs/release_notes/v1.5.5.md",
    "docs/release_notes/v1.5.6.md",
    "docs/release_notes/v1.5.7.md",
    "docs/release_notes/v1.5.8.md",
    "docs/release_notes/v1.5.9.md",
    "docs/release_notes/v1.5.10.md",
    "docs/release_notes/v1.5.11.md",
    "docs/release_notes/v1.5.12.md",
    "docs/release_notes/v1.6.3.md",
    "docs/release_notes/v1.6.4.md",
    "docs/release_notes/v1.6.5.md",
)
REQUIRED_AUTOMATED_CHECKS = frozenset(
    {
        "pr_head_ci",
        "post_merge_main_ci",
        "local_smoke",
        "full_pytest",
        "focused_reader_snapshot",
        "focused_reader_commands",
        "focused_pdf_api",
        "focused_pdf_foundation",
        "focused_projects_tags",
        "focused_settings",
        "focused_project_commands",
        "focused_project_paper_links",
        "focused_note_block_read",
        "focused_note_block_commands",
        "focused_project_note_block_links",
        "focused_release_version",
        "release_reconciliation",
        "tracker_export",
        "frontend_lint",
        "frontend_production_build",
        "frontend_node_tests",
        "frontend_projects_tags",
        "frontend_settings",
        "frontend_reader_commands",
        "frontend_project_commands",
        "frontend_note_blocks",
        "repository_hygiene",
    }
)
REQUIRED_MANUAL_CHECKS = frozenset(
    {
        "real_pdf_first_page_render",
        "previous_next_navigation",
        "direct_page_entry",
        "zoom_controls",
        "repeated_reader_entry_exit",
        "different_paper_transition",
        "rapid_page_navigation",
        "native_fallback_exclusivity",
        "worker_termination_error_absent",
        "api_offline_restart_recovery",
        "large_pdf_behavior",
        "detailed_range_inspection",
    }
)
REQUIRED_READER_WRITE_MANUAL_CHECKS = frozenset(
    {
        "persisted_note_correct_pdf",
        "absent_note",
        "unreadable_note_warning",
        "missing_pdf",
        "different_paper_transition",
        "api_offline_restart_recovery",
        "metadata_save_reload",
        "reading_note_save_reload",
        "two_stale_browser_sessions",
        "streamlit_web_visibility",
    }
)
REQUIRED_PROJECT_WRITE_MANUAL_CHECKS = frozenset(
    {
        "create_reload_streamlit_visibility",
        "metadata_round_trip",
        "paper_link_add_duplicate_remove",
        "archive_preserves_links",
        "project_revision_conflict",
        "link_revision_conflict",
        "api_restart_draft_recovery",
        "network_privacy",
    }
)
REQUIRED_NOTE_BLOCK_WRITE_MANUAL_CHECKS = frozenset(
    {
        "read_existing_empty_states",
        "create_reload_streamlit_visibility",
        "update_round_trip",
        "note_block_revision_conflict",
        "project_link_add_duplicate_unlink",
        "link_revision_conflict",
        "orphan_navigation_archived_controls",
        "api_restart_draft_recovery",
        "network_privacy",
    }
)
REQUIRED_METADATA_ENRICHMENT_MANUAL_CHECKS = frozenset(
    {
        "candidate_fetch_preview_only",
        "current_candidate_provenance_display",
        "selective_partial_apply_reload",
        "unselected_manual_metadata_preserved",
        "missing_candidate_abstract_preserves_existing",
        "partial_provider_result_safe",
        "provider_failure_preserves_paper_metadata",
        "unsaved_reading_note_survives_candidate_fetch",
        "unsaved_reading_note_survives_metadata_apply",
        "unsaved_reading_note_survives_enrichment_error",
        "stale_revision_conflict_no_silent_overwrite",
        "other_tab_metadata_preserved_after_stale_conflict",
        "repeated_apply_no_corruption",
        "browser_reload_preserves_applied_metadata",
        "reader_project_tag_workflow_smoke",
    }
)
REQUIRED_PDF_SCAN_IMPORT_MANUAL_CHECKS = frozenset(
    {
        "scan_preview_non_mutating",
        "candidate_states",
        "selected_import",
        "library_reader_visibility",
        "metadata_enrichment_follow_up",
        "partial_failure_feedback",
        "restart_persistence",
        "network_path_privacy",
    }
)
REQUIRED_TAG_CANDIDATE_REVIEW_MANUAL_CHECKS = frozenset(
    {
        "canonical_registry_workflow",
        "alias_collision_and_deprecation",
        "candidate_generation_non_mutating",
        "candidate_review_transitions",
        "promotion_resolution",
        "explicit_apply_and_repeat",
        "stale_conflict_and_draft_preservation",
        "network_privacy",
    }
)
REQUIRED_LIBRARY_PAPER_WORKFLOW_MANUAL_CHECKS = frozenset(
    {
        "library_primary_and_papers_signpost",
        "stable_urls_navigation",
        "server_side_search_filters_pagination",
        "browsing_and_missing_pdf_state",
        "scan_import_without_auto_enrichment_tagging",
        "enrichment_preview_selective_apply",
        "exact_sha256_duplicate_detection",
        "reconnect_preserves_paper_state",
        "ambiguous_repair_non_mutating",
        "offline_failure_conflict_behavior",
        "browser_network_privacy",
        "existing_surface_regressions",
        "restart_persistence",
    }
)
REQUIRED_PDF_FOUNDATION_MANUAL_CHECKS = frozenset(
    {
        "sharp_rendering_dpr",
        "sharp_rendering_zoom",
        "text_selection_alignment",
        "selection_coordinate_stability",
        "text_pdf_classification_extraction",
        "scanned_mixed_ocr_state",
        "cache_restart_reuse",
        "source_replacement_stale",
        "library_reader_workflow",
        "frontend_full_text_workflow",
    }
)
PRIVATE_VALUE_PATTERNS = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),
    re.compile(r"/(?:Users|home)/", re.IGNORECASE),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]", re.IGNORECASE),
    re.compile(r"\$env:|os\.environ|%[A-Za-z_][A-Za-z0-9_]*%", re.IGNORECASE),
)
CURRENT_DRIFT_PATTERNS = (
    re.compile(r"No v1\.4\.0 tag\b", re.IGNORECASE),
    re.compile(r"v1\.4\.0 tag[^\n|]*\|\s*(?:NOT PERFORMED|NOT VERIFIED)\b", re.IGNORECASE),
    re.compile(r"Current v1\.4\.0[^\n]*(?:smoke|pytest|Node tests)\s+\d", re.IGNORECASE),
    re.compile(r"\bReader (?:manual )?runtime\s*(?:is|:|\|)\s*\**VERIFIED\b", re.IGNORECASE),
    re.compile(r"\bStreamlit regression\s*(?:is|:|\|)\s*\**VERIFIED\b", re.IGNORECASE),
    re.compile(r"browser's native PDF capability", re.IGNORECASE),
)
INCOMPLETE_EVIDENCE_PATTERNS = (
    re.compile(r"\bno completed(?: manual)? record\b", re.IGNORECASE),
    re.compile(r"\bnot recorded\b", re.IGNORECASE),
    re.compile(r"\bno result\b", re.IGNORECASE),
    re.compile(r"\bpending\b", re.IGNORECASE),
    re.compile(r"\bremains\s+(?:not\s+verified|unverified)\b", re.IGNORECASE),
)
COMPLETION_EVIDENCE_PATTERNS = (
    re.compile(r"\bcompleted\b", re.IGNORECASE),
    re.compile(r"\bpassed\b", re.IGNORECASE),
    re.compile(r"(?<!not )\bverified\b", re.IGNORECASE),
)
EXPECTED_UNRESOLVED_EVIDENCE = (
    "automated_validation.pr_head_ci",
    "automated_validation.post_merge_main_ci",
    "manual_validation.reader_snapshot_runtime",
    "manual_validation.reader_write_runtime",
    "manual_validation.tag_candidate_review_runtime",
    "manual_validation.pdf_foundation_runtime",
    "publication_state.github_release",
    "recurring_operational_procedures.clean_pc_restore",
)
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
TASK_ID_PATTERN = re.compile(r"R-\d{3}")


class ReleaseStateError(ValueError):
    """Raised when the canonical release-state contract is invalid."""


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReleaseStateError("release-state manifest must be a JSON object")
    return data


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseStateError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReleaseStateError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseStateError(f"{field} must be a non-empty string")
    return value.strip()


def _sha(value: object, field: str) -> str:
    text = _text(value, field)
    if SHA_PATTERN.fullmatch(text) is None:
        raise ReleaseStateError(f"{field} must be a 40-character lowercase commit SHA")
    return text


def _walk_values(value: object, path: str = "manifest") -> Iterable[tuple[str, object]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, f"{path}[{index}]")


def _validate_controlled_statuses(manifest: Mapping[str, Any]) -> None:
    declared = manifest.get("controlled_statuses")
    if declared != list(CONTROLLED_STATUSES):
        raise ReleaseStateError("controlled_statuses must contain the canonical ordered values")
    for path, value in _walk_values(manifest):
        if path.rsplit(".", 1)[-1] == "status" and value not in CONTROLLED_STATUS_SET:
            raise ReleaseStateError(f"{path} is not controlled: {value!r}")


def _validate_private_values(manifest: Mapping[str, Any]) -> None:
    for path, value in _walk_values(manifest):
        if not isinstance(value, str):
            continue
        if any(pattern.search(value) for pattern in PRIVATE_VALUE_PATTERNS):
            raise ReleaseStateError(f"{path} contains a private path, identity, environment value, or secret")


def _validate_evidence(item: Mapping[str, Any], field: str) -> None:
    evidence = _mapping(item.get("evidence"), f"{field}.evidence")
    _text(evidence.get("date"), f"{field}.evidence.date")
    _text(evidence.get("reference"), f"{field}.evidence.reference")
    summary = _text(evidence.get("summary"), f"{field}.evidence.summary")
    status = item.get("status")
    if status == "VERIFIED" and any(pattern.search(summary) for pattern in INCOMPLETE_EVIDENCE_PATTERNS):
        raise ReleaseStateError(f"{field}.evidence.summary contradicts VERIFIED status")
    if status == "NOT VERIFIED" and any(pattern.search(summary) for pattern in COMPLETION_EVIDENCE_PATTERNS):
        raise ReleaseStateError(f"{field}.evidence.summary contradicts NOT VERIFIED status")


def derive_reader_runtime_status(checks: Mapping[str, Any]) -> str:
    statuses = {
        _mapping(item, f"reader_runtime.checks.{check_id}").get("status")
        for check_id, item in checks.items()
    }
    unsupported = statuses - {"VERIFIED", "NOT VERIFIED"}
    if unsupported:
        raise ReleaseStateError(
            f"Reader runtime leaf checks must be VERIFIED or NOT VERIFIED; found={sorted(unsupported)}"
        )
    if statuses == {"VERIFIED"}:
        return "VERIFIED"
    if statuses == {"NOT VERIFIED"}:
        return "NOT VERIFIED"
    if statuses == {"VERIFIED", "NOT VERIFIED"}:
        return "PARTIALLY VERIFIED"
    raise ReleaseStateError("Reader runtime checks cannot be empty")


def _validate_release_evidence(manifest: Mapping[str, Any]) -> None:
    baseline = _mapping(manifest.get("product_release_baseline"), "product_release_baseline")
    if baseline.get("status") != "VERIFIED":
        raise ReleaseStateError("product_release_baseline must be VERIFIED")
    if baseline.get("product_version") != "1.4.0":
        raise ReleaseStateError("immutable product baseline version must remain 1.4.0")
    if baseline.get("release_name") != "v1.4.0-pdfjs-reader-foundation":
        raise ReleaseStateError("immutable product baseline release name must remain v1.4.0-pdfjs-reader-foundation")
    baseline_sha = _sha(
        baseline.get("baseline_commit_sha"),
        "product_release_baseline.baseline_commit_sha",
    )
    _validate_evidence(baseline, "product_release_baseline")

    implementation = _mapping(
        baseline.get("implementation"),
        "product_release_baseline.implementation",
    )
    if implementation.get("status") != "VERIFIED":
        raise ReleaseStateError("product baseline implementation must be VERIFIED")
    _text(implementation.get("scope"), "product_release_baseline.implementation.scope")
    _validate_evidence(implementation, "product_release_baseline.implementation")

    tag = _mapping(baseline.get("tag"), "product_release_baseline.tag")
    if tag.get("status") != "VERIFIED":
        raise ReleaseStateError("product baseline tag must be VERIFIED")
    expected_tag = f"v{baseline['product_version']}"
    if tag.get("name") != expected_tag:
        raise ReleaseStateError(f"product baseline tag name must be {expected_tag}")
    if _sha(tag.get("target_commit_sha"), "product_release_baseline.tag.target_commit_sha") != baseline_sha:
        raise ReleaseStateError("verified tag target must equal the immutable product baseline commit")
    _sha(tag.get("object_sha"), "product_release_baseline.tag.object_sha")
    _validate_evidence(tag, "product_release_baseline.tag")

    change = _mapping(
        manifest.get("completed_control_plane_change"),
        "completed_control_plane_change",
    )
    if change.get("status") != "VERIFIED":
        raise ReleaseStateError("completed_control_plane_change must be VERIFIED")
    if not isinstance(change.get("number"), int) or isinstance(change.get("number"), bool) or change["number"] < 1:
        raise ReleaseStateError("completed control-plane change number must be a positive integer")
    if change.get("state") != "MERGED":
        raise ReleaseStateError("completed control-plane change state must be MERGED")
    if change.get("target_branch") != "main":
        raise ReleaseStateError("completed_control_plane_change.target_branch must be main")
    _sha(change.get("head_commit_sha"), "completed_control_plane_change.head_commit_sha")
    _sha(change.get("merge_commit_sha"), "completed_control_plane_change.merge_commit_sha")
    _text(change.get("url"), "completed_control_plane_change.url")
    _validate_evidence(change, "completed_control_plane_change")

    observation = _mapping(
        manifest.get("repository_head_observation"),
        "repository_head_observation",
    )
    if observation.get("status") != "DOCUMENTED ONLY" or observation.get("branch") != "main":
        raise ReleaseStateError("repository HEAD observation must be DOCUMENTED ONLY for branch main")
    if observation.get("commit_sha") is not None:
        raise ReleaseStateError("repository HEAD observation commit_sha must be null in committed state")
    if observation.get("required_invariant") is not False:
        raise ReleaseStateError("repository HEAD observation cannot be a committed invariant")
    _validate_evidence(observation, "repository_head_observation")


def _validate_automated_validation(manifest: Mapping[str, Any]) -> None:
    checks = _mapping(manifest.get("automated_validation"), "automated_validation")
    if set(checks) != REQUIRED_AUTOMATED_CHECKS:
        missing = sorted(REQUIRED_AUTOMATED_CHECKS - set(checks))
        extra = sorted(set(checks) - REQUIRED_AUTOMATED_CHECKS)
        raise ReleaseStateError(f"automated_validation keys differ; missing={missing}, extra={extra}")

    for check_id, raw_item in checks.items():
        item = _mapping(raw_item, f"automated_validation.{check_id}")
        _text(item.get("scope"), f"automated_validation.{check_id}.scope")
        _text(item.get("command"), f"automated_validation.{check_id}.command")
        counts = item.get("counts")
        if counts is not None:
            count_map = _mapping(counts, f"automated_validation.{check_id}.counts")
            if not count_map:
                raise ReleaseStateError(f"automated_validation.{check_id}.counts cannot be empty")
            for name, value in count_map.items():
                if not isinstance(name, str) or not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ReleaseStateError(
                        f"automated_validation.{check_id}.counts must contain non-negative integers"
                    )
        _validate_evidence(item, f"automated_validation.{check_id}")

    pull_request = _mapping(
        manifest["completed_control_plane_change"],
        "completed_control_plane_change",
    )
    pr_ci = _mapping(checks["pr_head_ci"], "automated_validation.pr_head_ci")
    if pr_ci.get("event") != "pull_request":
        raise ReleaseStateError("PR-head CI event must be pull_request")
    if pr_ci.get("commit_sha") != pull_request.get("head_commit_sha"):
        raise ReleaseStateError("PR-head CI commit must equal the recorded completed-change head commit")
    _text(pr_ci.get("run_id"), "automated_validation.pr_head_ci.run_id")
    _text(pr_ci.get("run_url"), "automated_validation.pr_head_ci.run_url")
    jobs = _mapping(pr_ci.get("jobs"), "automated_validation.pr_head_ci.jobs")
    if set(jobs) != {"frontend", "python"} or any(result not in {"success", "failure"} for result in jobs.values()):
        raise ReleaseStateError("PR-head CI must record success or failure for Python and frontend jobs")
    job_results = set(jobs.values())
    expected_pr_ci_status = (
        "VERIFIED"
        if job_results == {"success"}
        else "NOT VERIFIED"
        if job_results == {"failure"}
        else "PARTIALLY VERIFIED"
    )
    if pr_ci.get("status") != expected_pr_ci_status:
        raise ReleaseStateError(
            f"PR-head CI status must be {expected_pr_ci_status} for recorded job conclusions"
        )
    expected_job_counts = {
        "jobs_passed": sum(result == "success" for result in jobs.values()),
        "jobs_failed": sum(result == "failure" for result in jobs.values()),
    }
    if pr_ci.get("counts") != expected_job_counts:
        raise ReleaseStateError("PR-head CI counts must match recorded job conclusions")

    main_ci = _mapping(checks["post_merge_main_ci"], "automated_validation.post_merge_main_ci")
    if main_ci.get("status") != "NOT VERIFIED":
        raise ReleaseStateError("post-merge main CI must remain NOT VERIFIED without direct evidence")
    for field in ("run_id", "run_url", "commit_sha"):
        if main_ci.get(field) is not None:
            raise ReleaseStateError(f"post-merge main CI {field} must be null while NOT VERIFIED")
    if main_ci.get("jobs") != {} or main_ci.get("counts") is not None:
        raise ReleaseStateError("post-merge main CI cannot claim jobs or counts while NOT VERIFIED")

    smoke = _mapping(checks["local_smoke"], "automated_validation.local_smoke")
    if smoke.get("status") != "VERIFIED":
        raise ReleaseStateError("current smoke must be VERIFIED")
    smoke_counts = _mapping(smoke.get("counts"), "automated_validation.local_smoke.counts")
    if set(smoke_counts) != {"passed", "warnings", "failed"} or smoke_counts["failed"] != 0:
        raise ReleaseStateError("VERIFIED current smoke must record passed, warnings, and zero failed")


def _validate_manual_validation(manifest: Mapping[str, Any]) -> None:
    manual = _mapping(manifest.get("manual_validation"), "manual_validation")
    reader = _mapping(manual.get("reader_runtime"), "manual_validation.reader_runtime")
    checks = _mapping(reader.get("checks"), "manual_validation.reader_runtime.checks")
    if set(checks) != REQUIRED_MANUAL_CHECKS:
        missing = sorted(REQUIRED_MANUAL_CHECKS - set(checks))
        extra = sorted(set(checks) - REQUIRED_MANUAL_CHECKS)
        raise ReleaseStateError(f"Reader runtime checks differ; missing={missing}, extra={extra}")
    for check_id, raw_item in checks.items():
        item = _mapping(raw_item, f"manual_validation.reader_runtime.checks.{check_id}")
        _validate_evidence(item, f"manual_validation.reader_runtime.checks.{check_id}")
    expected_status = derive_reader_runtime_status(checks)
    if reader.get("status") != expected_status:
        raise ReleaseStateError(
            f"Reader runtime aggregate status must be {expected_status} for its child checks"
        )
    _validate_evidence(reader, "manual_validation.reader_runtime")

    streamlit = _mapping(manual.get("streamlit_regression"), "manual_validation.streamlit_regression")
    _validate_evidence(streamlit, "manual_validation.streamlit_regression")

    reader_snapshot = _mapping(
        manual.get("reader_snapshot_runtime"),
        "manual_validation.reader_snapshot_runtime",
    )
    _validate_evidence(reader_snapshot, "manual_validation.reader_snapshot_runtime")

    reader_write = _mapping(
        manual.get("reader_write_runtime"),
        "manual_validation.reader_write_runtime",
    )
    write_checks = _mapping(
        reader_write.get("checks"),
        "manual_validation.reader_write_runtime.checks",
    )
    if set(write_checks) != REQUIRED_READER_WRITE_MANUAL_CHECKS:
        missing = sorted(REQUIRED_READER_WRITE_MANUAL_CHECKS - set(write_checks))
        extra = sorted(set(write_checks) - REQUIRED_READER_WRITE_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Reader write runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in write_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.reader_write_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.reader_write_runtime.checks.{check_id}",
        )
    expected_write_status = derive_reader_runtime_status(write_checks)
    if reader_write.get("status") != expected_write_status:
        raise ReleaseStateError(
            "Reader write runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(reader_write, "manual_validation.reader_write_runtime")

    project_write = _mapping(
        manual.get("project_write_runtime"),
        "manual_validation.project_write_runtime",
    )
    project_checks = _mapping(
        project_write.get("checks"),
        "manual_validation.project_write_runtime.checks",
    )
    if set(project_checks) != REQUIRED_PROJECT_WRITE_MANUAL_CHECKS:
        missing = sorted(REQUIRED_PROJECT_WRITE_MANUAL_CHECKS - set(project_checks))
        extra = sorted(set(project_checks) - REQUIRED_PROJECT_WRITE_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Project write runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in project_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.project_write_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.project_write_runtime.checks.{check_id}",
        )
    expected_project_status = derive_reader_runtime_status(project_checks)
    if project_write.get("status") != expected_project_status:
        raise ReleaseStateError(
            "Project write runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(project_write, "manual_validation.project_write_runtime")

    note_block_write = _mapping(
        manual.get("note_block_write_runtime"),
        "manual_validation.note_block_write_runtime",
    )
    note_block_checks = _mapping(
        note_block_write.get("checks"),
        "manual_validation.note_block_write_runtime.checks",
    )
    if set(note_block_checks) != REQUIRED_NOTE_BLOCK_WRITE_MANUAL_CHECKS:
        missing = sorted(REQUIRED_NOTE_BLOCK_WRITE_MANUAL_CHECKS - set(note_block_checks))
        extra = sorted(set(note_block_checks) - REQUIRED_NOTE_BLOCK_WRITE_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Note Block write runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in note_block_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.note_block_write_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.note_block_write_runtime.checks.{check_id}",
        )
    expected_note_block_status = derive_reader_runtime_status(note_block_checks)
    if note_block_write.get("status") != expected_note_block_status:
        raise ReleaseStateError(
            "Note Block write runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(note_block_write, "manual_validation.note_block_write_runtime")

    metadata_enrichment = _mapping(
        manual.get("metadata_enrichment_runtime"),
        "manual_validation.metadata_enrichment_runtime",
    )
    enrichment_checks = _mapping(
        metadata_enrichment.get("checks"),
        "manual_validation.metadata_enrichment_runtime.checks",
    )
    if set(enrichment_checks) != REQUIRED_METADATA_ENRICHMENT_MANUAL_CHECKS:
        missing = sorted(REQUIRED_METADATA_ENRICHMENT_MANUAL_CHECKS - set(enrichment_checks))
        extra = sorted(set(enrichment_checks) - REQUIRED_METADATA_ENRICHMENT_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Metadata enrichment runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in enrichment_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.metadata_enrichment_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.metadata_enrichment_runtime.checks.{check_id}",
        )
    expected_metadata_enrichment_status = derive_reader_runtime_status(enrichment_checks)
    if metadata_enrichment.get("status") != expected_metadata_enrichment_status:
        raise ReleaseStateError(
            "Metadata enrichment runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(metadata_enrichment, "manual_validation.metadata_enrichment_runtime")

    pdf_scan_import = _mapping(
        manual.get("pdf_scan_import_runtime"),
        "manual_validation.pdf_scan_import_runtime",
    )
    scan_import_checks = _mapping(
        pdf_scan_import.get("checks"),
        "manual_validation.pdf_scan_import_runtime.checks",
    )
    if set(scan_import_checks) != REQUIRED_PDF_SCAN_IMPORT_MANUAL_CHECKS:
        missing = sorted(REQUIRED_PDF_SCAN_IMPORT_MANUAL_CHECKS - set(scan_import_checks))
        extra = sorted(set(scan_import_checks) - REQUIRED_PDF_SCAN_IMPORT_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"PDF scan/import runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in scan_import_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.pdf_scan_import_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.pdf_scan_import_runtime.checks.{check_id}",
        )
    expected_scan_import_status = derive_reader_runtime_status(scan_import_checks)
    if pdf_scan_import.get("status") != expected_scan_import_status:
        raise ReleaseStateError(
            "PDF scan/import runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(pdf_scan_import, "manual_validation.pdf_scan_import_runtime")

    tag_candidate_review = _mapping(
        manual.get("tag_candidate_review_runtime"),
        "manual_validation.tag_candidate_review_runtime",
    )
    tag_candidate_checks = _mapping(
        tag_candidate_review.get("checks"),
        "manual_validation.tag_candidate_review_runtime.checks",
    )
    if set(tag_candidate_checks) != REQUIRED_TAG_CANDIDATE_REVIEW_MANUAL_CHECKS:
        missing = sorted(REQUIRED_TAG_CANDIDATE_REVIEW_MANUAL_CHECKS - set(tag_candidate_checks))
        extra = sorted(set(tag_candidate_checks) - REQUIRED_TAG_CANDIDATE_REVIEW_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Tag candidate-review runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in tag_candidate_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.tag_candidate_review_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.tag_candidate_review_runtime.checks.{check_id}",
        )
    expected_tag_candidate_status = derive_reader_runtime_status(tag_candidate_checks)
    if tag_candidate_review.get("status") != expected_tag_candidate_status:
        raise ReleaseStateError(
            "Tag candidate-review runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(tag_candidate_review, "manual_validation.tag_candidate_review_runtime")

    library_paper_workflow = _mapping(
        manual.get("library_paper_workflow_runtime"),
        "manual_validation.library_paper_workflow_runtime",
    )
    library_checks = _mapping(
        library_paper_workflow.get("checks"),
        "manual_validation.library_paper_workflow_runtime.checks",
    )
    if set(library_checks) != REQUIRED_LIBRARY_PAPER_WORKFLOW_MANUAL_CHECKS:
        missing = sorted(REQUIRED_LIBRARY_PAPER_WORKFLOW_MANUAL_CHECKS - set(library_checks))
        extra = sorted(set(library_checks) - REQUIRED_LIBRARY_PAPER_WORKFLOW_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"Library/Paper workflow runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in library_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.library_paper_workflow_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.library_paper_workflow_runtime.checks.{check_id}",
        )
    expected_library_status = derive_reader_runtime_status(library_checks)
    if library_paper_workflow.get("status") != expected_library_status:
        raise ReleaseStateError(
            "Library/Paper workflow runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(library_paper_workflow, "manual_validation.library_paper_workflow_runtime")

    pdf_foundation = _mapping(
        manual.get("pdf_foundation_runtime"),
        "manual_validation.pdf_foundation_runtime",
    )
    pdf_foundation_checks = _mapping(
        pdf_foundation.get("checks"),
        "manual_validation.pdf_foundation_runtime.checks",
    )
    if set(pdf_foundation_checks) != REQUIRED_PDF_FOUNDATION_MANUAL_CHECKS:
        missing = sorted(REQUIRED_PDF_FOUNDATION_MANUAL_CHECKS - set(pdf_foundation_checks))
        extra = sorted(set(pdf_foundation_checks) - REQUIRED_PDF_FOUNDATION_MANUAL_CHECKS)
        raise ReleaseStateError(
            f"PDF foundation runtime checks differ; missing={missing}, extra={extra}"
        )
    for check_id, raw_item in pdf_foundation_checks.items():
        item = _mapping(
            raw_item,
            f"manual_validation.pdf_foundation_runtime.checks.{check_id}",
        )
        _validate_evidence(
            item,
            f"manual_validation.pdf_foundation_runtime.checks.{check_id}",
        )
    expected_pdf_foundation_status = derive_reader_runtime_status(pdf_foundation_checks)
    if pdf_foundation.get("status") != expected_pdf_foundation_status:
        raise ReleaseStateError(
            "PDF foundation runtime aggregate status must derive from its child checks"
        )
    _validate_evidence(pdf_foundation, "manual_validation.pdf_foundation_runtime")


def _validate_publication_and_operations(manifest: Mapping[str, Any]) -> None:
    publication = _mapping(manifest.get("publication_state"), "publication_state")
    github_release = _mapping(publication.get("github_release"), "publication_state.github_release")
    if github_release.get("status") != "NOT VERIFIED" or github_release.get("url") is not None:
        raise ReleaseStateError("GitHub Release must remain separately NOT VERIFIED with no URL")
    _validate_evidence(github_release, "publication_state.github_release")

    checkpoint = _mapping(publication.get("release_checkpoint"), "publication_state.release_checkpoint")
    if checkpoint.get("status") != "PARTIALLY VERIFIED":
        raise ReleaseStateError("tag-present/unpublished release checkpoint must be PARTIALLY VERIFIED")
    _validate_evidence(checkpoint, "publication_state.release_checkpoint")

    operations = _mapping(
        manifest.get("recurring_operational_procedures"),
        "recurring_operational_procedures",
    )
    restore = _mapping(operations.get("clean_pc_restore"), "recurring_operational_procedures.clean_pc_restore")
    if restore.get("status") != "NOT VERIFIED":
        raise ReleaseStateError("clean-PC restore must remain NOT VERIFIED")
    _text(restore.get("procedure"), "recurring_operational_procedures.clean_pc_restore.procedure")
    _text(restore.get("cadence"), "recurring_operational_procedures.clean_pc_restore.cadence")
    _validate_evidence(restore, "recurring_operational_procedures.clean_pc_restore")


def _validate_external_tracker(manifest: Mapping[str, Any]) -> None:
    external = _mapping(manifest.get("external_tracker"), "external_tracker")
    if external.get("schema_version") != "2.0":
        raise ReleaseStateError("external_tracker.schema_version must be 2.0")
    if external.get("status_values") != list(CONTROLLED_STATUSES):
        raise ReleaseStateError("external_tracker.status_values must match the canonical statuses")
    if _text(external.get("last_reconciled"), "external_tracker.last_reconciled") != manifest["as_of"]:
        raise ReleaseStateError("external_tracker.last_reconciled must equal manifest as_of")
    tasks = _list(external.get("tasks"), "external_tracker.tasks")
    expected_ids = [f"R-{number:03d}" for number in range(1, 26)] + ["R-145"]
    task_ids = [task.get("task_id") if isinstance(task, dict) else None for task in tasks]
    if task_ids != expected_ids:
        raise ReleaseStateError("external tracker tasks must be ordered R-001 through R-025, then R-145")
    for index, raw_task in enumerate(tasks):
        task = _mapping(raw_task, f"external_tracker.tasks[{index}]")
        if set(task) != {"disposition", "evidence", "last_verified", "status", "task_id"}:
            raise ReleaseStateError("external tracker tasks must contain exactly the five CSV fields")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or TASK_ID_PATTERN.fullmatch(task_id) is None:
            raise ReleaseStateError("external tracker task_id must match R-000")
        _text(task.get("evidence"), f"external_tracker.{task_id}.evidence")
        _text(task.get("disposition"), f"external_tracker.{task_id}.disposition")
        _text(task.get("last_verified"), f"external_tracker.{task_id}.last_verified")

    by_id = {task["task_id"]: task for task in tasks}
    derived_tasks = {
        "R-017": manifest["recurring_operational_procedures"]["clean_pc_restore"],
        "R-018": manifest["manual_validation"]["reader_runtime"],
        "R-019": manifest["product_release_baseline"]["implementation"],
        "R-025": manifest["publication_state"]["release_checkpoint"],
    }
    for task_id, state in derived_tasks.items():
        if by_id[task_id]["status"] != state["status"] or by_id[task_id]["evidence"] != state["evidence"]["summary"]:
            raise ReleaseStateError(f"{task_id} status and evidence must derive from its canonical state")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    required_top_level = {
        "schema_version",
        "product_version",
        "release_name",
        "as_of",
        "controlled_statuses",
        "product_release_baseline",
        "completed_control_plane_change",
        "repository_head_observation",
        "automated_validation",
        "manual_validation",
        "publication_state",
        "recurring_operational_procedures",
        "unresolved_evidence",
        "next_milestone",
        "historical_evidence",
        "operational_policy",
        "external_tracker",
    }
    if set(manifest) != required_top_level:
        missing = sorted(required_top_level - set(manifest))
        extra = sorted(set(manifest) - required_top_level)
        raise ReleaseStateError(f"manifest top-level keys differ; missing={missing}, extra={extra}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseStateError(f"schema_version must be {SCHEMA_VERSION}")
    if manifest.get("product_version") != "1.6.5":
        raise ReleaseStateError("product_version must identify the current 1.6.5 runtime target")
    if manifest.get("release_name") != "v1.6.5-visual-language-design-system-refinement":
        raise ReleaseStateError("release_name must identify the current v1.6.5 runtime target")
    _text(manifest.get("as_of"), "as_of")
    _validate_controlled_statuses(manifest)
    _validate_private_values(manifest)

    _validate_release_evidence(manifest)
    _validate_automated_validation(manifest)
    _validate_manual_validation(manifest)
    _validate_publication_and_operations(manifest)

    unresolved = _mapping(manifest.get("unresolved_evidence"), "unresolved_evidence")
    unresolved_items = _list(unresolved.get("items"), "unresolved_evidence.items")
    if unresolved_items != list(EXPECTED_UNRESOLVED_EVIDENCE):
        raise ReleaseStateError(
            "unresolved_evidence.items must list the canonical remaining partial or unverified release-state paths"
        )

    next_milestone = _mapping(manifest.get("next_milestone"), "next_milestone")
    if next_milestone.get("status") != "DOCUMENTED ONLY":
        raise ReleaseStateError("next_milestone must be DOCUMENTED ONLY")
    _text(next_milestone.get("name"), "next_milestone.name")
    _validate_evidence(next_milestone, "next_milestone")

    historical = _mapping(manifest.get("historical_evidence"), "historical_evidence")
    if historical.get("status") != "DOCUMENTED ONLY":
        raise ReleaseStateError("historical_evidence must be DOCUMENTED ONLY")
    _text(historical.get("policy"), "historical_evidence.policy")
    references = _list(historical.get("references"), "historical_evidence.references")
    if not references or any(not isinstance(item, str) or not item.strip() for item in references):
        raise ReleaseStateError("historical_evidence.references must contain repository-relative documents")
    smoke_records = _list(
        historical.get("conflicting_smoke_records"),
        "historical_evidence.conflicting_smoke_records",
    )
    if len(smoke_records) != 2:
        raise ReleaseStateError("historical evidence must preserve exactly two conflicting v1.4.0 smoke records")
    count_signatures: set[tuple[tuple[str, int], ...]] = set()
    for index, raw_record in enumerate(smoke_records):
        record = _mapping(raw_record, f"historical_evidence.conflicting_smoke_records[{index}]")
        _text(record.get("reference"), f"historical_evidence.conflicting_smoke_records[{index}].reference")
        _text(record.get("date"), f"historical_evidence.conflicting_smoke_records[{index}].date")
        counts = _mapping(
            record.get("counts"),
            f"historical_evidence.conflicting_smoke_records[{index}].counts",
        )
        if set(counts) != {"failed", "passed", "warnings"}:
            raise ReleaseStateError("historical smoke records require passed, warnings, and failed")
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
            raise ReleaseStateError("historical smoke counts must be non-negative integers")
        count_signatures.add(tuple(sorted(counts.items())))
    if len(count_signatures) != 2:
        raise ReleaseStateError("historical v1.4.0 smoke records must remain conflicting")

    policy = _mapping(manifest.get("operational_policy"), "operational_policy")
    if policy.get("status") != "DOCUMENTED ONLY":
        raise ReleaseStateError("operational_policy must be DOCUMENTED ONLY")
    _text(policy.get("reference"), "operational_policy.reference")
    _text(policy.get("summary"), "operational_policy.summary")
    _validate_external_tracker(manifest)


def _escape_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _format_counts(counts: object) -> str:
    if counts is None:
        return "Not recorded"
    assert isinstance(counts, dict)
    return ", ".join(f"{value} {name.replace('_', ' ')}" for name, value in counts.items())


def _evidence_summary(item: Mapping[str, Any]) -> str:
    evidence = item["evidence"]
    return f"{evidence['summary']} ({evidence['date']}; {evidence['reference']})"


def render_current_status(manifest: Mapping[str, Any]) -> str:
    validate_manifest(manifest)
    baseline = manifest["product_release_baseline"]
    change = manifest["completed_control_plane_change"]
    observation = manifest["repository_head_observation"]
    automated = manifest["automated_validation"]
    manual = manifest["manual_validation"]
    publication = manifest["publication_state"]
    restore = manifest["recurring_operational_procedures"]["clean_pc_restore"]
    smoke_counts = automated["local_smoke"]["counts"]
    pr_jobs = automated["pr_head_ci"]["jobs"]

    lines = [
        "<!-- Generated by scripts/reconcile_release_state.py. Do not edit by hand. -->",
        "",
        "# Current Release Status",
        "",
        f"Canonical manifest: [`tracker_sync_status.json`](tracker_sync_status.json), schema {manifest['schema_version']}.",
        f"Rendered as of {manifest['as_of']}.",
        "",
        "## Release identity",
        "",
        f"- Runtime target version: `{manifest['product_version']}`",
        f"- Runtime target name: `{manifest['release_name']}`",
        f"- Immutable released baseline: `{baseline['release_name']}` at `{baseline['baseline_commit_sha']}`",
        f"- Next milestone: **{manifest['next_milestone']['status']}** — {manifest['next_milestone']['name']}",
        "",
        "## Current state summary",
        "",
        "| Area | Status | Evidence |",
        "|---|---|---|",
        f"| v{manifest['product_version']} local runtime target | {automated['local_smoke']['status']} | {_escape_cell(_evidence_summary(automated['local_smoke']))} |",
        f"| v1.4.0 implementation baseline | {baseline['implementation']['status']} | {_escape_cell(_evidence_summary(baseline['implementation']))} |",
        f"| PR #{change['number']} control-plane change | {change['status']} | Merged into `main` at `{change['merge_commit_sha']}`. |",
        f"| v1.4.0 tag | {baseline['tag']['status']} | Tag targets immutable baseline `{baseline['tag']['target_commit_sha']}`. |",
        f"| PR-head GitHub Actions | {automated['pr_head_ci']['status']} | Run `{automated['pr_head_ci']['run_id']}`; "
        f"Python `{pr_jobs['python']}`, frontend `{pr_jobs['frontend']}`. |",
        f"| Post-merge `main` GitHub Actions | {automated['post_merge_main_ci']['status']} | {_escape_cell(automated['post_merge_main_ci']['evidence']['summary'])} |",
        f"| Reader runtime | {manual['reader_runtime']['status']} | {_escape_cell(manual['reader_runtime']['evidence']['summary'])} |",
        f"| v1.5.12 PDF foundation runtime | {manual['pdf_foundation_runtime']['status']} | {_escape_cell(manual['pdf_foundation_runtime']['evidence']['summary'])} |",
        f"| v1.5.11 Library/Paper workflow runtime | {manual['library_paper_workflow_runtime']['status']} | {_escape_cell(manual['library_paper_workflow_runtime']['evidence']['summary'])} |",
        f"| v1.5.0 Reader Snapshot runtime | {manual['reader_snapshot_runtime']['status']} | {_escape_cell(manual['reader_snapshot_runtime']['evidence']['summary'])} |",
        f"| v1.5.1 Reader write runtime | {manual['reader_write_runtime']['status']} | {_escape_cell(manual['reader_write_runtime']['evidence']['summary'])} |",
        f"| v1.5.4 Project write runtime | {manual['project_write_runtime']['status']} | {_escape_cell(manual['project_write_runtime']['evidence']['summary'])} |",
        f"| v1.5.5 Note Block write runtime | {manual['note_block_write_runtime']['status']} | {_escape_cell(manual['note_block_write_runtime']['evidence']['summary'])} |",
        f"| v1.5.8 Metadata enrichment runtime | {manual['metadata_enrichment_runtime']['status']} | {_escape_cell(manual['metadata_enrichment_runtime']['evidence']['summary'])} |",
        f"| v1.5.9 PDF scan/import runtime | {manual['pdf_scan_import_runtime']['status']} | {_escape_cell(manual['pdf_scan_import_runtime']['evidence']['summary'])} |",
        f"| v1.5.10 Tag candidate review runtime | {manual['tag_candidate_review_runtime']['status']} | {_escape_cell(manual['tag_candidate_review_runtime']['evidence']['summary'])} |",
        f"| Streamlit regression | {manual['streamlit_regression']['status']} | {_escape_cell(manual['streamlit_regression']['evidence']['summary'])} |",
        f"| GitHub Release publication | {publication['github_release']['status']} | {_escape_cell(publication['github_release']['evidence']['summary'])} |",
        f"| Clean-PC restore | {restore['status']} | Recurring operational procedure; no rehearsal is claimed. |",
        "",
        "## Immutable baseline and completed change",
        "",
        f"- Product baseline commit: `{baseline['baseline_commit_sha']}`.",
        f"- PR #{change['number']}: [{change['url']}]({change['url']}); head `{change['head_commit_sha']}`, merge `{change['merge_commit_sha']}`.",
        f"- Tag `{baseline['tag']['name']}` is verified at `{baseline['tag']['target_commit_sha']}`.",
        "- Tag existence is source-control evidence only. It does not imply GitHub Release publication.",
        f"- Repository HEAD observation: **{observation['status']}**; committed SHA is intentionally "
        f"`null`, and `required_invariant` is `{str(observation['required_invariant']).lower()}`.",
        "- Generated evidence does not become stale when the commit containing it is merged.",
        "",
        "## Automated validation",
        "",
        "| Check | Status | Scope | Counts | Evidence |",
        "|---|---|---|---|---|",
    ]
    for check_id, item in automated.items():
        counts = _format_counts(item.get("counts"))
        label = check_id.replace("_", " ").title().replace("Ci", "CI").replace("Pytest", "pytest")
        lines.append(
            f"| {label} | {item['status']} | {_escape_cell(item['scope'])} | "
            f"{_escape_cell(counts)} | {_escape_cell(_evidence_summary(item))} |"
        )

    lines.extend(
        [
            "",
            f"The current smoke result is {smoke_counts['passed']} passed, {smoke_counts['warnings']} warnings, "
            f"{smoke_counts['failed']} failed. The two conflicting "
            "v1.4.0 records remain historical evidence and do not override this current result.",
            "",
            "## v1.5.12 PDF foundation manual validation",
            "",
            f"Aggregate state: **{manual['pdf_foundation_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["pdf_foundation_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.11 Library/Paper workflow manual validation",
            "",
            f"Aggregate state: **{manual['library_paper_workflow_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["library_paper_workflow_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## Reader manual validation",
            "",
            f"Aggregate state: **{manual['reader_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["reader_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.1 Reader write manual validation",
            "",
            f"Aggregate state: **{manual['reader_write_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["reader_write_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.4 Project write manual validation",
            "",
            f"Aggregate state: **{manual['project_write_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["project_write_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.5 Note Block write manual validation",
            "",
            f"Aggregate state: **{manual['note_block_write_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["note_block_write_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.8 Metadata enrichment manual validation",
            "",
            f"Aggregate state: **{manual['metadata_enrichment_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["metadata_enrichment_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.9 PDF scan/import manual validation",
            "",
            f"Aggregate state: **{manual['pdf_scan_import_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["pdf_scan_import_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## v1.5.10 Tag governance and candidate-review manual validation",
            "",
            f"Aggregate state: **{manual['tag_candidate_review_runtime']['status']}**.",
            "",
            "| Check | Status | Evidence |",
            "|---|---|---|",
        ]
    )
    for check_id, item in manual["tag_candidate_review_runtime"]["checks"].items():
        label = check_id.replace("_", " ").capitalize()
        lines.append(f"| {label} | {item['status']} | {_escape_cell(_evidence_summary(item))} |")

    lines.extend(
        [
            "",
            "## Publication and recurring operations",
            "",
            f"- GitHub Release: **{publication['github_release']['status']}**. "
            f"{publication['github_release']['evidence']['summary']}",
            f"- Release checkpoint: **{publication['release_checkpoint']['status']}**. "
            f"{publication['release_checkpoint']['evidence']['summary']}",
            f"- Clean-PC restore: **{restore['status']}**. {restore['evidence']['summary']} "
            f"Procedure: `{restore['procedure']}`.",
            "",
            "## Unresolved evidence",
            "",
            f"- PR-head workflow: **{automated['pr_head_ci']['status']}**. "
            f"{automated['pr_head_ci']['evidence']['summary']}",
            f"- Post-merge `main` workflow: **{automated['post_merge_main_ci']['status']}**. "
            f"{automated['post_merge_main_ci']['evidence']['summary']}",
            f"- v1.5.0 Reader Snapshot runtime: **{manual['reader_snapshot_runtime']['status']}**. "
            f"{manual['reader_snapshot_runtime']['evidence']['summary']}",
            f"- v1.5.1 Reader write runtime: **{manual['reader_write_runtime']['status']}**. "
            f"{manual['reader_write_runtime']['evidence']['summary']}",
            f"- v1.5.10 Tag candidate review runtime: **{manual['tag_candidate_review_runtime']['status']}**. "
            f"{manual['tag_candidate_review_runtime']['evidence']['summary']}",
            f"- GitHub Release publication: **{publication['github_release']['status']}**. "
            f"{publication['github_release']['evidence']['summary']}",
            f"- Clean-PC restore: **{restore['status']}**. {restore['evidence']['summary']}",
            "",
            "## Historical conflicting smoke evidence",
            "",
        ]
    )
    for record in manifest["historical_evidence"]["conflicting_smoke_records"]:
        lines.append(f"- {_format_counts(record['counts'])} ({record['date']}; {record['reference']}).")
    lines.extend(
        [
            "",
            "These records remain conflicting historical v1.4.0 evidence. They are not the latest smoke result.",
            "",
            "Historical release notes remain historical evidence. They are not inputs for current-state "
            "inference when the canonical manifest has a current field.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_current_documents(project_root: Path, manifest: Mapping[str, Any]) -> None:
    root = Path(project_root)
    for relative_path in CURRENT_REFERENCE_DOCS:
        path = root / relative_path
        if not path.is_file():
            raise ReleaseStateError(f"current status reference document is missing: {relative_path}")
        text = path.read_text(encoding="utf-8")
        if "CURRENT_RELEASE_STATUS.md" not in text:
            raise ReleaseStateError(f"{relative_path} must link to CURRENT_RELEASE_STATUS.md")
        for pattern in CURRENT_DRIFT_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                raise ReleaseStateError(
                    f"{relative_path} contains a stale or unsupported current-state claim: {match.group(0)!r}"
                )

    readme = (root / "README.md").read_text(encoding="utf-8")
    if "PDF.js canvas renderer" not in readme or "native fallback" not in readme:
        raise ReleaseStateError("README must describe PDF.js as primary with a native fallback")

    generated = render_current_status(manifest)
    manual = manifest["manual_validation"]
    if (
        manual["reader_runtime"]["status"] != "VERIFIED"
        and re.search(r"Reader runtime\s*\|\s*VERIFIED\b", generated)
    ):
        raise ReleaseStateError("generated output claims completed Reader runtime without evidence")


def render_output(
    manifest_path: Path = MANIFEST_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    validate_documents: bool = True,
) -> Path:
    manifest = load_manifest(manifest_path)
    validate_manifest(manifest)
    if validate_documents:
        validate_current_documents(Path(manifest_path).resolve().parents[1], manifest)
    content = render_current_status(manifest).encode("utf-8")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or destination.read_bytes() != content:
        destination.write_bytes(content)
    return destination


def _normalize_newlines(content: bytes) -> str:
    """Decode UTF-8 and normalize only CRLF/lone-CR line endings to LF."""

    return content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def check_release_state(
    manifest_path: Path = MANIFEST_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    validate_documents: bool = True,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(manifest_path)
        validate_manifest(manifest)
        if validate_documents:
            validate_current_documents(Path(manifest_path).resolve().parents[1], manifest)
        expected = render_current_status(manifest)
        destination = Path(output_path)
        if not destination.is_file():
            errors.append(f"generated output is missing: {destination.name}")
        else:
            try:
                actual = _normalize_newlines(destination.read_bytes())
            except UnicodeDecodeError:
                actual = ""
            if actual != expected:
                errors.append(f"generated output is stale: {destination.name}; run --render")
    except (OSError, json.JSONDecodeError, ReleaseStateError) as exc:
        errors.append(str(exc))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render or validate the canonical current release state.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--render", action="store_true", help="render the controlled current-status document")
    mode.add_argument("--check", action="store_true", help="check schema, invariants, documents, and generated output")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)

    if args.render:
        try:
            destination = render_output(args.manifest, args.output)
        except (OSError, json.JSONDecodeError, ReleaseStateError) as exc:
            print(f"Release-state render failed: {exc}")
            return 1
        print(f"Release-state output rendered: {destination.name}")
        return 0

    errors = check_release_state(args.manifest, args.output)
    if errors:
        for error in errors:
            print(f"Release-state check failed: {error}")
        return 1
    print("Release-state check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
