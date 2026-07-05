from __future__ import annotations

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
from services.tag_book import CATEGORY_VALUES, save_tag_book_canonical_registry
from storage.atomic_json import atomic_write_json
from storage.index_store import save_index
from storage.paths import INDEX_CSV


CANONICAL_TAG_CATEGORIES = CATEGORY_VALUES

TAG_MANAGER_FILTERS = ("all", "unknown", "canonical", "alias-resolved", "ambiguous/short")


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
