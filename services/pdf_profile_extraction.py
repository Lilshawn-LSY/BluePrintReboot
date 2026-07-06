from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ingest.doi import normalize_doi


FRONT_MATTER_CHARS = 30000
SECTION_HEADINGS = {
    "abstract": "Abstract",
    "article highlights": "Article Highlights",
    "background": "Background",
    "conclusion": "Conclusion",
    "conclusions": "Conclusions",
    "discussion": "Discussion",
    "introduction": "Introduction",
    "keywords": "Keywords",
    "key words": "Keywords",
    "materials and methods": "Materials and Methods",
    "methods": "Methods",
    "references": "References",
    "results": "Results",
    "summary": "Summary",
}
ABSTRACT_STOP_HEADINGS = {
    "article highlights",
    "background",
    "conclusion",
    "conclusions",
    "discussion",
    "introduction",
    "keywords",
    "key words",
    "materials and methods",
    "methods",
    "references",
    "results",
}
KEYWORD_STOP_HEADINGS = {
    "abstract",
    "background",
    "conclusion",
    "conclusions",
    "discussion",
    "introduction",
    "materials and methods",
    "methods",
    "references",
    "results",
}
NOISE_PATTERNS = (
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*page\s+\d+(?:\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"downloaded\s+from", re.IGNORECASE),
    re.compile(r"^\s*https?://", re.IGNORECASE),
    re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
    re.compile(r"^\s*copyright\s+", re.IGNORECASE),
)
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s<>\]\)\"']+", flags=re.IGNORECASE)
SUPERSCRIPT_CHARS = str.maketrans(
    {
        "¹": "",
        "²": "",
        "³": "",
        "⁴": "",
        "⁵": "",
        "⁶": "",
        "⁷": "",
        "⁸": "",
        "⁹": "",
        "⁰": "",
        "*": "",
        "†": "",
        "‡": "",
        "§": "",
    }
)


@dataclass(frozen=True)
class PdfProfileExtraction:
    title: str = ""
    authors: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    article_type: str = "unknown"
    section_headings: list[str] = field(default_factory=list)
    cleaned_text: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "keywords": list(self.keywords),
            "doi": self.doi,
            "article_type": self.article_type,
            "section_headings": list(self.section_headings),
            "cleaned_text": self.cleaned_text,
            "warnings": list(self.warnings),
        }


def clean_pdf_text_for_profile(text: str) -> str:
    source = str(text or "")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    source = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[A-Za-z])", "", source)
    raw_lines = source.splitlines()

    filtered: list[str] = []
    repeated_counts: dict[str, int] = {}
    for raw_line in raw_lines:
        line = _normalize_line(raw_line)
        if not line:
            filtered.append("")
            continue
        normalized = _normalized_line_key(line)
        if _is_noise_line(line):
            continue
        if _repeatable_header_footer(line):
            repeated_counts[normalized] = repeated_counts.get(normalized, 0) + 1
            if repeated_counts[normalized] > 1:
                continue
        filtered.append(line)

    output: list[str] = []
    paragraph: list[str] = []
    seen_section_heading = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(_join_paragraph_lines(paragraph))
            paragraph.clear()

    for line in filtered:
        if not line:
            flush_paragraph()
            if output and output[-1] != "":
                output.append("")
            continue

        inline_heading, inline_text = _split_inline_heading(line)
        if inline_heading:
            flush_paragraph()
            output.append(inline_heading)
            seen_section_heading = True
            if inline_text:
                paragraph.append(inline_text)
            continue

        if _is_review_marker(line):
            flush_paragraph()
            output.append("REVIEW")
            continue

        heading = section_heading_for_line(line)
        if heading:
            flush_paragraph()
            output.append(str(heading))
            seen_section_heading = True
            continue

        if not seen_section_heading:
            flush_paragraph()
            output.append(line)
            continue

        paragraph.append(line)

    flush_paragraph()
    return "\n".join(_collapse_blank_lines(output)).strip() + ("\n" if output else "")


def extract_pdf_profile_from_text(text: str, *, front_matter_chars: int = FRONT_MATTER_CHARS) -> PdfProfileExtraction:
    cleaned = clean_pdf_text_for_profile(text)
    front = cleaned[:front_matter_chars]
    lines = [line.strip() for line in front.splitlines() if line.strip()]
    section_headings = _section_headings(lines)
    title = _extract_title(lines)
    authors = _extract_authors(lines, title)
    abstract = _extract_section_text(lines, "abstract", ABSTRACT_STOP_HEADINGS)
    keywords = _extract_keywords(lines)
    doi = _extract_doi(front)
    article_type = detect_article_type(lines, section_headings, title)

    warnings: list[str] = []
    if not title:
        warnings.append("PDF profile title was not detected.")
    if not abstract:
        warnings.append("PDF profile abstract was not detected.")
    if not keywords:
        warnings.append("PDF profile keywords were not detected.")

    return PdfProfileExtraction(
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords,
        doi=doi,
        article_type=article_type,
        section_headings=section_headings,
        cleaned_text=cleaned,
        warnings=warnings,
    )


def detect_article_type(lines: list[str], section_headings: list[str], title: str = "") -> str:
    heading_keys = {_heading_key(heading) for heading in section_headings}
    searchable = " ".join([title, *lines[:12]]).lower()
    if "review" in heading_keys or re.search(r"\breview\b", searchable):
        return "review"
    if "abstract" in heading_keys and (
        "methods" in heading_keys
        or "materials and methods" in heading_keys
        or "results" in heading_keys
        or "discussion" in heading_keys
    ):
        return "research"
    return "unknown"


def section_heading_for_line(line: str) -> str:
    stripped = str(line or "").strip()
    inline = re.match(r"^(abstract|keywords|key words)\s*[:.\-]\s+.+$", stripped, flags=re.IGNORECASE)
    if inline:
        return SECTION_HEADINGS[_heading_key(inline.group(1))]
    key = _heading_key(stripped)
    if key in SECTION_HEADINGS and len(stripped) <= 80:
        return SECTION_HEADINGS[key]
    numbered = re.sub(r"^\d+(?:\.\d+)*\s+", "", stripped)
    key = _heading_key(numbered)
    if key in SECTION_HEADINGS and len(numbered) <= 80:
        return SECTION_HEADINGS[key]
    return ""


def _split_inline_heading(line: str) -> tuple[str, str]:
    match = re.match(r"^(abstract|keywords|key words)\s*[:.\-]\s+(.+)$", str(line or "").strip(), flags=re.IGNORECASE)
    if not match:
        return "", ""
    return SECTION_HEADINGS[_heading_key(match.group(1))], _clean_profile_text(match.group(2))


def _extract_title(lines: list[str]) -> str:
    front_lines = _lines_before_first_section(lines)
    for line in front_lines:
        if _is_review_marker(line) or _line_has_doi(line) or _looks_like_author_line(line):
            continue
        if len(line) < 8 or len(line) > 220:
            continue
        if sum(char.isalpha() for char in line) < 5:
            continue
        return line
    return ""


def _extract_authors(lines: list[str], title: str) -> str:
    front_lines = _lines_before_first_section(lines)
    if title in front_lines:
        front_lines = front_lines[front_lines.index(title) + 1 :]
    candidates: list[str] = []
    for line in front_lines[:6]:
        if _is_review_marker(line) or _line_has_doi(line) or "@" in line:
            continue
        if _looks_like_affiliation_line(line):
            continue
        if _looks_like_author_line(line):
            candidates.append(_clean_author_line(line))
    return "; ".join(_dedupe(candidates))


def _extract_section_text(lines: list[str], wanted_key: str, stop_headings: set[str]) -> str:
    collecting = False
    parts: list[str] = []
    for line in lines:
        inline = re.match(rf"^{wanted_key}\s*[:.\-]\s+(.+)$", line, flags=re.IGNORECASE)
        if inline:
            collecting = True
            parts.append(inline.group(1).strip())
            continue

        heading = section_heading_for_line(line)
        heading_key = _heading_key(heading)
        if collecting and heading_key in stop_headings:
            break
        if heading_key == wanted_key:
            collecting = True
            continue
        if collecting:
            parts.append(line)
    return _clean_profile_text(" ".join(parts))


def _extract_keywords(lines: list[str]) -> list[str]:
    keyword_text = _extract_section_text(lines, "keywords", KEYWORD_STOP_HEADINGS)
    if not keyword_text:
        keyword_text = _extract_section_text(lines, "key words", KEYWORD_STOP_HEADINGS)
    return _split_keywords(keyword_text)


def _extract_doi(text: str) -> str:
    match = DOI_PATTERN.search(str(text or ""))
    if not match:
        return ""
    return normalize_doi(match.group(0).rstrip(".,;"))


def _section_headings(lines: list[str]) -> list[str]:
    headings: list[str] = []
    for line in lines:
        if _is_review_marker(line):
            heading = "Review"
        else:
            heading = section_heading_for_line(line)
        if heading and heading not in headings:
            headings.append(heading)
    return headings


def _lines_before_first_section(lines: list[str]) -> list[str]:
    collected: list[str] = []
    for line in lines:
        heading = section_heading_for_line(line)
        if heading and _heading_key(heading) in {"abstract", "keywords", "key words", "introduction"}:
            break
        collected.append(line)
    return collected


def _split_keywords(text: str) -> list[str]:
    if not text:
        return []
    text = re.sub(r"\bkeywords?\b\s*[:.\-]?", "", text, flags=re.IGNORECASE).strip()
    raw_values = re.split(r"[,;|]", text)
    keywords: list[str] = []
    for raw in raw_values:
        keyword = _clean_profile_text(raw)
        if keyword and 2 <= len(keyword) <= 80:
            keywords.append(keyword)
    return _dedupe(keywords)


def _join_paragraph_lines(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    return _clean_profile_text(text)


def _normalize_line(line: str) -> str:
    text = str(line or "").translate(SUPERSCRIPT_CHARS)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_profile_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalized_line_key(line: str) -> str:
    return re.sub(r"\s+", " ", str(line or "").strip().lower())


def _is_noise_line(line: str) -> bool:
    return any(pattern.search(line) for pattern in NOISE_PATTERNS)


def _repeatable_header_footer(line: str) -> bool:
    lowered = line.lower()
    return len(line) <= 160 and (
        "doi" in lowered
        or "journal" in lowered
        or "vol." in lowered
        or "volume" in lowered
        or bool(DOI_PATTERN.search(line))
    )


def _line_has_doi(line: str) -> bool:
    lowered = line.lower()
    return "doi" in lowered or bool(DOI_PATTERN.search(line))


def _is_review_marker(line: str) -> bool:
    return _heading_key(line) == "review"


def _looks_like_author_line(line: str) -> bool:
    text = str(line or "")
    lowered = text.lower()
    if any(term in lowered for term in ("university", "department", "institute", "laboratory", "correspondence")):
        return False
    if re.search(r"\b(and|&)\b", lowered) and len(text) <= 220:
        return True
    if "," in text and len(text) <= 220 and not text.endswith("."):
        return True
    return False


def _looks_like_affiliation_line(line: str) -> bool:
    lowered = str(line or "").lower()
    return any(term in lowered for term in ("university", "department", "institute", "school of", "faculty of"))


def _clean_author_line(line: str) -> str:
    text = str(line or "")
    text = re.sub(r"(?<=[A-Za-z])\d+(?:,\d+)*", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" and ", "; ")
    text = text.replace(" & ", "; ")
    return text.strip(" ,;")


def _heading_key(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^[#\d.\s]+", "", text)
    text = text.strip(" :.-")
    return re.sub(r"\s+", " ", text)


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    for line in lines:
        if line == "" and (not collapsed or collapsed[-1] == ""):
            continue
        collapsed.append(line)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return collapsed


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            deduped.append(value)
            seen.add(key)
    return deduped
