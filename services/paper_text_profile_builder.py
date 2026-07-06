from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from core.paper_text_profile import PaperTextProfile, PAPER_TEXT_PROFILE_SCHEMA_VERSION
from services.note_import import parse_external_note_text
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
ABSTRACT_STOP_HEADINGS = {
    "keywords",
    "keyword",
    "introduction",
    "background",
    "materials and methods",
    "methods",
    "results",
    "references",
}


def build_paper_text_profile(
    record: Mapping[str, Any],
    *,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
) -> PaperTextProfile:
    paper_id = _required_paper_id(record)
    title, title_source, title_confidence = _title_from_record(record)
    abstract, abstract_source, abstract_confidence = _abstract_from_sources(
        paper_id,
        record,
        extracted_text_dir,
    )
    keywords = _keyword_values(record.get("keywords", ""))
    note_sections, section_sources = _note_sections_from_sources(
        paper_id,
        notes_dir=notes_dir,
        note_blocks_dir=note_blocks_dir,
    )

    sources: dict[str, str] = {
        "title": title_source,
        "abstract": abstract_source,
        "keywords": "paper_index" if keywords else "",
        "note_sections": ", ".join(sorted(set(section_sources.values()))) if section_sources else "",
    }
    sources.update({f"note_sections.{section}": source for section, source in section_sources.items()})

    confidence = {
        "title": title_confidence,
        "abstract": abstract_confidence,
        "keywords": "high" if keywords else "none",
        "note_sections": _note_section_confidence(section_sources),
    }

    return PaperTextProfile(
        schema_version=PAPER_TEXT_PROFILE_SCHEMA_VERSION,
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        keywords=keywords,
        note_sections=note_sections,
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


def _title_from_record(record: Mapping[str, Any]) -> tuple[str, str, str]:
    title = _clean_text(record.get("title"))
    if title:
        return title, "paper_index", "high"
    filename_stem = Path(_clean_text(record.get("filename"))).stem
    if filename_stem:
        return filename_stem, "filename", "low"
    return "", "", "none"


def _abstract_from_sources(
    paper_id: str,
    record: Mapping[str, Any],
    extracted_text_dir: Path,
) -> tuple[str, str, str]:
    abstract = _clean_text(record.get("abstract"))
    if abstract:
        return abstract, "paper_index", "high"

    try:
        cached_text = load_cached_extracted_text(paper_id, extracted_text_dir)
    except OSError:
        cached_text = ""
    fallback = _abstract_from_cached_text(cached_text)
    if fallback:
        return fallback, "extracted_text_cache", "low"
    return "", "", "none"


def _abstract_from_cached_text(text: str) -> str:
    lines = str(text or "").splitlines()
    abstract_lines: list[str] = []
    in_abstract = False
    for raw_line in lines[:250]:
        line = raw_line.strip()
        if not line and not in_abstract:
            continue
        heading = _heading_token(line)
        if in_abstract and heading in ABSTRACT_STOP_HEADINGS:
            break
        if not in_abstract:
            if heading == "abstract":
                in_abstract = True
                inline = _inline_heading_text(line, "abstract")
                if inline:
                    abstract_lines.append(inline)
            continue
        if line:
            abstract_lines.append(line)
        elif abstract_lines:
            break
        if len(" ".join(abstract_lines)) >= 2500:
            break

    abstract = " ".join(" ".join(abstract_lines).split())
    return abstract if len(abstract) >= 40 else ""


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
