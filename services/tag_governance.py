from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ingest.tag_suggester import (
    apply_tag_merge_to_records,
    build_tag_alias_index,
    load_canonical_tags,
    normalize_tag,
    preview_tag_merge,
    resolve_canonical_tag,
)
from services import tag_book
from services.tag_book import CATEGORY_VALUES, save_tag_book_canonical_registry
from storage.atomic_json import atomic_write_json
from storage.index_store import save_index
from storage.paths import INDEX_CSV, PROJECT_ROOT
from storage.workspace_lock import (
    WorkspaceLockUnavailable,
    workspace_root_for_path,
    workspace_write_lock,
)


CANONICAL_TAG_CATEGORIES = CATEGORY_VALUES

TAG_MANAGER_FILTERS = ("all", "unknown", "canonical", "alias-resolved", "ambiguous/short")


class TagGovernanceError(Exception):
    """Base class for controlled canonical Tag Book command failures."""


class TagGovernanceConflict(TagGovernanceError):
    """The supplied Tag Book revision is no longer current."""


class TagGovernanceInvalid(TagGovernanceError):
    """The requested canonical-tag mutation violates registry invariants."""


class TagGovernanceNotFound(TagGovernanceError):
    """The requested canonical tag or alias is not present."""


class TagGovernanceUnavailable(TagGovernanceError):
    """The Tag Book could not be read or written consistently."""


@dataclass(frozen=True)
class TagGovernanceResult:
    status: str
    tag: dict[str, Any]
    registry_revision: str


def canonical_tag_registry_revision(loaded_book: dict[str, Any]) -> str:
    """Return a deterministic optimistic-concurrency token for canonical records."""

    records = [
        tag_book._serializable_tag_record(record)  # type: ignore[attr-defined]
        for _, record in sorted(loaded_book.get("tags", {}).items())
        if isinstance(record, dict)
    ]
    encoded = json.dumps(
        {"version": str(loaded_book.get("version", "2")), "tags": records},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_tag_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_key": str(record["canonical"]),
        "label": str(record.get("label", "")),
        "category": str(record.get("category", "other")),
        "aliases": [str(alias) for alias in record.get("aliases", [])],
        "status": str(record.get("status", "active")),
        "suggestion_strength": int(record.get("suggestion_strength", 1)),
        "description": str(record.get("description", "")),
    }


class CanonicalTagGovernanceService:
    """The only mutable canonical Tag Book boundary.

    Canonical keys are stable identities. This service intentionally exposes
    metadata, aliases, and deprecation rather than destructive deletion or key
    renaming. It never touches Paper records, including legacy/noncanonical tag
    values already stored on Papers.
    """

    def __init__(
        self,
        *,
        tag_book_dir: Path = tag_book.DEFAULT_TAG_BOOK_DIR,
        workspace_root: Path | None = None,
    ) -> None:
        self.tag_book_dir = Path(tag_book_dir)
        self.workspace_root = Path(workspace_root) if workspace_root is not None else _tag_book_workspace_root(self.tag_book_dir)

    def snapshot(self) -> tuple[list[dict[str, Any]], str]:
        loaded = self._load()
        items = [canonical_tag_item(record) for _, record in sorted(loaded["tags"].items())]
        return items, canonical_tag_registry_revision(loaded)

    def create_tag(
        self,
        *,
        label: str,
        category: str,
        description: str = "",
        suggestion_strength: int = 1,
        expected_revision: str,
    ) -> TagGovernanceResult:
        clean_label = _required_text(label, "Canonical tag label")
        canonical = tag_book.normalize_tag(clean_label)
        if not canonical:
            raise TagGovernanceInvalid("Canonical tag label must not be empty.")
        if category not in CANONICAL_TAG_CATEGORIES:
            raise TagGovernanceInvalid("Unsupported canonical tag category.")
        strength = _strength(suggestion_strength)
        description_value = _description(description)
        with self._locked():
            loaded = self._load()
            self._require_revision(loaded, expected_revision)
            identities = _tag_identities(loaded)
            if canonical in identities:
                raise TagGovernanceInvalid("Canonical tag name collides with an existing canonical tag or alias.")
            record = {
                "canonical": canonical,
                "label": clean_label,
                "category": category,
                "aliases": [],
                "status": "active",
                "suggestion_strength": strength,
                "description": description_value,
                "created_from": "tag_governance",
            }
            loaded["tags"][canonical] = record
            self._save(loaded)
            return TagGovernanceResult("created", canonical_tag_item(record), canonical_tag_registry_revision(loaded))

    def update_tag(
        self,
        canonical_key: str,
        *,
        changes: dict[str, Any],
        expected_revision: str,
    ) -> TagGovernanceResult:
        canonical = self._canonical_key(canonical_key)
        allowed = {"label", "category", "description", "suggestion_strength"}
        if not changes or set(changes) - allowed:
            raise TagGovernanceInvalid("Only label, category, description, and suggestion strength can be edited.")
        with self._locked():
            loaded = self._load()
            self._require_revision(loaded, expected_revision)
            record = loaded["tags"].get(canonical)
            if not isinstance(record, dict):
                raise TagGovernanceNotFound
            updated = dict(record)
            if "label" in changes:
                label = _required_text(changes["label"], "Canonical tag label")
                label_identity = tag_book.normalize_tag(label)
                owner = _tag_identities(loaded).get(label_identity)
                if owner is not None and owner != canonical:
                    raise TagGovernanceInvalid("Canonical tag label collides with an existing canonical tag or alias.")
                updated["label"] = label
            if "category" in changes:
                category = changes["category"]
                if not isinstance(category, str) or category not in CANONICAL_TAG_CATEGORIES:
                    raise TagGovernanceInvalid("Unsupported canonical tag category.")
                updated["category"] = category
            if "description" in changes:
                updated["description"] = _description(changes["description"])
            if "suggestion_strength" in changes:
                updated["suggestion_strength"] = _strength(changes["suggestion_strength"])
            loaded["tags"][canonical] = updated
            if updated == record:
                return TagGovernanceResult("no_op", canonical_tag_item(record), canonical_tag_registry_revision(loaded))
            self._save(loaded)
            return TagGovernanceResult("saved", canonical_tag_item(updated), canonical_tag_registry_revision(loaded))

    def add_alias(
        self,
        canonical_key: str,
        *,
        alias: str,
        expected_revision: str,
    ) -> TagGovernanceResult:
        canonical = self._canonical_key(canonical_key)
        alias_value = _required_text(alias, "Alias")
        alias_identity = tag_book.normalize_tag(alias_value)
        if not alias_identity:
            raise TagGovernanceInvalid("Alias must not be empty.")
        with self._locked():
            loaded = self._load()
            self._require_revision(loaded, expected_revision)
            record = loaded["tags"].get(canonical)
            if not isinstance(record, dict):
                raise TagGovernanceNotFound
            if alias_identity == canonical:
                raise TagGovernanceInvalid("A canonical tag cannot be added as its own alias.")
            if alias_identity in _tag_identities(loaded):
                raise TagGovernanceInvalid("Alias collides with an existing canonical tag or alias.")
            updated = dict(record)
            updated["aliases"] = [*list(record.get("aliases", [])), alias_value]
            loaded["tags"][canonical] = updated
            self._save(loaded)
            return TagGovernanceResult("saved", canonical_tag_item(updated), canonical_tag_registry_revision(loaded))

    def remove_alias(
        self,
        canonical_key: str,
        *,
        alias: str,
        expected_revision: str,
    ) -> TagGovernanceResult:
        canonical = self._canonical_key(canonical_key)
        alias_identity = tag_book.normalize_tag(alias)
        if not alias_identity:
            raise TagGovernanceInvalid("Alias must not be empty.")
        with self._locked():
            loaded = self._load()
            self._require_revision(loaded, expected_revision)
            record = loaded["tags"].get(canonical)
            if not isinstance(record, dict):
                raise TagGovernanceNotFound
            aliases = list(record.get("aliases", []))
            retained = [value for value in aliases if tag_book.normalize_tag(value) != alias_identity]
            if len(retained) == len(aliases):
                raise TagGovernanceNotFound
            updated = dict(record)
            updated["aliases"] = retained
            loaded["tags"][canonical] = updated
            self._save(loaded)
            return TagGovernanceResult("saved", canonical_tag_item(updated), canonical_tag_registry_revision(loaded))

    def deprecate_tag(self, canonical_key: str, *, expected_revision: str) -> TagGovernanceResult:
        canonical = self._canonical_key(canonical_key)
        with self._locked():
            loaded = self._load()
            self._require_revision(loaded, expected_revision)
            record = loaded["tags"].get(canonical)
            if not isinstance(record, dict):
                raise TagGovernanceNotFound
            if str(record.get("status", "active")).strip().lower() == "deprecated":
                return TagGovernanceResult("no_op", canonical_tag_item(record), canonical_tag_registry_revision(loaded))
            updated = dict(record)
            updated["status"] = "deprecated"
            loaded["tags"][canonical] = updated
            self._save(loaded)
            return TagGovernanceResult("deprecated", canonical_tag_item(updated), canonical_tag_registry_revision(loaded))

    def resolve(self, raw_value: str) -> dict[str, Any] | None:
        loaded = self._load()
        identity = tag_book.normalize_tag(raw_value)
        owner = _tag_identities(loaded).get(identity)
        if owner is None:
            return None
        record = loaded["tags"].get(owner)
        return canonical_tag_item(record) if isinstance(record, dict) else None

    @contextmanager
    def _locked(self):
        try:
            with workspace_write_lock(self.workspace_root):
                yield
        except WorkspaceLockUnavailable:
            raise TagGovernanceUnavailable from None

    def _load(self) -> dict[str, Any]:
        try:
            loaded = tag_book.load_tag_book(self.tag_book_dir)
            warnings = tag_book.validate_tag_book(loaded)
        except Exception:
            raise TagGovernanceUnavailable from None
        if warnings:
            raise TagGovernanceUnavailable
        return loaded

    def _save(self, loaded: dict[str, Any]) -> None:
        try:
            tag_book.save_tag_book(loaded, self.tag_book_dir)
        except Exception:
            raise TagGovernanceUnavailable from None

    def _require_revision(self, loaded: dict[str, Any], expected_revision: str) -> None:
        if canonical_tag_registry_revision(loaded) != expected_revision:
            raise TagGovernanceConflict

    @staticmethod
    def _canonical_key(value: str) -> str:
        canonical = tag_book.normalize_tag(value)
        if not canonical:
            raise TagGovernanceInvalid("Canonical tag identity must not be empty.")
        return canonical


def _tag_book_workspace_root(tag_book_dir: Path) -> Path:
    directory = Path(tag_book_dir).resolve(strict=False)
    return directory.parent.parent if directory.parent.name.casefold() == "config" else directory.parent


def _tag_identities(loaded: dict[str, Any]) -> dict[str, str]:
    identities: dict[str, str] = {}
    for canonical, raw_record in loaded.get("tags", {}).items():
        if not isinstance(raw_record, dict):
            continue
        for raw_value in (canonical, raw_record.get("label", ""), *raw_record.get("aliases", [])):
            identity = tag_book.normalize_tag(raw_value)
            if identity:
                identities[identity] = canonical
    return identities


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TagGovernanceInvalid(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise TagGovernanceInvalid(f"{field_name} must be between 1 and 200 characters.")
    return normalized


def _description(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2_000:
        raise TagGovernanceInvalid("Description must be a string of at most 2000 characters.")
    return value


def _strength(value: Any) -> int:
    if isinstance(value, bool):
        raise TagGovernanceInvalid("Suggestion strength must be an integer.")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise TagGovernanceInvalid("Suggestion strength must be an integer.") from None
    if normalized < 0 or normalized > 100:
        raise TagGovernanceInvalid("Suggestion strength must be between 0 and 100.")
    return normalized


def load_tag_manager_records(index_csv: str | Path = INDEX_CSV) -> list[dict]:
    path = Path(index_csv)
    if not path.exists() or path.stat().st_size == 0:
        return []
    return pd.read_csv(path, dtype=str).fillna("").to_dict("records")


def summarize_used_tags(records: list[dict], registry: dict) -> list[dict]:
    usage: dict[str, dict[str, Any]] = {}
    for record in records:
        seen_in_record: set[str] = set()
        for raw_tag in _split_tags(record.get("tags", "")):
            normalized = normalize_tag(raw_tag)
            if not normalized or normalized in seen_in_record:
                continue
            seen_in_record.add(normalized)
            item = usage.setdefault(
                normalized,
                {
                    "tag": raw_tag,
                    "normalized_tag": normalized,
                    "paper_ids": set(),
                    "paper_examples": [],
                },
            )
            paper_id = str(record.get("paper_id", ""))
            item["paper_ids"].add(paper_id or f"record-{id(record)}")
            if len(item["paper_examples"]) < 5:
                item["paper_examples"].append(
                    {
                        "paper_id": paper_id,
                        "title": str(record.get("title", "")).strip()
                        or str(record.get("filename", "")).strip()
                        or paper_id,
                    }
                )

    alias_index = build_tag_alias_index(registry)
    collisions = alias_index["collisions"]
    summaries: list[dict] = []
    for normalized, item in usage.items():
        canonical_tag = resolve_canonical_tag(normalized, registry)
        is_ambiguous = normalized in collisions
        is_short = len(normalized) <= 2
        if normalized in registry:
            status = "canonical"
            canonical_tag = normalized
        elif canonical_tag:
            status = "alias-resolved"
        else:
            status = "unknown"

        warnings = []
        if is_short:
            warnings.append("Short tag; explicit review required")
        if is_ambiguous:
            warnings.append("Ambiguous alias: " + ", ".join(collisions[normalized]))
        canonical_entry = registry.get(canonical_tag or "", {})
        summaries.append(
            {
                "tag": item["tag"],
                "normalized_tag": normalized,
                "paper_count": len(item["paper_ids"]),
                "status": status,
                "canonical_tag": canonical_tag or "",
                "category": str(canonical_entry.get("category", "")),
                "is_short": is_short,
                "is_ambiguous": is_ambiguous,
                "warning": "; ".join(warnings),
                "paper_examples": item["paper_examples"],
            }
        )
    return sorted(summaries, key=lambda item: (-item["paper_count"], item["normalized_tag"]))


def filter_used_tags(summaries: list[dict], selected_filter: str) -> list[dict]:
    if selected_filter == "all":
        return list(summaries)
    if selected_filter == "ambiguous/short":
        return [item for item in summaries if item.get("is_ambiguous") or item.get("is_short")]
    if selected_filter not in TAG_MANAGER_FILTERS:
        raise ValueError(f"Unknown tag filter: {selected_filter}")
    return [item for item in summaries if item.get("status") == selected_filter]


def preview_used_tag_merge(
    records: list[dict],
    source_tag: str,
    target_tag: str,
    registry: dict,
) -> dict:
    return preview_tag_merge(records, source_tag, target_tag, registry, exact_source=True)


def apply_used_tag_merge_to_index(
    source_tag: str,
    target_tag: str,
    registry: dict,
    index_csv: str | Path = INDEX_CSV,
) -> dict:
    with workspace_write_lock(workspace_root_for_path(Path(index_csv))):
        records = load_tag_manager_records(index_csv)
        preview = preview_used_tag_merge(records, source_tag, target_tag, registry)
        if preview["affected_records"]:
            merged = apply_tag_merge_to_records(
                records,
                source_tag,
                target_tag,
                registry,
                exact_source=True,
            )
            save_index(pd.DataFrame(merged), Path(index_csv))
        return preview


def register_tag_alias(
    raw_alias: str,
    target_tag: str,
    registry_path: str | Path | None = None,
) -> dict:
    root = workspace_root_for_path(Path(registry_path)) if registry_path else PROJECT_ROOT
    with workspace_write_lock(root):
        return _register_tag_alias_locked(raw_alias, target_tag, registry_path)


def _register_tag_alias_locked(
    raw_alias: str,
    target_tag: str,
    registry_path: str | Path | None,
) -> dict:
    registry = load_canonical_tags(registry_path)
    canonical_target = resolve_canonical_tag(target_tag, registry)
    if not canonical_target:
        raise ValueError(f"Canonical target '{target_tag}' does not exist or is ambiguous.")

    alias = str(raw_alias).strip()
    normalized_alias = normalize_tag(alias)
    if not normalized_alias:
        raise ValueError("Alias must not be empty.")
    owners = _alias_owners(normalized_alias, registry)
    if owners - {canonical_target}:
        raise ValueError(
            f"Alias '{alias}' collides with canonical tag(s): {', '.join(sorted(owners))}."
        )

    aliases = list(registry[canonical_target].get("aliases", []))
    if normalized_alias not in {normalize_tag(value) for value in aliases}:
        aliases.append(alias)
        registry[canonical_target]["aliases"] = aliases
        save_canonical_tags(registry, registry_path)
    return registry


def create_canonical_tag(
    raw_alias: str,
    label: str,
    category: str,
    registry_path: str | Path | None = None,
) -> dict:
    root = workspace_root_for_path(Path(registry_path)) if registry_path else PROJECT_ROOT
    with workspace_write_lock(root):
        return _create_canonical_tag_locked(raw_alias, label, category, registry_path)


def _create_canonical_tag_locked(
    raw_alias: str,
    label: str,
    category: str,
    registry_path: str | Path | None,
) -> dict:
    clean_label = str(label).strip()
    canonical_tag = normalize_tag(clean_label)
    alias = str(raw_alias).strip()
    if not canonical_tag:
        raise ValueError("Canonical tag label must not be empty.")
    if not normalize_tag(alias):
        raise ValueError("Selected library tag must not be empty.")
    if category not in CANONICAL_TAG_CATEGORIES:
        raise ValueError(f"Unsupported canonical tag category: {category}")

    registry = load_canonical_tags(registry_path)
    if canonical_tag in registry:
        raise ValueError(f"Canonical tag '{canonical_tag}' already exists.")
    for value in (canonical_tag, clean_label, alias):
        owners = _alias_owners(normalize_tag(value), registry)
        if owners:
            raise ValueError(
                f"'{value}' collides with canonical tag(s): {', '.join(sorted(owners))}."
            )

    registry[canonical_tag] = {
        "label": clean_label,
        "category": category,
        "aliases": [alias],
        "status": "active",
    }
    save_canonical_tags(registry, registry_path)
    return registry


def save_canonical_tags(registry: dict, path: str | Path | None = None) -> None:
    if path is None:
        save_tag_book_canonical_registry(registry)
        return

    registry_path = Path(path)
    atomic_write_json(registry_path, registry, ensure_ascii=False, indent=2, trailing_newline=True)


def _alias_owners(normalized_alias: str, registry: dict) -> set[str]:
    if not normalized_alias:
        return set()
    alias_index = build_tag_alias_index(registry)
    if normalized_alias in alias_index["collisions"]:
        return set(alias_index["collisions"][normalized_alias])
    owner = alias_index["alias_to_canonical"].get(normalized_alias)
    return {owner} if owner else set()


def _split_tags(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "")
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
