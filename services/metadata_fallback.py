from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import requests

from config.contact import build_blueprint_user_agent
from core.paper_text_profile import PaperTextProfile, coerce_paper_text_profile
from ingest.document_text import extract_pdf_text_with_markitdown, extract_pdf_text_with_pypdf
from ingest.doi import normalize_doi
from services.pdf_profile_extraction import extract_pdf_profile_from_text
from storage.extracted_text_store import load_cached_extracted_text
from storage.index_store import load_index, save_index
from storage.paths import EXTRACTED_TEXT_DIR, INDEX_CSV


ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_ARXIV_TIMEOUT = 8.0
APPLY_FIELDS = ("title", "authors", "year", "abstract", "keywords", "doi")
MODERN_ARXIV_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:arxiv\s*[:_\-\s]\s*)?(\d{4}\.\d{4,5})(?:v\d+)?(?![A-Za-z0-9])"
)
OLD_STYLE_ARXIV_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:arxiv\s*[:_\-\s]\s*)?([a-z][a-z0-9.-]*/\d{7})(?:v\d+)?(?![A-Za-z0-9])"
)
BOILERPLATE_TITLE_LINES = {
    "abstract",
    "keywords",
    "introduction",
    "references",
    "contents",
}
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_metadata_candidate(
    *,
    source: str = "none",
    confidence: str = "none",
    diagnostics: list[str] | None = None,
    arxiv_id: str = "",
) -> dict[str, Any]:
    return {
        "title": "",
        "authors": "",
        "year": "",
        "abstract": "",
        "doi": "",
        "arxiv_id": arxiv_id,
        "source": source,
        "confidence": confidence,
        "field_sources": {},
        "diagnostics": diagnostics or [],
    }


def normalize_arxiv_id(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    old_match = OLD_STYLE_ARXIV_PATTERN.search(text)
    if old_match:
        candidate = old_match.group(1).lower()
        return candidate if _old_style_arxiv_id_is_valid(candidate) else ""
    modern_match = MODERN_ARXIV_PATTERN.search(text)
    if modern_match:
        candidate = modern_match.group(1)
        return candidate if _modern_arxiv_id_is_valid(candidate) else ""
    return ""


def extract_arxiv_ids(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (OLD_STYLE_ARXIV_PATTERN, MODERN_ARXIV_PATTERN):
        for match in pattern.finditer(str(text or "")):
            arxiv_id = normalize_arxiv_id(match.group(0))
            if arxiv_id and arxiv_id not in found:
                found.append(arxiv_id)
    return found


def extract_arxiv_id_from_text(text: str) -> str:
    ids = extract_arxiv_ids(text)
    return ids[0] if ids else ""


def lookup_arxiv_metadata(
    arxiv_id: str,
    *,
    timeout: float = DEFAULT_ARXIV_TIMEOUT,
    request_get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_arxiv_id(arxiv_id)
    if not normalized:
        return empty_metadata_candidate(
            diagnostics=["No valid arXiv ID was available for lookup."],
        )

    get = request_get or requests.get
    url = f"{ARXIV_API_URL}?{urlencode({'id_list': normalized})}"
    try:
        response = get(
            url,
            headers={"User-Agent": build_blueprint_user_agent()},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return _arxiv_id_only_candidate(normalized, "arXiv lookup timed out.")
    except requests.exceptions.SSLError:
        return _arxiv_id_only_candidate(
            normalized,
            "arXiv SSL/certificate check failed. Check certifi, proxy, or network inspection.",
        )
    except requests.exceptions.ConnectionError:
        return _arxiv_id_only_candidate(
            normalized,
            "arXiv network connection failed. Local metadata fallback remains available.",
        )
    except requests.exceptions.RequestException as exc:
        return _arxiv_id_only_candidate(normalized, f"arXiv request failed: {exc}")
    except Exception as exc:
        return _arxiv_id_only_candidate(normalized, f"arXiv lookup failed unexpectedly: {exc}")

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code != 200:
        return _arxiv_id_only_candidate(normalized, f"arXiv lookup returned HTTP {status_code}.")

    xml_text = str(getattr(response, "text", "") or "")
    try:
        candidate = parse_arxiv_atom_metadata(xml_text, fallback_arxiv_id=normalized)
    except ET.ParseError:
        return _arxiv_id_only_candidate(normalized, "arXiv returned malformed metadata.")
    if candidate["source"] == "none":
        return _arxiv_id_only_candidate(normalized, "arXiv returned no metadata entry.")
    return candidate


def parse_arxiv_atom_metadata(xml_text: str, *, fallback_arxiv_id: str = "") -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    entry = root.find("atom:entry", ATOM_NAMESPACE)
    if entry is None:
        entry = root.find("entry")
    if entry is None:
        return empty_metadata_candidate(
            arxiv_id=normalize_arxiv_id(fallback_arxiv_id),
            diagnostics=["arXiv returned no metadata entry."],
        )

    arxiv_id = normalize_arxiv_id(_child_text(entry, "id")) or normalize_arxiv_id(fallback_arxiv_id)
    title = _clean_metadata_text(_child_text(entry, "title"))
    abstract = _clean_metadata_text(_child_text(entry, "summary"))
    authors = "; ".join(
        _clean_metadata_text(_child_text(author, "name"))
        for author in _children(entry, "author")
        if _clean_metadata_text(_child_text(author, "name"))
    )
    year = _year_from_date(_child_text(entry, "published")) or _year_from_date(_child_text(entry, "updated"))
    doi = normalize_doi(_child_text_by_suffix(entry, "doi"))
    diagnostics = ["arXiv metadata parsed."]
    missing = [
        label
        for label, value in (("title", title), ("authors", authors), ("year", year))
        if not value
    ]
    if missing:
        diagnostics.append(f"arXiv metadata missing: {', '.join(missing)}.")

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "source": "arxiv_id",
        "confidence": "high" if title and authors and year else "medium",
        "diagnostics": diagnostics,
    }


def build_doi_less_metadata_candidate(
    record: dict[str, str],
    *,
    pdf_text: str | None = None,
    lookup_arxiv: bool = True,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    request_get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    filename = str(record.get("filename") or Path(str(record.get("filepath", ""))).name)
    diagnostics: list[str] = []

    text = pdf_text
    if text is None:
        text, text_diagnostics = _candidate_text_for_record(record, cache_dir=cache_dir)
        diagnostics.extend(text_diagnostics)

    arxiv_id = extract_arxiv_id_from_text(filename)
    arxiv_location = "filename"
    if not arxiv_id:
        arxiv_id = extract_arxiv_id_from_text(text or "")
        arxiv_location = "PDF or extracted text"

    if arxiv_id:
        diagnostics.append(f"arXiv ID found in {arxiv_location}: {arxiv_id}.")
        if lookup_arxiv:
            candidate = lookup_arxiv_metadata(arxiv_id, request_get=request_get)
            candidate["diagnostics"] = diagnostics + list(candidate.get("diagnostics", []))
            if not candidate.get("year"):
                candidate["year"] = _year_from_arxiv_id(arxiv_id)
            if not candidate.get("title"):
                candidate["title"] = _filename_title_guess(filename)
            return candidate
        candidate = _arxiv_id_only_candidate(arxiv_id, "arXiv metadata lookup was not requested.")
        candidate["diagnostics"] = diagnostics + list(candidate.get("diagnostics", []))
        if not candidate.get("title"):
            candidate["title"] = _filename_title_guess(filename)
        return candidate

    pdf_profile_candidate = pdf_profile_metadata_candidate_from_text(text or "")
    if any(str(pdf_profile_candidate.get(field, "") or "").strip() for field in ("title", "authors", "abstract", "keywords", "doi")):
        pdf_profile_candidate["diagnostics"] = diagnostics + list(pdf_profile_candidate.get("diagnostics", []))
        return pdf_profile_candidate

    title_guess = title_guess_from_pdf_text(text or "")
    if title_guess:
        return {
            **empty_metadata_candidate(
                source="pdf_text_guess",
                confidence="low",
                diagnostics=diagnostics + ["Title-like text was guessed from PDF text."],
            ),
            "title": title_guess,
        }

    filename_title = _filename_title_guess(filename)
    if filename_title:
        return {
            **empty_metadata_candidate(
                source="filename_guess",
                confidence="weak",
                diagnostics=diagnostics + ["Filename was used as a weak title fallback."],
            ),
            "title": filename_title,
        }

    return empty_metadata_candidate(diagnostics=diagnostics + ["No DOI-less metadata candidate was found."])


def pdf_profile_metadata_candidate_from_text(text: str) -> dict[str, Any]:
    profile = extract_pdf_profile_from_text(text)
    field_sources: dict[str, str] = {}
    candidate = empty_metadata_candidate(
        source="pdf_profile",
        confidence="medium" if profile.abstract or profile.keywords else "low",
        diagnostics=["PDF profile front matter parsed.", *profile.warnings],
    )
    for field, value in (
        ("title", profile.title),
        ("authors", profile.authors),
        ("abstract", profile.abstract),
        ("keywords", ", ".join(profile.keywords)),
        ("doi", profile.doi),
    ):
        if value:
            candidate[field] = value
            field_sources[field] = "pdf_profile"
    candidate["article_type"] = profile.article_type
    candidate["section_headings"] = profile.section_headings
    candidate["field_sources"] = field_sources
    return candidate


def fill_metadata_gaps_from_pdf_profile(
    record: dict[str, Any],
    candidate: dict[str, Any] | None,
    profile: PaperTextProfile | dict | None,
) -> dict[str, Any]:
    filled = dict(candidate or {})
    if not profile:
        return filled

    pdf_profile = coerce_paper_text_profile(profile)
    field_sources = dict(filled.get("field_sources", {}) if isinstance(filled.get("field_sources"), dict) else {})
    candidate_source = str(filled.get("source", "") or "candidate")
    for field in ("title", "authors", "abstract", "keywords", "doi"):
        if str(filled.get(field, "") or "").strip():
            field_sources.setdefault(field, candidate_source)

    fallback_values = {
        "title": pdf_profile.title,
        "authors": pdf_profile.authors,
        "abstract": pdf_profile.abstract,
        "keywords": ", ".join(pdf_profile.keywords),
        "doi": pdf_profile.doi,
    }
    changed_fields: list[str] = []
    for field, value in fallback_values.items():
        if not str(value or "").strip():
            continue
        if str(filled.get(field, "") or "").strip():
            continue
        if str(record.get(field, "") or "").strip():
            continue
        filled[field] = value
        field_sources[field] = "pdf_profile"
        changed_fields.append(field)

    if pdf_profile.article_type and pdf_profile.article_type != "unknown":
        filled.setdefault("article_type", pdf_profile.article_type)
    if pdf_profile.section_headings:
        filled.setdefault("section_headings", list(pdf_profile.section_headings))
    filled["field_sources"] = field_sources
    if changed_fields:
        diagnostics = list(filled.get("diagnostics", []))
        diagnostics.append("Filled blank metadata fields from PDF profile: " + ", ".join(changed_fields) + ".")
        filled["diagnostics"] = diagnostics
        source = str(filled.get("source", "") or "")
        if source and source != "pdf_profile":
            filled["source"] = f"{source}+pdf_profile"
        else:
            filled["source"] = "pdf_profile"
    return filled


def title_guess_from_pdf_text(text: str) -> str:
    for line in _clean_lines(text):
        normalized = line.lower().strip(":")
        if normalized in BOILERPLATE_TITLE_LINES:
            continue
        if normalized.startswith(("doi", "arxiv", "http://", "https://")):
            continue
        if len(line) < 8 or len(line) > 180:
            continue
        if sum(char.isalpha() for char in line) < 4:
            continue
        if re.fullmatch(r"[\d\s./:-]+", line):
            continue
        return line
    return ""


def build_metadata_candidate_update(
    record: dict[str, str],
    candidate: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    updates: dict[str, str] = {}
    skipped: dict[str, str] = {}

    for field in APPLY_FIELDS:
        value = str(candidate.get(field, "") or "").strip()
        if not value:
            continue
        if field == "doi":
            value = normalize_doi(value)
        current = str(record.get(field, "") or "").strip()
        if current and not overwrite:
            skipped[field] = current
            continue
        updates[field] = value

    if updates:
        for field, candidate_key in (
            ("metadata_source", "source"),
            ("metadata_confidence", "confidence"),
        ):
            current = str(record.get(field, "") or "").strip()
            value = str(candidate.get(candidate_key, "") or "").strip()
            if value and (overwrite or not current):
                updates[field] = value
        current_checked_at = str(record.get("metadata_checked_at", "") or "").strip()
        if overwrite or not current_checked_at:
            updates["metadata_checked_at"] = utc_now_iso()
        if "doi" in updates:
            current_doi_source = str(record.get("doi_source", "") or "").strip()
            if overwrite or not current_doi_source:
                updates["doi_source"] = str(candidate.get("source", "") or "doi_less_metadata").strip()

    return {
        "updates": updates,
        "skipped_existing_fields": skipped,
        "changed_fields": list(updates),
    }


def apply_metadata_candidate_to_index(
    paper_id: str,
    candidate: dict[str, Any],
    *,
    overwrite: bool = False,
    index_csv: Path = INDEX_CSV,
) -> dict[str, Any]:
    df = load_index(index_csv)
    row_mask = df["paper_id"] == paper_id
    if not row_mask.any():
        return {
            "updated_fields": [],
            "skipped_existing_fields": {},
            "paper_found": False,
        }

    row = df[row_mask].iloc[0].to_dict()
    plan = build_metadata_candidate_update(row, candidate, overwrite=overwrite)
    updates = plan["updates"]
    if updates:
        for field, value in updates.items():
            if field in df.columns:
                df.loc[row_mask, field] = value
        df.loc[row_mask, "updated_at"] = utc_now_iso()
        save_index(df, index_csv)

    return {
        "updated_fields": [field for field in updates if field in df.columns],
        "skipped_existing_fields": plan["skipped_existing_fields"],
        "paper_found": True,
    }


def _candidate_text_for_record(record: dict[str, str], *, cache_dir: Path) -> tuple[str, list[str]]:
    diagnostics: list[str] = []
    paper_id = str(record.get("paper_id", "") or "")
    if paper_id:
        cached_text = load_cached_extracted_text(paper_id, cache_dir)
        if cached_text.strip():
            return cached_text[:20000], ["Used existing extracted-text cache."]

    pdf_path = Path(str(record.get("filepath", "") or ""))
    if not pdf_path.exists() or not pdf_path.is_file():
        return "", diagnostics + ["PDF text was unavailable because the file was not found."]

    try:
        text = extract_pdf_text_with_pypdf(pdf_path, max_pages=2)
    except Exception as exc:
        diagnostics.append(f"pypdf preview failed: {exc}")
        text = ""
    if text.strip():
        diagnostics.append("Read first PDF pages with pypdf for metadata fallback.")
        return text[:20000], diagnostics

    markitdown_text = extract_pdf_text_with_markitdown(pdf_path)
    if markitdown_text.strip():
        diagnostics.append("Read PDF text with MarkItDown for metadata fallback.")
        return markitdown_text[:20000], diagnostics

    return "", diagnostics + ["No readable PDF text was available for metadata fallback."]


def _arxiv_id_only_candidate(arxiv_id: str, diagnostic: str) -> dict[str, Any]:
    normalized = normalize_arxiv_id(arxiv_id)
    return {
        **empty_metadata_candidate(
            source="arxiv_id",
            confidence="medium",
            diagnostics=[diagnostic],
            arxiv_id=normalized,
        ),
        "year": _year_from_arxiv_id(normalized),
    }


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = _clean_metadata_text(raw_line)
        if line:
            lines.append(line)
    return lines


def _filename_title_guess(filename: str) -> str:
    stem = Path(str(filename or "")).stem
    if not stem:
        return ""
    stem = re.sub(MODERN_ARXIV_PATTERN, " ", stem)
    stem = re.sub(OLD_STYLE_ARXIV_PATTERN, " ", stem)
    stem = re.sub(r"\b(v\d+|pdf|final|draft)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_\-]+", " ", stem)
    title = _clean_metadata_text(stem)
    if not title or sum(char.isalpha() for char in title) < 4:
        return ""
    return title


def _modern_arxiv_id_is_valid(arxiv_id: str) -> bool:
    match = re.fullmatch(r"\d{4}\.\d{4,5}", arxiv_id)
    if not match:
        return False
    yymm = int(arxiv_id[:4])
    month = int(arxiv_id[2:4])
    if month < 1 or month > 12:
        return False
    current = datetime.now(timezone.utc)
    current_yymm = (current.year % 100) * 100 + current.month
    return 704 <= yymm <= current_yymm + 1


def _old_style_arxiv_id_is_valid(arxiv_id: str) -> bool:
    match = re.fullmatch(r"[a-z][a-z0-9.-]*/(\d{7})", arxiv_id)
    if not match:
        return False
    digits = match.group(1)
    month = int(digits[2:4])
    return 1 <= month <= 12


def _year_from_arxiv_id(arxiv_id: str) -> str:
    normalized = normalize_arxiv_id(arxiv_id)
    if not normalized:
        return ""
    if "/" in normalized:
        digits = normalized.rsplit("/", 1)[1]
        year = int(digits[:2])
        return str(1900 + year if year >= 91 else 2000 + year)
    year = int(normalized[:2])
    return str(2000 + year)


def _year_from_date(value: str) -> str:
    match = re.match(r"\s*(\d{4})", str(value or ""))
    return match.group(1) if match else ""


def _children(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == local_name]


def _child_text(element: ET.Element, local_name: str) -> str:
    for child in _children(element, local_name):
        return str(child.text or "")
    return ""


def _child_text_by_suffix(element: ET.Element, local_name: str) -> str:
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            return str(child.text or "")
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_metadata_text(value: str) -> str:
    return " ".join(str(value or "").split())
