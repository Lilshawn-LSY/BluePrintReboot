from __future__ import annotations

import re


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
DOI_SEARCH_PATTERN = re.compile(
    r"(?:doi(?:\s*:\s*|\s+)|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/[^\s\"<>]+",
    re.IGNORECASE,
)


def normalize_doi(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""

    value = re.sub(r"^doi(?:\s*:\s*|\s+)", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE).strip()
    value = value.strip(" \t\r\n.>,)]}")
    return value.lower()


def is_probable_doi(value: str) -> bool:
    return bool(DOI_PATTERN.match(normalize_doi(value)))


def extract_doi_from_text(text: str) -> str:
    for match in DOI_SEARCH_PATTERN.finditer(text or ""):
        doi = normalize_doi(match.group(0))
        if is_probable_doi(doi):
            return doi
    return ""
