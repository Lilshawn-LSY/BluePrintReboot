from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_RULE_PATH = Path(__file__).resolve().parents[1] / "config" / "tag_rules.json"

SOURCE_WEIGHTS = {
    "keywords": 6,
    "openalex_topics": 5,
    "openalex_keywords": 5,
    "title": 4,
    "abstract": 4,
    "markdown_text": 3,
    "crossref_subjects": 3,
    "journal": 2,
    "filename": 1,
}

SOURCE_FIELDS = tuple(SOURCE_WEIGHTS.keys())

FORM_SUGGESTION_FIELDS = ("title", "abstract", "keywords", "journal", "filename", "tags")
CROSSREF_PREVIEW_SUGGESTION_FIELDS = ("title", "abstract", "keywords", "journal", "crossref_subjects")


def load_tag_rules(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    rule_path = Path(path) if path is not None else DEFAULT_RULE_PATH
    with rule_path.open("r", encoding="utf-8") as file:
        raw_rules = json.load(file)

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


def build_tag_suggestion_record(
    saved_record: dict,
    form_values: dict | None = None,
    crossref_preview: dict | None = None,
) -> dict:
    suggestion_record = dict(saved_record or {})
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
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


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


def suggest_tags(record: dict[str, str], rules: dict | None = None) -> list[str]:
    return [explanation["tag"] for explanation in explain_tag_suggestions(record, rules)]


def explain_tag_suggestions(record: dict[str, str], rules: dict | None = None) -> list[dict]:
    active_rules = rules if rules is not None else load_tag_rules()
    existing = set(parse_tags(str(record.get("tags", ""))))
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
            text = _record_field_text(record.get(field, ""))
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
