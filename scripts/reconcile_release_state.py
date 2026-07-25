from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "tracker_sync_status.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "CURRENT_RELEASE_STATUS.md"
SCHEMA_VERSION = "3.0"
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
    "docs/release_notes/v1.4.0.md",
)
REQUIRED_AUTOMATED_CHECKS = frozenset(
    {
        "pr_head_ci",
        "post_merge_main_ci",
        "local_smoke",
        "full_pytest",
        "focused_pdf_api",
        "focused_release_version",
        "frontend_lint",
        "frontend_production_build",
        "frontend_node_tests",
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
    re.compile(r"Manual PDF\.js Reader runtime\s*\|\s*(?:VERIFIED|NOT PERFORMED|NOT VERIFIED)\b", re.IGNORECASE),
    re.compile(r"Current v1\.4\.0[^\n]*(?:smoke|pytest|Node tests)\s+\d", re.IGNORECASE),
    re.compile(r"v1\.4\.0[^\n]*manual[^\n]*(?:complete|passed|VERIFIED)\b", re.IGNORECASE),
    re.compile(r"\bReader (?:manual )?runtime\s*(?:is|:|\|)\s*\**VERIFIED\b", re.IGNORECASE),
    re.compile(r"\bStreamlit regression\s*(?:is|:|\|)\s*\**VERIFIED\b", re.IGNORECASE),
    re.compile(r"browser's native PDF capability", re.IGNORECASE),
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
    _text(evidence.get("summary"), f"{field}.evidence.summary")


def _validate_source_control(manifest: Mapping[str, Any]) -> None:
    source = _mapping(manifest.get("source_control"), "source_control")
    main = _mapping(source.get("main"), "source_control.main")
    if main.get("status") != "VERIFIED" or main.get("branch") != "main":
        raise ReleaseStateError("source_control.main must be VERIFIED for branch main")
    main_sha = _sha(main.get("commit_sha"), "source_control.main.commit_sha")
    _validate_evidence(main, "source_control.main")

    pull_request = _mapping(source.get("pull_request"), "source_control.pull_request")
    if pull_request.get("status") != "VERIFIED":
        raise ReleaseStateError("source_control.pull_request must be VERIFIED")
    if pull_request.get("number") != 4 or pull_request.get("state") != "MERGED":
        raise ReleaseStateError("source_control.pull_request must identify merged PR #4")
    if pull_request.get("target_branch") != "main":
        raise ReleaseStateError("source_control.pull_request.target_branch must be main")
    _sha(pull_request.get("head_commit_sha"), "source_control.pull_request.head_commit_sha")
    merge_sha = _sha(pull_request.get("merge_commit_sha"), "source_control.pull_request.merge_commit_sha")
    if merge_sha != main_sha:
        raise ReleaseStateError("merged PR #4 commit must equal the verified main commit")
    _text(pull_request.get("url"), "source_control.pull_request.url")
    _validate_evidence(pull_request, "source_control.pull_request")

    tag = _mapping(source.get("tag"), "source_control.tag")
    if tag.get("status") != "VERIFIED":
        raise ReleaseStateError("source_control.tag must be VERIFIED")
    expected_tag = f"v{manifest['product_version']}"
    if tag.get("name") != expected_tag:
        raise ReleaseStateError(f"source_control.tag.name must be {expected_tag}")
    if _sha(tag.get("target_commit_sha"), "source_control.tag.target_commit_sha") != main_sha:
        raise ReleaseStateError("verified tag target must equal the verified main commit")
    _sha(tag.get("object_sha"), "source_control.tag.object_sha")
    _validate_evidence(tag, "source_control.tag")


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

    source = _mapping(manifest["source_control"], "source_control")
    pull_request = _mapping(source["pull_request"], "source_control.pull_request")
    pr_ci = _mapping(checks["pr_head_ci"], "automated_validation.pr_head_ci")
    if pr_ci.get("status") != "VERIFIED":
        raise ReleaseStateError("PR-head CI must be VERIFIED")
    if pr_ci.get("event") != "pull_request":
        raise ReleaseStateError("PR-head CI event must be pull_request")
    if pr_ci.get("commit_sha") != pull_request.get("head_commit_sha"):
        raise ReleaseStateError("PR-head CI commit must equal PR #4 head commit")
    _text(pr_ci.get("run_id"), "automated_validation.pr_head_ci.run_id")
    _text(pr_ci.get("run_url"), "automated_validation.pr_head_ci.run_url")
    jobs = _mapping(pr_ci.get("jobs"), "automated_validation.pr_head_ci.jobs")
    if jobs != {"frontend": "success", "python": "success"}:
        raise ReleaseStateError("PR-head CI must record successful Python and frontend jobs")

    main_ci = _mapping(checks["post_merge_main_ci"], "automated_validation.post_merge_main_ci")
    if main_ci.get("status") != "NOT VERIFIED":
        raise ReleaseStateError("post-merge main CI must remain NOT VERIFIED without direct evidence")
    for field in ("run_id", "run_url", "commit_sha"):
        if main_ci.get(field) is not None:
            raise ReleaseStateError(f"post-merge main CI {field} must be null while NOT VERIFIED")
    if main_ci.get("jobs") != {} or main_ci.get("counts") is not None:
        raise ReleaseStateError("post-merge main CI cannot claim jobs or counts while NOT VERIFIED")

    smoke = _mapping(checks["local_smoke"], "automated_validation.local_smoke")
    if smoke.get("status") != "VERIFIED" or smoke.get("counts") is not None:
        raise ReleaseStateError("smoke must be VERIFIED without silently selected aggregate counts")
    conflicts = _list(smoke.get("conflicting_evidence"), "automated_validation.local_smoke.conflicting_evidence")
    if len(conflicts) < 2:
        raise ReleaseStateError("smoke must preserve at least two conflicting count records")
    count_signatures: set[tuple[tuple[str, int], ...]] = set()
    for index, raw_conflict in enumerate(conflicts):
        conflict = _mapping(raw_conflict, f"automated_validation.local_smoke.conflicting_evidence[{index}]")
        _text(conflict.get("reference"), f"automated_validation.local_smoke.conflicting_evidence[{index}].reference")
        _text(conflict.get("date"), f"automated_validation.local_smoke.conflicting_evidence[{index}].date")
        counts = _mapping(
            conflict.get("counts"),
            f"automated_validation.local_smoke.conflicting_evidence[{index}].counts",
        )
        if set(counts) != {"failed", "passed", "warnings"}:
            raise ReleaseStateError("each conflicting smoke record must contain passed, warnings, and failed")
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
            raise ReleaseStateError("conflicting smoke counts must be non-negative integers")
        if counts["failed"] != 0:
            raise ReleaseStateError("VERIFIED smoke conflict records must each report zero failures")
        count_signatures.add(tuple(sorted(counts.items())))
    if len(count_signatures) < 2:
        raise ReleaseStateError("smoke conflicting evidence must contain genuinely different counts")


def _validate_manual_validation(manifest: Mapping[str, Any]) -> None:
    manual = _mapping(manifest.get("manual_validation"), "manual_validation")
    reader = _mapping(manual.get("reader_runtime"), "manual_validation.reader_runtime")
    if reader.get("status") != "PARTIALLY VERIFIED":
        raise ReleaseStateError("Reader runtime must be PARTIALLY VERIFIED")
    _validate_evidence(reader, "manual_validation.reader_runtime")
    checks = _mapping(reader.get("checks"), "manual_validation.reader_runtime.checks")
    if set(checks) != REQUIRED_MANUAL_CHECKS:
        missing = sorted(REQUIRED_MANUAL_CHECKS - set(checks))
        extra = sorted(set(checks) - REQUIRED_MANUAL_CHECKS)
        raise ReleaseStateError(f"Reader runtime checks differ; missing={missing}, extra={extra}")
    statuses: set[str] = set()
    for check_id, raw_item in checks.items():
        item = _mapping(raw_item, f"manual_validation.reader_runtime.checks.{check_id}")
        statuses.add(str(item.get("status")))
        _validate_evidence(item, f"manual_validation.reader_runtime.checks.{check_id}")
    if "VERIFIED" not in statuses or "NOT VERIFIED" not in statuses:
        raise ReleaseStateError("PARTIALLY VERIFIED Reader runtime needs passed and pending checks")

    streamlit = _mapping(manual.get("streamlit_regression"), "manual_validation.streamlit_regression")
    if streamlit.get("status") != "NOT VERIFIED":
        raise ReleaseStateError("current Streamlit regression must remain NOT VERIFIED")
    _validate_evidence(streamlit, "manual_validation.streamlit_regression")


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
    _text(external.get("last_reconciled"), "external_tracker.last_reconciled")
    tasks = _list(external.get("tasks"), "external_tracker.tasks")
    expected_ids = [f"R-{number:03d}" for number in range(1, 26)]
    task_ids = [task.get("task_id") if isinstance(task, dict) else None for task in tasks]
    if task_ids != expected_ids:
        raise ReleaseStateError("external tracker tasks must be ordered R-001 through R-025")
    for index, raw_task in enumerate(tasks):
        task = _mapping(raw_task, f"external_tracker.tasks[{index}]")
        if set(task) != {"disposition", "evidence", "last_verified", "status", "task_id"}:
            raise ReleaseStateError("external tracker tasks must contain exactly the five CSV fields")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or TASK_ID_PATTERN.fullmatch(task_id) is None:
            raise ReleaseStateError("external tracker task_id must match R-000")
        _text(task.get("evidence"), f"external_tracker.{task_id}.evidence")
        _text(task.get("disposition"), f"external_tracker.{task_id}.disposition")
        if _text(task.get("last_verified"), f"external_tracker.{task_id}.last_verified") != manifest["as_of"]:
            raise ReleaseStateError(f"external_tracker.{task_id}.last_verified must equal manifest as_of")

    by_id = {task["task_id"]: task for task in tasks}
    derived_tasks = {
        "R-017": manifest["recurring_operational_procedures"]["clean_pc_restore"],
        "R-018": manifest["manual_validation"]["reader_runtime"],
        "R-019": manifest["implementation_state"],
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
        "implementation_state",
        "source_control",
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
    if manifest.get("product_version") != "1.4.0":
        raise ReleaseStateError("product_version must identify the current 1.4.0 product")
    if manifest.get("release_name") != "v1.4.0-pdfjs-reader-foundation":
        raise ReleaseStateError("release_name must identify the current v1.4.0 release")
    _text(manifest.get("as_of"), "as_of")
    _validate_controlled_statuses(manifest)
    _validate_private_values(manifest)

    implementation = _mapping(manifest.get("implementation_state"), "implementation_state")
    if implementation.get("status") != "VERIFIED":
        raise ReleaseStateError("implementation_state must be VERIFIED")
    _text(implementation.get("scope"), "implementation_state.scope")
    _validate_evidence(implementation, "implementation_state")

    _validate_source_control(manifest)
    _validate_automated_validation(manifest)
    _validate_manual_validation(manifest)
    _validate_publication_and_operations(manifest)

    unresolved = _mapping(manifest.get("unresolved_evidence"), "unresolved_evidence")
    smoke_conflict = _mapping(unresolved.get("smoke_count_conflict"), "unresolved_evidence.smoke_count_conflict")
    if smoke_conflict.get("status") != "NOT VERIFIED":
        raise ReleaseStateError("unresolved smoke count conflict must remain NOT VERIFIED")
    _validate_evidence(smoke_conflict, "unresolved_evidence.smoke_count_conflict")

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
    source = manifest["source_control"]
    automated = manifest["automated_validation"]
    manual = manifest["manual_validation"]
    publication = manifest["publication_state"]
    restore = manifest["recurring_operational_procedures"]["clean_pc_restore"]

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
        f"- Product version: `{manifest['product_version']}`",
        f"- Release name: `{manifest['release_name']}`",
        f"- Implementation state: **{manifest['implementation_state']['status']}**",
        f"- Next milestone: **{manifest['next_milestone']['status']}** — {manifest['next_milestone']['name']}",
        "",
        "## Current state summary",
        "",
        "| Area | Status | Evidence |",
        "|---|---|---|",
        f"| Implementation | {manifest['implementation_state']['status']} | {_escape_cell(_evidence_summary(manifest['implementation_state']))} |",
        f"| PR #4 | {source['pull_request']['status']} | Merged into `main` at `{source['pull_request']['merge_commit_sha']}`. |",
        f"| v1.4.0 tag | {source['tag']['status']} | Tag targets `{source['tag']['target_commit_sha']}`. |",
        f"| PR-head GitHub Actions | {automated['pr_head_ci']['status']} | Run `{automated['pr_head_ci']['run_id']}`; Python and frontend jobs succeeded. |",
        f"| Post-merge `main` GitHub Actions | {automated['post_merge_main_ci']['status']} | {_escape_cell(automated['post_merge_main_ci']['evidence']['summary'])} |",
        f"| Reader runtime | {manual['reader_runtime']['status']} | Passed and pending checks are separated below. |",
        f"| Streamlit regression | {manual['streamlit_regression']['status']} | {_escape_cell(manual['streamlit_regression']['evidence']['summary'])} |",
        f"| GitHub Release publication | {publication['github_release']['status']} | {_escape_cell(publication['github_release']['evidence']['summary'])} |",
        f"| Clean-PC restore | {restore['status']} | Recurring operational procedure; no rehearsal is claimed. |",
        "",
        "## Source-control state",
        "",
        f"- Verified `main` commit: `{source['main']['commit_sha']}`.",
        f"- PR #4: [{source['pull_request']['url']}]({source['pull_request']['url']}); head `{source['pull_request']['head_commit_sha']}`, merge `{source['pull_request']['merge_commit_sha']}`.",
        f"- Tag `{source['tag']['name']}` is verified at `{source['tag']['target_commit_sha']}`.",
        "- Tag existence is source-control evidence only. It does not imply GitHub Release publication.",
        "",
        "## Automated validation",
        "",
        "| Check | Status | Scope | Counts | Evidence |",
        "|---|---|---|---|---|",
    ]
    for check_id, item in automated.items():
        counts = _format_counts(item.get("counts"))
        if check_id == "local_smoke":
            records = [
                f"{_format_counts(record['counts'])} ({record['reference']})"
                for record in item["conflicting_evidence"]
            ]
            counts = "Conflicting records: " + "; ".join(records)
        label = check_id.replace("_", " ").title().replace("Ci", "CI").replace("Pytest", "pytest")
        lines.append(
            f"| {label} | {item['status']} | {_escape_cell(item['scope'])} | "
            f"{_escape_cell(counts)} | {_escape_cell(_evidence_summary(item))} |"
        )

    lines.extend(
        [
            "",
            "The smoke result is VERIFIED because both committed records report zero failures. "
            "Its pass/warning counts remain explicitly unresolved; no value is selected silently.",
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
            f"- Smoke pass/warning count: **{manifest['unresolved_evidence']['smoke_count_conflict']['status']}**. "
            f"{manifest['unresolved_evidence']['smoke_count_conflict']['evidence']['summary']}",
            f"- Post-merge `main` workflow: **{automated['post_merge_main_ci']['status']}**. "
            f"{automated['post_merge_main_ci']['evidence']['summary']}",
            f"- API offline/restart recovery, large-PDF behavior, detailed Range inspection, "
            f"and separate Streamlit regression remain **NOT VERIFIED**.",
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
        expected = render_current_status(manifest).encode("utf-8")
        destination = Path(output_path)
        if not destination.is_file():
            errors.append(f"generated output is missing: {destination.name}")
        elif destination.read_bytes() != expected:
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
