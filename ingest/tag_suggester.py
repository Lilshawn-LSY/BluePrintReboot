from __future__ import annotations

from typing import Mapping


TAG_RULES = [
    ("review", ("review", "survey")),
    ("method", ("method", "methods", "protocol", "pipeline")),
    ("protocol", ("protocol",)),
    ("plant-biology", ("arabidopsis", "plant biology", "plant-biology", "root apical meristem")),
    ("arabidopsis", ("arabidopsis",)),
    ("root", ("root", "root apical meristem")),
    ("meristem", ("meristem", "root apical meristem")),
    ("ros", ("reactive oxygen species", " ros ", " nbt ", "nitroblue tetrazolium")),
    ("auxin", ("auxin",)),
    ("cytokinin", ("cytokinin",)),
    ("single-cell", ("single-cell", "single cell", "scrna-seq", "single cell rna sequencing")),
    ("scrna-seq", ("scrna-seq", "single-cell rna-seq", "single cell rna sequencing")),
    ("spatial-transcriptomics", ("spatial transcriptomics", "spatial-transcriptomics")),
    ("bioinformatics", ("bioinformatics", "computational biology")),
    ("machine-learning", ("machine learning", "machine-learning")),
    ("ai-biology", ("artificial intelligence", " ai ", "deep learning")),
    ("synthetic-biology", ("synthetic biology", "synthetic-biology")),
    ("metabolic-engineering", ("metabolic engineering", "metabolic-engineering")),
    ("protein-design", ("protein design", "protein-design")),
    ("gene-circuit", ("gene circuit", "gene-circuit", "genetic circuit")),
    ("crispr", ("crispr",)),
    ("statistics", ("statistics", "statistical", "bayesian", "regression")),
]


def suggest_tags_for_record(record: Mapping[str, str], extra_text: str = "") -> list[str]:
    existing = _parse_tags(record.get("tags", ""))
    searchable = _searchable_text(record, extra_text)
    suggestions: list[str] = []
    for tag, needles in TAG_RULES:
        if tag in existing or tag in suggestions:
            continue
        if any(needle in searchable for needle in needles):
            suggestions.append(tag)
    return suggestions


def merge_tags(existing_tags: str, accepted_tags: list[str]) -> str:
    merged = _parse_tags(existing_tags)
    for tag in accepted_tags:
        normalized = _normalize_tag(tag)
        if normalized and normalized not in merged:
            merged.append(normalized)
    return ", ".join(merged)


def _searchable_text(record: Mapping[str, str], extra_text: str) -> str:
    fields = ["title", "authors", "journal", "filename", "doi", "tags"]
    text = " ".join(str(record.get(field, "")) for field in fields)
    return f" {text} {extra_text} ".lower().replace("_", "-")


def _parse_tags(tags: str) -> list[str]:
    parsed: list[str] = []
    for tag in (tags or "").split(","):
        normalized = _normalize_tag(tag)
        if normalized and normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _normalize_tag(tag: str) -> str:
    return "-".join((tag or "").strip().lower().replace("_", "-").split())
