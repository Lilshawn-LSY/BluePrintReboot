from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypedDict

from services import tag_book
from storage.atomic_json import read_json_file
from storage.index_store import read_index_snapshot
from storage.paths import INDEX_CSV


class CanonicalTag(TypedDict):
    canonical_key: str
    label: str
    category: str
    aliases: list[str]
    status: str
    suggestion_strength: int


class CandidateQualityCounts(TypedDict):
    high: int
    medium: int
    weak: int
    rejected: int


class CandidateSummary(TypedDict):
    availability: Literal["available", "unavailable"]
    state: Literal["populated", "empty", "unavailable"]
    source: Literal["paper_index", "none"]
    evaluated_paper_count: int
    candidate_count: int
    known_canonical_match_count: int
    quality_counts: CandidateQualityCounts


def _require_mapping_json(path: Path) -> None:
    if not path.is_file():
        return
    value = read_json_file(path, store_name=f"Tag Book JSON file {path.name}")
    if not isinstance(value, Mapping):
        raise ValueError("Tag Book configuration must be an object.")


def _strict_tag_book(
    *,
    tag_book_dir: Path | None = None,
    legacy_rule_path: Path | None = None,
    legacy_canonical_tag_path: Path | None = None,
) -> dict[str, Any]:
    base_dir = Path(tag_book_dir) if tag_book_dir is not None else tag_book.DEFAULT_TAG_BOOK_DIR
    primary_path = base_dir / "tag_book.json"
    rule_path = (
        Path(legacy_rule_path)
        if legacy_rule_path is not None
        else tag_book.LEGACY_RULE_PATH
    )
    registry_path = (
        Path(legacy_canonical_tag_path)
        if legacy_canonical_tag_path is not None
        else tag_book.LEGACY_CANONICAL_TAG_PATH
    )
    if primary_path.is_file():
        raw = read_json_file(primary_path, store_name="Tag Book JSON file tag_book.json")
        if not isinstance(raw, Mapping):
            raise ValueError("Tag Book must be an object.")
        raw_tags = raw.get("tags", raw)
        if not isinstance(raw_tags, (list, Mapping)):
            raise ValueError("Tag Book tags must be a list or object.")
        records = raw_tags.values() if isinstance(raw_tags, Mapping) else raw_tags
        if any(not isinstance(record, Mapping) for record in records):
            raise ValueError("Each canonical tag must be an object.")
    else:
        _require_mapping_json(rule_path)
        _require_mapping_json(registry_path)

    loaded = tag_book.load_tag_book(
        base_dir,
        legacy_rule_path=rule_path,
        legacy_canonical_tag_path=registry_path,
    )
    raw_records = loaded.get("raw_tag_records")
    if not isinstance(raw_records, list):
        raise ValueError("Tag Book records must be a list.")
    normalized_keys = [
        tag_book.normalize_tag(record.get("canonical") or record.get("label"))
        for record in raw_records
        if isinstance(record, Mapping)
    ]
    canonical_keys = [key for key in normalized_keys if key]
    if len(canonical_keys) != len(set(canonical_keys)):
        raise ValueError("Canonical tag identities must be unique.")
    return loaded


def build_canonical_tag_items(
    *,
    tag_book_dir: Path | None = None,
    legacy_rule_path: Path | None = None,
    legacy_canonical_tag_path: Path | None = None,
) -> tuple[list[CanonicalTag], bool]:
    loaded = _strict_tag_book(
        tag_book_dir=tag_book_dir,
        legacy_rule_path=legacy_rule_path,
        legacy_canonical_tag_path=legacy_canonical_tag_path,
    )
    tags = loaded.get("tags")
    if not isinstance(tags, Mapping):
        raise ValueError("Canonical tags must be an object.")
    items: list[CanonicalTag] = []
    for canonical, raw_record in tags.items():
        if not isinstance(raw_record, Mapping):
            raise ValueError("Each canonical tag must be an object.")
        aliases = raw_record.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            raise ValueError("Canonical tag aliases must be strings.")
        strength = raw_record.get("suggestion_strength", 1)
        if isinstance(strength, bool) or not isinstance(strength, int):
            raise ValueError("Canonical tag suggestion strength must be an integer.")
        items.append(
            {
                "canonical_key": str(canonical),
                "label": str(raw_record.get("label", "")),
                "category": str(raw_record.get("category", "")),
                "aliases": sorted(
                    (alias.strip() for alias in aliases if alias.strip()),
                    key=lambda alias: (alias.casefold(), alias),
                ),
                "status": str(raw_record.get("status", "")),
                "suggestion_strength": strength,
            }
        )
    return items, bool(loaded.get("loaded_from_fallback", False))


def _unavailable_candidate_summary() -> CandidateSummary:
    return {
        "availability": "unavailable",
        "state": "unavailable",
        "source": "none",
        "evaluated_paper_count": 0,
        "candidate_count": 0,
        "known_canonical_match_count": 0,
        "quality_counts": {"high": 0, "medium": 0, "weak": 0, "rejected": 0},
    }


def build_candidate_summary(
    *,
    tag_book_dir: Path | None = None,
    legacy_rule_path: Path | None = None,
    legacy_canonical_tag_path: Path | None = None,
    index_csv: Path | None = None,
) -> CandidateSummary:
    loaded = _strict_tag_book(
        tag_book_dir=tag_book_dir,
        legacy_rule_path=legacy_rule_path,
        legacy_canonical_tag_path=legacy_canonical_tag_path,
    )
    source_path = Path(index_csv) if index_csv is not None else INDEX_CSV
    if not source_path.is_file():
        return _unavailable_candidate_summary()
    try:
        records = read_index_snapshot(source_path).to_dict("records")
    except Exception:
        return _unavailable_candidate_summary()

    known_matches: set[str] = set()
    candidate_qualities: dict[str, str] = {}
    quality_rank = {"rejected": 0, "weak": 1, "medium": 2, "high": 3}
    for record in records:
        suggestions = tag_book.explain_tag_book_suggestions(record, loaded)
        for suggestion in suggestions:
            canonical = str(suggestion.get("canonical", "")).strip()
            kind = str(suggestion.get("kind", "")).strip()
            if not canonical:
                continue
            if kind == "known_canonical":
                known_matches.add(canonical)
                continue
            if kind not in {"new_candidate", "weak_candidate", "rejected_candidate"}:
                continue
            quality = str(suggestion.get("quality", "")).strip()
            if quality not in quality_rank:
                quality = "weak" if kind == "weak_candidate" else (
                    "rejected" if kind == "rejected_candidate" else "medium"
                )
            previous = candidate_qualities.get(canonical)
            if previous is None or quality_rank[quality] > quality_rank[previous]:
                candidate_qualities[canonical] = quality

    quality_counts: CandidateQualityCounts = {
        "high": sum(item == "high" for item in candidate_qualities.values()),
        "medium": sum(item == "medium" for item in candidate_qualities.values()),
        "weak": sum(item == "weak" for item in candidate_qualities.values()),
        "rejected": sum(item == "rejected" for item in candidate_qualities.values()),
    }
    candidate_count = len(candidate_qualities)
    return {
        "availability": "available",
        "state": "populated" if candidate_count else "empty",
        "source": "paper_index",
        "evaluated_paper_count": len(records),
        "candidate_count": candidate_count,
        "known_canonical_match_count": len(known_matches),
        "quality_counts": quality_counts,
    }
