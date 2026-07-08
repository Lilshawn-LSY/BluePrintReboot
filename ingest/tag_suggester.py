from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.paper_text_profile import PaperTextProfile, coerce_paper_text_profile
from services.tag_book import (
    explain_tag_book_suggestions,
    load_tag_book,
    normalize_tag as normalize_tag_value,
    tag_book_to_registry,
    tag_book_to_rulebook,
)
from storage.atomic_json import read_json_file


DEFAULT_RULE_PATH = Path(__file__).resolve().parents[1] / "config" / "tag_rules.json"
DEFAULT_CANONICAL_TAG_PATH = Path(__file__).resolve().parents[1] / "config" / "canonical_tags.json"

SOURCE_WEIGHTS = {
    "keywords": 6,
    "pdf_keywords": 6,
    "title": 5,
    "openalex_topics": 5,
    "openalex_keywords": 5,
    "abstract": 4,
    "pdf_abstract": 4,
    "markdown_text": 3,
    "pdf_section_headings": 3,
    "note_methods": 3,
    "note_evidence": 3,
    "note_summary": 2,
    "note_claims": 2,
    "note_questions": 1,
    "note_ideas": 1,
    "note_limitations": 1,
    "crossref_subjects": 3,
    "journal": 2,
    "filename": 1,
}

SOURCE_FIELDS = tuple(SOURCE_WEIGHTS.keys())

FORM_SUGGESTION_FIELDS = ("title", "abstract", "keywords", "journal", "filename", "tags")
CROSSREF_PREVIEW_SUGGESTION_FIELDS = ("title", "abstract", "keywords", "journal", "crossref_subjects")
PROFILE_NOTE_SECTION_FIELDS = {
    "One-line Summary": "note_summary",
    "Summary": "note_summary",
    "Key Claims": "note_claims",
    "Methods": "note_methods",
    "Method": "note_methods",
    "Evidence / Results": "note_evidence",
    "Evidence": "note_evidence",
    "Questions": "note_questions",
    "Ideas": "note_ideas",
    "Limitations": "note_limitations",
}


def load_tag_rules(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    rule_path = Path(path) if path is not None else DEFAULT_RULE_PATH
    if path is None or _same_path(rule_path, DEFAULT_RULE_PATH):
        return tag_book_to_rulebook(load_tag_book())

    raw_rules = read_json_file(rule_path, store_name="Tag rule file")

    rules: dict[str, dict[str, Any]] = {}
    for raw_tag, raw_rule in raw_rules.items():
        tag = normalize_tag(raw_tag)
        if not tag or not isinstance(raw_rule, dict):
            continue
        aliases = raw_rule.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        rules[tag] = {
            "category": str(raw_rule.get("category", "")).strip(),
            "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
            "weight": int(raw_rule.get("weight", 1) or 1),
        }
    return rules


def load_canonical_tags(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    registry_path = Path(path) if path is not None else DEFAULT_CANONICAL_TAG_PATH
    if path is None or _same_path(registry_path, DEFAULT_CANONICAL_TAG_PATH):
        return tag_book_to_registry(load_tag_book())

    raw_registry = read_json_file(registry_path, store_name="Canonical tag registry")

    if not isinstance(raw_registry, dict):
        raise ValueError("Canonical tag registry must be a JSON object.")

    registry: dict[str, dict[str, Any]] = {}
    for raw_tag, raw_entry in raw_registry.items():
        tag = normalize_tag(raw_tag)
        if not tag or not isinstance(raw_entry, dict):
            continue
        aliases = raw_entry.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        registry[tag] = {
            **raw_entry,
            "label": str(raw_entry.get("label", tag)).strip() or tag,
            "category": str(raw_entry.get("category", "")).strip(),
            "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
            "status": str(raw_entry.get("status", "active")).strip() or "active",
        }
    return registry


def build_tag_alias_index(registry: dict) -> dict[str, dict]:
    owners_by_alias: dict[str, set[str]] = {}
    for raw_tag, raw_entry in registry.items():
        tag = normalize_tag(raw_tag)
        if not tag or not isinstance(raw_entry, dict):
            continue
        aliases = raw_entry.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        alias_values = [tag, raw_entry.get("label", ""), *aliases]
        for raw_alias in alias_values:
            alias = normalize_tag(raw_alias)
            if alias:
                owners_by_alias.setdefault(alias, set()).add(tag)

    collisions = {
        alias: sorted(owners)
        for alias, owners in owners_by_alias.items()
        if len(owners) > 1
    }
    alias_to_canonical = {
        alias: next(iter(owners))
        for alias, owners in owners_by_alias.items()
        if len(owners) == 1
    }
    return {
        "alias_to_canonical": alias_to_canonical,
        "collisions": collisions,
    }


def resolve_canonical_tag(raw_tag: str, registry: dict) -> str | None:
    tag = normalize_tag(raw_tag)
    if not tag:
        return None
    if tag in registry:
        return tag
    return build_tag_alias_index(registry)["alias_to_canonical"].get(tag)


def canonicalize_tags(raw_tags: str | list[str] | tuple[str, ...], registry: dict) -> list[str]:
    values = re.split(r"[,;]", raw_tags) if isinstance(raw_tags, str) else raw_tags
    canonical_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in values:
        normalized = normalize_tag(raw_tag)
        tag = resolve_canonical_tag(raw_tag, registry) or normalized
        if tag and tag not in seen:
            canonical_tags.append(tag)
            seen.add(tag)
    return canonical_tags


def audit_canonical_tags(records: list[dict], registry: dict) -> dict:
    registry_tags = {normalize_tag(tag) for tag in registry if normalize_tag(tag)}
    seen_canonical_tags: set[str] = set()
    unknown_tags: set[str] = set()
    duplicate_normalized_tags: set[str] = set()

    for record in records:
        identities_in_record: set[str] = set()
        for raw_tag in _raw_tag_values(record.get("tags", "")):
            normalized = normalize_tag(raw_tag)
            if not normalized:
                continue
            canonical = resolve_canonical_tag(raw_tag, registry)
            identity = canonical or normalized
            if identity in identities_in_record:
                duplicate_normalized_tags.add(identity)
            identities_in_record.add(identity)
            if canonical:
                seen_canonical_tags.add(canonical)
            else:
                unknown_tags.add(normalized)

    alias_index = build_tag_alias_index(registry)
    return {
        "known_tags": sorted(seen_canonical_tags),
        "unknown_tags": sorted(unknown_tags),
        "unused_canonical_tags": sorted(registry_tags - seen_canonical_tags),
        "duplicate_normalized_tags": sorted(duplicate_normalized_tags),
        "alias_collisions": alias_index["collisions"],
    }


def preview_tag_merge(
    records: list[dict],
    source_tag: str,
    target_tag: str,
    registry: dict,
    exact_source: bool = False,
) -> dict:
    merged_records = apply_tag_merge_to_records(
        records,
        source_tag,
        target_tag,
        registry,
        exact_source=exact_source,
    )
    changes = []
    for index, (before, after) in enumerate(zip(records, merged_records)):
        if str(before.get("tags", "")) != str(after.get("tags", "")):
            changes.append(
                {
                    "record_index": index,
                    "paper_id": str(before.get("paper_id", "")),
                    "before": str(before.get("tags", "")),
                    "after": str(after.get("tags", "")),
                }
            )
    return {
        "source_tag": resolve_canonical_tag(source_tag, registry) or normalize_tag(source_tag),
        "target_tag": _require_canonical_target(target_tag, registry),
        "affected_records": len(changes),
        "changes": changes,
        "records": merged_records,
    }


def apply_tag_merge_to_records(
    records: list[dict],
    source_tag: str,
    target_tag: str,
    registry: dict,
    exact_source: bool = False,
) -> list[dict]:
    source_normalized = normalize_tag(source_tag)
    source_canonical = resolve_canonical_tag(source_tag, registry)
    target_canonical = _require_canonical_target(target_tag, registry)
    if not source_normalized:
        raise ValueError("Source tag must not be empty.")

    merged_records: list[dict] = []
    for record in records:
        raw_tags = _raw_tag_values(record.get("tags", ""))
        has_source = any(
            _matches_merge_source(
                raw_tag,
                source_normalized,
                source_canonical,
                registry,
                exact_source,
            )
            for raw_tag in raw_tags
        )
        if not has_source:
            merged_records.append(dict(record))
            continue

        merged_tags: list[str] = []
        seen_identities: set[str] = set()
        for raw_tag in raw_tags:
            normalized = normalize_tag(raw_tag)
            resolved = resolve_canonical_tag(raw_tag, registry)
            matches_source = _matches_merge_source(
                raw_tag,
                source_normalized,
                source_canonical,
                registry,
                exact_source,
            )
            output_tag = target_canonical if matches_source else str(raw_tag).strip()
            output_identity = resolve_canonical_tag(output_tag, registry) or normalize_tag(output_tag)
            if output_identity and output_identity not in seen_identities:
                merged_tags.append(output_tag)
                seen_identities.add(output_identity)

        merged_record = dict(record)
        merged_record["tags"] = ", ".join(merged_tags)
        merged_records.append(merged_record)
    return merged_records


def build_tag_suggestion_record(
    saved_record: dict,
    form_values: dict | None = None,
    crossref_preview: dict | None = None,
    paper_text_profile: PaperTextProfile | dict | None = None,
) -> dict:
    suggestion_record = dict(saved_record or {})
    if paper_text_profile is not None:
        suggestion_record = apply_paper_text_profile_to_record(suggestion_record, paper_text_profile)
    if form_values:
        for field in FORM_SUGGESTION_FIELDS:
            value = form_values.get(field)
            if _has_value(value):
                suggestion_record[field] = value
    if crossref_preview:
        for field in CROSSREF_PREVIEW_SUGGESTION_FIELDS:
            value = crossref_preview.get(field)
            if _has_value(value):
                suggestion_record[field] = value
    return suggestion_record


def apply_paper_text_profile_to_record(
    record: dict,
    paper_text_profile: PaperTextProfile | dict,
) -> dict:
    profile = coerce_paper_text_profile(paper_text_profile)
    suggestion_record = dict(record or {})
    if _has_value(profile.title):
        suggestion_record["title"] = profile.title
    if _has_value(profile.abstract):
        if profile.sources.get("abstract") == "pdf_profile":
            suggestion_record["pdf_abstract"] = profile.abstract
        else:
            suggestion_record["abstract"] = profile.abstract
    if _has_value(profile.keywords):
        if profile.sources.get("keywords") == "pdf_profile":
            suggestion_record["pdf_keywords"] = profile.keywords
        else:
            suggestion_record["keywords"] = profile.keywords
    if _has_value(profile.section_headings):
        suggestion_record["pdf_section_headings"] = profile.section_headings
    if _has_value(profile.article_type):
        suggestion_record["article_type"] = profile.article_type
    suggestion_record["paper_text_profile_schema_version"] = profile.schema_version
    for section, text in profile.note_sections.items():
        field = PROFILE_NOTE_SECTION_FIELDS.get(str(section))
        if not field or not _has_value(text):
            continue
        existing = _record_field_text(suggestion_record.get(field, ""))
        suggestion_record[field] = _join_text_values(existing, str(text))
    return suggestion_record


def validate_tag_rules(rules: dict) -> list[str]:
    warnings: list[str] = []
    aliases_by_normalized_value: dict[str, str] = {}

    for tag, rule in rules.items():
        normalized_tag = normalize_tag(str(tag))
        if tag != normalized_tag:
            warnings.append(f"Tag '{tag}' is not normalized kebab-case.")
        if not isinstance(rule, dict):
            warnings.append(f"Tag '{tag}' rule must be an object.")
            continue

        if "category" not in rule or not str(rule.get("category", "")).strip():
            warnings.append(f"Tag '{tag}' is missing category.")
        if "aliases" not in rule:
            warnings.append(f"Tag '{tag}' is missing aliases.")
            aliases = []
        else:
            aliases = rule.get("aliases")
            if not isinstance(aliases, list) or not aliases:
                warnings.append(f"Tag '{tag}' aliases must be a non-empty list.")
                aliases = []

        if "weight" not in rule:
            warnings.append(f"Tag '{tag}' is missing weight.")
        else:
            try:
                float(rule.get("weight"))
            except (TypeError, ValueError):
                warnings.append(f"Tag '{tag}' weight must be numeric.")

        for alias in aliases:
            alias_text = str(alias).strip()
            if not alias_text:
                warnings.append(f"Tag '{tag}' has an empty alias.")
                continue
            normalized_alias = normalize_tag(alias_text)
            owner = aliases_by_normalized_value.get(normalized_alias)
            if owner and owner != tag:
                warnings.append(f"Alias '{alias_text}' is used by both '{owner}' and '{tag}'.")
            else:
                aliases_by_normalized_value[normalized_alias] = tag

    return warnings


def audit_library_tags(records: list[dict], rules: dict) -> dict:
    rule_tags = {normalize_tag(str(tag)) for tag in rules.keys() if normalize_tag(str(tag))}
    seen_tags: set[str] = set()
    known_tags: set[str] = set()
    unknown_tags: set[str] = set()
    duplicate_normalized_tags: set[str] = set()

    for record in records:
        raw_tags = str(record.get("tags", ""))
        normalized_in_record: set[str] = set()
        for raw in re.split(r"[,;]", raw_tags):
            tag = normalize_tag(raw)
            if not tag:
                continue
            if tag in normalized_in_record:
                duplicate_normalized_tags.add(tag)
            normalized_in_record.add(tag)
            seen_tags.add(tag)
            if tag in rule_tags:
                known_tags.add(tag)
            else:
                unknown_tags.add(tag)

    return {
        "known_tags": sorted(known_tags),
        "unknown_tags": sorted(unknown_tags),
        "unused_rulebook_tags": sorted(rule_tags - seen_tags),
        "duplicate_normalized_tags": sorted(duplicate_normalized_tags),
    }


def normalize_tag(value: str) -> str:
    return normalize_tag_value(value)


def parse_tags(value: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[,;]", value or ""):
        tag = normalize_tag(raw)
        if tag and tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    return normalized


def merge_tags(existing_tags: str, suggested_tags: list[str]) -> str:
    merged = parse_tags(existing_tags)
    seen = set(merged)
    for tag in suggested_tags:
        normalized = normalize_tag(tag)
        if normalized and normalized not in seen:
            merged.append(normalized)
            seen.add(normalized)
    return ", ".join(merged)


def suggest_tags(
    record: dict[str, Any],
    rules: dict | None = None,
    paper_text_profile: PaperTextProfile | dict | None = None,
) -> list[str]:
    return [
        explanation["tag"]
        for explanation in explain_tag_suggestions(record, rules, paper_text_profile=paper_text_profile)
        if explanation.get("kind", "known_canonical") == "known_canonical"
    ]


def explain_tag_suggestions(
    record: dict[str, Any],
    rules: dict | None = None,
    paper_text_profile: PaperTextProfile | dict | None = None,
) -> list[dict]:
    suggestion_record = (
        apply_paper_text_profile_to_record(record, paper_text_profile)
        if paper_text_profile is not None
        else dict(record or {})
    )
    if rules is None:
        return explain_tag_book_suggestions(suggestion_record)

    active_rules = rules if rules is not None else load_tag_rules()
    existing = set(parse_tags(str(suggestion_record.get("tags", ""))))
    suggestions: dict[str, dict[str, Any]] = {}

    for tag, rule in active_rules.items():
        normalized_tag = normalize_tag(tag)
        if not normalized_tag or normalized_tag in existing:
            continue

        matched_fields: set[str] = set()
        score = 0
        rule_weight = int(rule.get("weight", 1) or 1)
        aliases = [str(alias) for alias in rule.get("aliases", [])]

        for field in SOURCE_FIELDS:
            text = _record_field_text(suggestion_record.get(field, ""))
            if text and _matches_any_alias(text, aliases):
                matched_fields.add(field)
                score += rule_weight * SOURCE_WEIGHTS[field]

        if matched_fields:
            suggestions[normalized_tag] = {
                "tag": normalized_tag,
                "category": str(rule.get("category", "")).strip(),
                "score": score,
                "matched_fields": sorted(matched_fields, key=_source_sort_key),
            }

    return sorted(
        suggestions.values(),
        key=lambda item: (-int(item["score"]), item["tag"]),
    )


def _record_field_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values())
    return str(value or "")


def _join_text_values(left: str, right: str) -> str:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text:
        return right_text
    if not right_text or right_text in left_text:
        return left_text
    return f"{left_text}\n\n{right_text}"


def _raw_tag_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [raw.strip() for raw in re.split(r"[,;]", str(value or "")) if raw.strip()]


def _require_canonical_target(target_tag: str, registry: dict) -> str:
    target = resolve_canonical_tag(target_tag, registry)
    if target:
        return target
    normalized = normalize_tag(target_tag)
    collisions = build_tag_alias_index(registry)["collisions"]
    if normalized in collisions:
        owners = ", ".join(collisions[normalized])
        raise ValueError(f"Target tag '{target_tag}' is ambiguous: {owners}.")
    raise ValueError(f"Target tag '{target_tag}' is not in the canonical tag registry.")


def _matches_merge_source(
    raw_tag: str,
    source_normalized: str,
    source_canonical: str | None,
    registry: dict,
    exact_source: bool,
) -> bool:
    if exact_source or not source_canonical:
        return normalize_tag(raw_tag) == source_normalized
    return resolve_canonical_tag(raw_tag, registry) == source_canonical


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _matches_any_alias(text: str, aliases: list[str]) -> bool:
    haystack = text.lower()
    for alias in aliases:
        needle = alias.strip().lower()
        if not needle:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return True
    return False


def _source_sort_key(field: str) -> tuple[int, str]:
    return (-SOURCE_WEIGHTS.get(field, 0), field)


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right
