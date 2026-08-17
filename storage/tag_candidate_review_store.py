from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from storage.atomic_json import JsonShapeError, atomic_write_json, read_json_file
from storage.identities import is_safe_paper_id
from storage.paths import TAG_CANDIDATE_REVIEWS_JSON


STORE_VERSION = "1"


def load_tag_candidate_reviews(path: Path = TAG_CANDIDATE_REVIEWS_JSON) -> dict[str, Any]:
    """Load persisted per-paper review contexts without synthesizing replacements.

    A missing store is the normal empty state. A corrupt or incorrectly shaped store
    deliberately raises through the atomic JSON boundary so writes remain blocked.
    """

    target = Path(path)
    raw = read_json_file(
        target,
        default={"version": STORE_VERSION, "papers": {}},
        store_name="Tag candidate review store",
    )
    if not isinstance(raw, Mapping):
        raise JsonShapeError(target, "Tag candidate review store must contain an object")
    papers = raw.get("papers", {})
    if not isinstance(papers, Mapping):
        raise JsonShapeError(target, "Tag candidate review store papers must contain an object")
    normalized_papers: dict[str, dict[str, Any]] = {}
    for paper_id, context in papers.items():
        if not is_safe_paper_id(paper_id) or not isinstance(context, Mapping):
            raise JsonShapeError(target, "Tag candidate review contexts must be objects keyed by paper id")
        candidates = context.get("candidates", [])
        if not isinstance(candidates, list) or any(not isinstance(item, Mapping) for item in candidates):
            raise JsonShapeError(target, "Tag candidate review candidates must be a list of objects")
        normalized_papers[paper_id] = {
            "candidates": [dict(item) for item in candidates],
        }
    return {"version": str(raw.get("version", STORE_VERSION)), "papers": normalized_papers}


def save_tag_candidate_reviews(
    payload: Mapping[str, Any],
    path: Path = TAG_CANDIDATE_REVIEWS_JSON,
) -> Path:
    papers = payload.get("papers", {}) if isinstance(payload, Mapping) else {}
    if not isinstance(papers, Mapping):
        raise ValueError("Tag candidate review store papers must be an object.")
    serialized_papers: dict[str, dict[str, Any]] = {}
    for paper_id, context in papers.items():
        if not is_safe_paper_id(paper_id) or not isinstance(context, Mapping):
            raise ValueError("Tag candidate review contexts require safe paper IDs and object values.")
        candidates = context.get("candidates", [])
        if not isinstance(candidates, list) or any(not isinstance(item, Mapping) for item in candidates):
            raise ValueError("Tag candidate review candidates must be a list of objects.")
        serialized_papers[str(paper_id)] = {
            "candidates": [dict(item) for item in candidates]
        }
    serialized = {
        "version": str(payload.get("version", STORE_VERSION)) if isinstance(payload, Mapping) else STORE_VERSION,
        "papers": serialized_papers,
    }
    return atomic_write_json(
        Path(path),
        serialized,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        trailing_newline=True,
    )
