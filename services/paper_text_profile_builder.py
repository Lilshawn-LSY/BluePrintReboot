from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from core.paper_text_profile import PaperTextProfile, PAPER_TEXT_PROFILE_SCHEMA_VERSION
from services.note_import import parse_external_note_text
from services.pdf_profile_extraction import PdfProfileExtraction, extract_pdf_profile_from_text
from storage.extracted_text_store import load_cached_extracted_text
from storage.index_store import INDEX_CSV, load_index
from storage.note_block_store import list_note_blocks
from storage.note_store import note_path_for
from storage.paper_profile_store import save_profile
from storage.paths import EXTRACTED_TEXT_DIR, NOTE_BLOCKS_DIR, NOTES_DIR, PAPER_PROFILES_DIR


NOTE_BLOCK_SECTION_LABELS = {
    "summary": "Summary",
    "claim": "Key Claims",
    "method": "Methods",
    "evidence": "Evidence / Results",
    "question": "Questions",
    "idea": "Ideas",
    "limitation": "Limitations",
}
PROFILE_NOTE_SECTIONS = (
    "One-line Summary",
    "Summary",
    "Key Claims",
    "Methods",
    "Evidence / Results",
    "Questions",
    "Ideas",
    "Limitations",
)

def build_paper_text_profile(
    record: Mapping[str, Any],
    *,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
) -> PaperTextProfile:
    paper_id = _required_paper_id(record)
    pdf_profile = _pdf_profile_from_cache(paper_id, extracted_text_dir)
    title, title_source, title_confidence = _title_from_sources(record, pdf_profile)
    authors, authors_source, authors_confidence = _authors_from_sources(record, pdf_profile)
    abstract, abstract_source, abstract_confidence = _abstract_from_sources(record, pdf_profile)
    keywords, keywords_source, keywords_confidence = _keywords_from_sources(record, pdf_profile)
    doi, doi_source, doi_confidence = _doi_from_sources(record, pdf_profile)
    article_type = pdf_profile.article_type if pdf_profile else "unknown"
    article_type_source = "pdf_profile" if pdf_profile and pdf_profile.article_type != "unknown" else ""
    section_headings = list(pdf_profile.section_headings) if pdf_profile else []
    note_sections, section_sources = _note_sections_from_sources(
        paper_id,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
    )

    sources: dict[str, str] = {
        "title": title_source,
        "authors": authors_source,
        "abstract": abstract_source,
        "keywords": keywords_source,
        "doi": doi_source,
        "article_type": article_type_source,
        "section_headings": "pdf_profile" if section_headings else "",
        "note_sections": ", ".join(sorted(set(section_sources.values()))) if section_sources else "",
    }
    sources.update({f"note_sections.{section}": source for section, source in section_sources.items()})

    confidence = {
        "title": title_confidence,
        "authors": authors_confidence,
        "abstract": abstract_confidence,
        "keywords": keywords_confidence,
        "doi": doi_confidence,
        "article_type": "medium" if article_type_source else "none",
        "section_headings": "medium" if section_headings else "none",
        "note_sections": _note_section_confidence(section_sources),
    }

    return PaperTextProfile(
        schema_version=PAPER_TEXT_PROFILE_SCHEMA_VERSION,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords,
        doi=doi,
        article_type=article_type,
        section_headings=section_headings,
        note_sections=note_sections,
        extraction_warnings=list(pdf_profile.warnings) if pdf_profile else [],
        sources=sources,
        confidence=confidence,
        generated_at=_utc_now_iso(),
    )


def build_and_save_paper_text_profile(
    record: Mapping[str, Any],
    *,
    profile_dir: Path = PAPER_PROFILES_DIR,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
) -> PaperTextProfile:
    profile = build_paper_text_profile(
        record,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        extracted_text_dir=extracted_text_dir,
    )
    save_profile(profile, profile_dir)
    return profile


def build_and_save_paper_text_profile_for_id(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    profile_dir: Path = PAPER_PROFILES_DIR,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
) -> PaperTextProfile | None:
    dataframe = load_index(index_csv)
    if dataframe.empty or "paper_id" not in dataframe.columns:
        return None
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return None
    return build_and_save_paper_text_profile(
        matches.iloc[0].to_dict(),
        profile_dir=profile_dir,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
        extracted_text_dir=extracted_text_dir,
    )


def _required_paper_id(record: Mapping[str, Any]) -> str:
    paper_id = _clean_text(record.get("paper_id"))
    if not paper_id:
        raise ValueError("paper_id is required to build a PaperTextProfile.")
    return paper_id


def _pdf_profile_from_cache(paper_id: str, extracted_text_dir: Path) -> PdfProfileExtraction | None:
    try:
        cached_text = load_cached_extracted_text(paper_id, extracted_text_dir)
    except OSError:
        cached_text = ""
    if not cached_text.strip():
        return None
    return extract_pdf_profile_from_text(cached_text)


def _title_from_sources(record: Mapping[str, Any], pdf_profile: PdfProfileExtraction | None) -> tuple[str, str, str]:
    title = _clean_text(record.get("title"))
    if title:
        return title, "paper_index", "high"
    if pdf_profile and pdf_profile.title:
        return pdf_profile.title, "pdf_profile", "medium"
    filename_stem = Path(_clean_text(record.get("filename"))).stem
    if filename_stem:
        return filename_stem, "filename", "low"
    return "", "", "none"


def _authors_from_sources(record: Mapping[str, Any], pdf_profile: PdfProfileExtraction | None) -> tuple[str, str, str]:
    authors = _clean_text(record.get("authors"))
    if authors:
        return authors, "paper_index", "high"
    if pdf_profile and pdf_profile.authors:
        return pdf_profile.authors, "pdf_profile", "medium"
    return "", "", "none"


def _abstract_from_sources(record: Mapping[str, Any], pdf_profile: PdfProfileExtraction | None) -> tuple[str, str, str]:
    abstract = _clean_text(record.get("abstract"))
    if abstract:
        return abstract, "paper_index", "high"
    if pdf_profile and pdf_profile.abstract:
        return pdf_profile.abstract, "pdf_profile", "medium"
    return "", "", "none"


def _keywords_from_sources(
    record: Mapping[str, Any],
    pdf_profile: PdfProfileExtraction | None,
) -> tuple[list[str], str, str]:
    keywords = _keyword_values(record.get("keywords", ""))
    if keywords:
        return keywords, "paper_index", "high"
    if pdf_profile and pdf_profile.keywords:
        return list(pdf_profile.keywords), "pdf_profile", "medium"
    return [], "", "none"


def _doi_from_sources(record: Mapping[str, Any], pdf_profile: PdfProfileExtraction | None) -> tuple[str, str, str]:
    doi = _clean_text(record.get("doi"))
    if doi:
        return doi, "paper_index", "high"
    if pdf_profile and pdf_profile.doi:
        return pdf_profile.doi, "pdf_profile", "medium"
    return "", "", "none"


def _note_sections_from_sources(
    paper_id: str,
    *,
    notes_dir: Path,
    note_blocks_dir: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    sources: dict[str, set[str]] = defaultdict(set)

    for section, text in _reading_note_sections(paper_id, notes_dir).items():
        _append_section_text(sections, section, text)
        if text.strip():
            sources[section].add("reading_note")

    for section, text in _note_block_sections(paper_id, note_blocks_dir).items():
        _append_section_text(sections, section, text)
        if text.strip():
            sources[section].add("note_blocks")

    joined_sections = {
        section: "\n\n".join(parts)
        for section, parts in sections.items()
        if section != "References" and any(part.strip() for part in parts)
    }
    joined_sources = {
        section: ", ".join(sorted(values))
        for section, values in sources.items()
        if section in joined_sections
    }
    return joined_sections, joined_sources


def _reading_note_sections(paper_id: str, notes_dir: Path) -> dict[str, str]:
    note_path = note_path_for({"paper_id": paper_id}, notes_dir)
    if not note_path.exists():
        return {}
    try:
        note_text = note_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    parsed = parse_external_note_text(note_text, source_filename=note_path.name)
    raw_sections = parsed.get("sections", {})
    if not isinstance(raw_sections, Mapping):
        return {}
    return {
        section: _clean_text(raw_sections.get(section))
        for section in PROFILE_NOTE_SECTIONS
        if _clean_text(raw_sections.get(section))
    }


def _note_block_sections(paper_id: str, note_blocks_dir: Path) -> dict[str, str]:
    try:
        blocks = list_note_blocks(paper_id, note_blocks_dir)
    except (OSError, ValueError):
        return {}

    grouped: dict[str, list[str]] = defaultdict(list)
    for block in blocks:
        section = NOTE_BLOCK_SECTION_LABELS.get(str(block.get("block_type", "")))
        if not section:
            continue
        text = _block_profile_text(block)
        if text:
            grouped[section].append(text)
    return {section: "\n\n".join(parts) for section, parts in grouped.items()}


def _block_profile_text(block: Mapping[str, Any]) -> str:
    parts = [
        _clean_text(block.get("title")),
        _clean_text(block.get("quote")),
        _clean_text(block.get("text")),
    ]
    return "\n".join(part for part in parts if part)


def _append_section_text(sections: dict[str, list[str]], section: str, text: str) -> None:
    cleaned = _clean_text(text)
    if not section or not cleaned:
        return
    existing = "\n\n".join(sections[section])
    if cleaned not in existing:
        sections[section].append(cleaned)


def _note_section_confidence(section_sources: Mapping[str, str]) -> str:
    source_values = " ".join(section_sources.values())
    if "note_blocks" in source_values:
        return "high"
    if "reading_note" in source_values:
        return "medium"
    return "none"


def _keyword_values(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = re.split(r"[,;]", value)
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = []
    keywords: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        keyword = _clean_text(raw)
        key = keyword.casefold()
        if keyword and key not in seen:
            keywords.append(keyword)
            seen.add(key)
    return keywords


def _heading_token(line: str) -> str:
    text = re.sub(r"^[#\d\.\s]+", "", line or "").strip().rstrip(":").lower()
    text = re.split(r"[:.\-]", text, maxsplit=1)[0]
    return re.sub(r"\s+", " ", text).strip()


def _inline_heading_text(line: str, heading: str) -> str:
    match = re.match(rf"^\s*{re.escape(heading)}\s*[:.\-]\s*(.+)$", line, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ""


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
