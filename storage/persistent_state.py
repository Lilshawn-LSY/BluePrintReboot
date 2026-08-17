from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from storage.identities import is_safe_paper_id


JsonShape = Literal["list", "object", "list_or_object", "candidate_reviews"]


@dataclass(frozen=True)
class JsonStoreDefinition:
    relative_path: str
    shape: JsonShape
    item_objects: bool = False
    include_in_backup: bool = True


PERSISTENT_JSON_STORES = (
    JsonStoreDefinition("data/projects/projects.json", "list", item_objects=True),
    JsonStoreDefinition("data/projects/project_links.json", "list", item_objects=True),
    JsonStoreDefinition("data/tag_candidate_reviews.json", "candidate_reviews"),
    JsonStoreDefinition("data/note_imports.json", "list", item_objects=True),
    JsonStoreDefinition("data/lifecycle_decisions.json", "list", item_objects=True),
    JsonStoreDefinition("data/settings.json", "object"),
    JsonStoreDefinition("config/settings.json", "object"),
    JsonStoreDefinition("config/tag_rules.json", "list_or_object"),
    JsonStoreDefinition("config/canonical_tags.json", "list_or_object"),
    JsonStoreDefinition("config/tag_book/tag_book.json", "object"),
    JsonStoreDefinition("config/tag_book/method_lexicon.json", "object"),
    JsonStoreDefinition("config/tag_book/normalization_rules.json", "object"),
    JsonStoreDefinition("config/tag_book/blocked_terms.json", "object"),
    JsonStoreDefinition("config/tag_book/candidate_patterns.json", "object"),
)


BACKUP_FILE_PATHS = tuple(
    definition.relative_path
    for definition in PERSISTENT_JSON_STORES
    if definition.include_in_backup
)


def json_shape_error(definition: JsonStoreDefinition, value: object) -> str | None:
    if definition.shape == "list":
        if not isinstance(value, list):
            return "must contain a JSON list"
        if definition.item_objects and any(not isinstance(item, dict) for item in value):
            return "must contain only JSON objects"
        return _list_item_shape_error(definition.relative_path, value)
    if definition.shape == "object":
        return None if isinstance(value, dict) else "must contain a JSON object"
    if definition.shape == "list_or_object":
        return None if isinstance(value, (list, dict)) else "must contain a JSON list or object"
    if not isinstance(value, dict):
        return "must contain a JSON object"
    papers = value.get("papers")
    if not isinstance(papers, dict):
        return "papers must contain a JSON object"
    for paper_id, context in papers.items():
        if not is_safe_paper_id(paper_id) or not isinstance(context, dict):
            return "papers must contain object contexts keyed by safe paper_id"
        candidates = context.get("candidates")
        if not isinstance(candidates, list) or any(not isinstance(item, dict) for item in candidates):
            return "each paper context must contain a candidates list of objects"
        for index, candidate in enumerate(candidates):
            required = ("candidate_id", "tag_text", "normalized_tag", "state")
            if any(not isinstance(candidate.get(field), str) or not candidate[field].strip() for field in required):
                return f"candidate {index} is missing required string fields"
            evidence = candidate.get("evidence", [])
            if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
                return f"candidate {index} evidence must be a list of objects"
    return None


def note_block_shape_error(value: object, *, paper_id: str) -> str | None:
    if not isinstance(value, list):
        return "must contain a JSON list"
    seen: set[str] = set()
    allowed_types = {"summary", "claim", "method", "evidence", "question", "idea", "limitation"}
    for index, block in enumerate(value):
        if not isinstance(block, dict):
            return f"item {index} must be a JSON object"
        block_id = block.get("id")
        stored_paper_id = block.get("paper_id", paper_id)
        if not isinstance(block_id, str) or not block_id.strip():
            return f"item {index} requires a non-empty id"
        if block_id in seen:
            return f"item {index} duplicates note-block id {block_id}"
        seen.add(block_id)
        if stored_paper_id != paper_id:
            return f"item {index} paper_id does not match its storage file"
        if block.get("block_type") not in allowed_types:
            return f"item {index} has an invalid block_type"
    return None


def _list_item_shape_error(relative_path: str, value: list[object]) -> str | None:
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return f"item {index} must be a JSON object"
        if relative_path == "data/projects/projects.json":
            required = ("id", "name", "status", "priority")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                return f"project item {index} is missing required string fields"
            if not isinstance(item.get("tags", []), list):
                return f"project item {index} tags must be a list"
        elif relative_path == "data/projects/project_links.json":
            required = ("id", "project_id", "target_type", "target_id", "link_type")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                return f"project-link item {index} is missing required string fields"
            if item.get("target_type") not in {"paper", "note_block"}:
                return f"project-link item {index} has an invalid target_type"
            if not isinstance(item.get("paper_id", ""), str):
                return f"project-link item {index} paper_id must be a string"
        elif relative_path == "data/note_imports.json":
            required = ("import_id", "target_paper_id", "source_filename", "import_mode")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                return f"note-import item {index} is missing required string fields"
            if not is_safe_paper_id(item.get("target_paper_id")):
                return f"note-import item {index} has an unsafe target_paper_id"
            if not isinstance(item.get("created_block_ids", []), list):
                return f"note-import item {index} created_block_ids must be a list"
        elif relative_path == "data/lifecycle_decisions.json":
            required = ("decision_type", "workspace_relative_path", "pdf_sha256")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                return f"lifecycle item {index} is missing required string fields"
    return None
