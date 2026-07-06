from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


PAPER_TEXT_PROFILE_SCHEMA_VERSION = "1.0.15"
PROFILE_CONFIDENCE_FIELDS = (
    "title",
    "authors",
    "abstract",
    "keywords",
    "doi",
    "article_type",
    "section_headings",
    "note_sections",
)
CONFIDENCE_VALUES = {"none", "low", "medium", "high"}


@dataclass
class PaperTextProfile:
    paper_id: str
    schema_version: str = PAPER_TEXT_PROFILE_SCHEMA_VERSION
    title: str = ""
    authors: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    article_type: str = "unknown"
    section_headings: list[str] = field(default_factory=list)
    note_sections: dict[str, str] = field(default_factory=dict)
    extraction_warnings: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, str] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return paper_text_profile_to_dict(self)


def paper_text_profile_from_dict(data: Mapping[str, Any]) -> PaperTextProfile:
    if not isinstance(data, Mapping):
        raise ValueError("PaperTextProfile payload must be an object.")
    paper_id = _string_value(data.get("paper_id"))
    if not paper_id:
        raise ValueError("PaperTextProfile.paper_id must not be empty.")
    return PaperTextProfile(
        schema_version=_string_value(data.get("schema_version")) or PAPER_TEXT_PROFILE_SCHEMA_VERSION,
        paper_id=paper_id,
        title=_string_value(data.get("title")),
        authors=_string_value(data.get("authors")),
        abstract=_string_value(data.get("abstract")),
        keywords=_normalize_keywords(data.get("keywords")),
        doi=_string_value(data.get("doi")),
        article_type=_normalize_article_type(data.get("article_type")),
        section_headings=_normalize_string_list(data.get("section_headings")),
        note_sections=_normalize_text_mapping(data.get("note_sections")),
        extraction_warnings=_normalize_string_list(data.get("extraction_warnings")),
        sources=_normalize_text_mapping(data.get("sources")),
        confidence=_normalize_confidence(data.get("confidence")),
        generated_at=_string_value(data.get("generated_at")),
    )


def paper_text_profile_to_dict(profile: PaperTextProfile | Mapping[str, Any]) -> dict[str, Any]:
    normalized = profile if isinstance(profile, PaperTextProfile) else paper_text_profile_from_dict(profile)
    confidence = _normalize_confidence(normalized.confidence)
    for field_name in PROFILE_CONFIDENCE_FIELDS:
        confidence.setdefault(field_name, "none")
    return {
        "schema_version": _string_value(normalized.schema_version) or PAPER_TEXT_PROFILE_SCHEMA_VERSION,
        "paper_id": _string_value(normalized.paper_id),
        "title": _string_value(normalized.title),
        "authors": _string_value(normalized.authors),
        "abstract": _string_value(normalized.abstract),
        "keywords": _normalize_keywords(normalized.keywords),
        "doi": _string_value(normalized.doi),
        "article_type": _normalize_article_type(normalized.article_type),
        "section_headings": _normalize_string_list(normalized.section_headings),
        "note_sections": _normalize_text_mapping(normalized.note_sections),
        "extraction_warnings": _normalize_string_list(normalized.extraction_warnings),
        "sources": _normalize_text_mapping(normalized.sources),
        "confidence": confidence,
        "generated_at": _string_value(normalized.generated_at),
    }


def coerce_paper_text_profile(profile: PaperTextProfile | Mapping[str, Any]) -> PaperTextProfile:
    if isinstance(profile, PaperTextProfile):
        return paper_text_profile_from_dict(profile.to_dict())
    return paper_text_profile_from_dict(profile)


def _normalize_keywords(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = re.split(r"[,;]", value)
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = []

    keywords: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        keyword = " ".join(str(raw or "").split())
        key = keyword.casefold()
        if keyword and key not in seen:
            keywords.append(keyword)
            seen.add(key)
    return keywords


def _normalize_text_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _string_value(raw_key)
        text = _string_value(raw_value)
        if key and text:
            normalized[key] = text
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = re.split(r"[,;]", value)
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        item = " ".join(str(raw or "").split())
        key = item.casefold()
        if item and key not in seen:
            normalized.append(item)
            seen.add(key)
    return normalized


def _normalize_article_type(value: Any) -> str:
    article_type = _string_value(value).lower()
    return article_type if article_type in {"review", "research", "unknown"} else "unknown"


def _normalize_confidence(value: Any) -> dict[str, str]:
    confidence = _normalize_text_mapping(value)
    for field_name, raw_confidence in list(confidence.items()):
        normalized = raw_confidence.strip().lower()
        confidence[field_name] = normalized if normalized in CONFIDENCE_VALUES else "low"
    return confidence


def _string_value(value: Any) -> str:
    return str(value or "").strip()
