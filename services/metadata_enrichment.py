from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from ingest.crossref import CrossrefLookupError, lookup_crossref_metadata
from ingest.doi import is_probable_doi, normalize_doi
from ingest.scanner import DoiExtractionResult, extract_doi_metadata_from_pdf
from services.metadata_fallback import build_doi_less_metadata_candidate
from services.paper_metadata_mutation import (
    WEB_EDITABLE_METADATA_FIELDS,
    normalize_paper_metadata_value,
    normalized_web_metadata,
    paper_metadata_revision,
)
from storage.index_store import read_index_snapshot
from storage.paths import EXTRACTED_TEXT_DIR, INDEX_CSV, PAPERS_DIR


class MetadataEnrichmentError(Exception):
    """Base class for bounded metadata-enrichment preview failures."""


class MetadataEnrichmentNotFound(MetadataEnrichmentError):
    """The requested stable Paper identity does not exist."""


class MetadataEnrichmentUnavailable(MetadataEnrichmentError):
    """The preview could not be built from local state consistently."""


MetadataFieldName = str


@dataclass(frozen=True)
class MetadataEnrichmentField:
    field: MetadataFieldName
    current_value: str
    candidate_value: str
    source: str
    state: str


@dataclass(frozen=True)
class MetadataEnrichmentPreview:
    paper_id: str
    metadata_revision: str
    candidate_sources: tuple[str, ...]
    fields: tuple[MetadataEnrichmentField, ...]
    diagnostics: tuple[str, ...]


_SOURCE_LABELS = {
    "crossref": "Crossref",
    "pdf_doi": "PDF-derived DOI",
    "arxiv_id": "arXiv",
    "pdf_profile": "PDF-derived profile",
    "pdf_text_guess": "PDF text guess",
    "filename_guess": "Filename guess",
    "none": "",
}


def _source_label(source: object) -> str:
    normalized = str(source or "").strip()
    if not normalized:
        return ""
    labels = [_SOURCE_LABELS.get(part.strip(), part.strip()) for part in normalized.split("+")]
    return " + ".join(label for label in labels if label)


def _safe_diagnostics(values: Sequence[object]) -> list[str]:
    """Keep provider status useful without returning exceptions or local paths."""

    safe: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        lowered = text.casefold()
        if lowered.startswith("crossref metadata candidate retrieved"):
            message = "Crossref metadata candidate retrieved."
        elif lowered.startswith("crossref returned no supported"):
            message = "Crossref returned no supported metadata fields."
        elif lowered.startswith("crossref metadata lookup was unavailable"):
            message = "Crossref metadata lookup was unavailable; local fallback was checked."
        elif lowered.startswith("the stored doi is not valid"):
            message = "The stored DOI is not valid enough for Crossref lookup; local fallback was checked."
        elif lowered.startswith("a doi was detected from the managed pdf"):
            message = "A DOI was detected from the managed PDF for lookup only; it was not saved."
        elif lowered.startswith("pdf doi detection was unavailable"):
            message = "PDF DOI detection was unavailable."
        elif lowered.startswith("local metadata fallback was unavailable"):
            message = "Local metadata fallback was unavailable."
        elif "pypdf preview failed" in lowered or "markitdown" in lowered and "failed" in lowered:
            message = "PDF metadata preview was unavailable."
        elif "arxiv" in lowered and ("failed" in lowered or "timed out" in lowered or "network" in lowered or "ssl" in lowered or "http" in lowered or "malformed" in lowered):
            message = "arXiv metadata lookup was unavailable; local candidate values remain available when present."
        elif lowered.startswith("arxiv metadata parsed"):
            message = "arXiv metadata was parsed."
        elif lowered.startswith("arxiv metadata missing"):
            message = text
        elif lowered.startswith("arxiv id found"):
            message = text
        elif lowered.startswith("used existing extracted-text cache"):
            message = "Used the existing extracted-text cache for a local metadata candidate."
        elif lowered.startswith("read first pdf pages"):
            message = "Read the first PDF pages for a local metadata candidate."
        elif lowered.startswith("pdf profile"):
            message = text
        elif lowered.startswith("title-like text") or lowered.startswith("filename was used"):
            message = text
        elif lowered.startswith("no readable pdf") or lowered.startswith("pdf text was unavailable") or lowered.startswith("no doi-less metadata"):
            message = text
        elif lowered.startswith("filled blank metadata fields"):
            message = text
        else:
            # Candidate builders are extensible. Do not expose arbitrary exception text
            # or storage details from a future provider through this public contract.
            continue
        if message not in safe:
            safe.append(message)
    return safe[:20]


def _safe_managed_pdf_path(record: Mapping[str, object], papers_dir: Path) -> Path | None:
    """Resolve only an indexed PDF that remains inside the managed papers directory."""

    root = Path(papers_dir).resolve(strict=False)
    raw_path = str(record.get("filepath", "") or "").strip()
    filename = str(record.get("filename", "") or "").strip()
    candidate = Path(raw_path) if raw_path else root / filename
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


class MetadataEnrichmentService:
    """Read-only candidate builder for the explicit web enrichment workflow.

    This service deliberately never calls an index save or a Reader command. The
    existing ``ReaderCommandService.save_metadata`` command remains the only path
    that persists a user-selected subset of these candidate values.
    """

    def __init__(
        self,
        *,
        index_csv: Path = INDEX_CSV,
        papers_dir: Path = PAPERS_DIR,
        extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
        crossref_lookup: Callable[[str], Mapping[str, object]] | None = None,
        fallback_builder: Callable[[dict[str, str]], Mapping[str, object]] | None = None,
        doi_extractor: Callable[[Path], DoiExtractionResult] | None = None,
    ) -> None:
        self.index_csv = Path(index_csv)
        self.papers_dir = Path(papers_dir)
        self.extracted_text_dir = Path(extracted_text_dir)
        self._crossref_lookup = crossref_lookup or lookup_crossref_metadata
        self._doi_extractor = doi_extractor or extract_doi_metadata_from_pdf
        self._fallback_builder = fallback_builder or (
            lambda record: build_doi_less_metadata_candidate(
                record,
                cache_dir=self.extracted_text_dir,
            )
        )

    def preview(self, paper_id: str) -> MetadataEnrichmentPreview:
        try:
            dataframe = read_index_snapshot(self.index_csv)
        except Exception:
            raise MetadataEnrichmentUnavailable from None
        if "paper_id" not in dataframe:
            raise MetadataEnrichmentUnavailable
        matches = dataframe[dataframe["paper_id"] == paper_id]
        if matches.empty:
            raise MetadataEnrichmentNotFound

        record = {
            str(key): str(value)
            for key, value in matches.iloc[0].fillna("").to_dict().items()
        }
        current = normalized_web_metadata(record)
        diagnostics: list[str] = []
        candidates: dict[str, str] = {}
        field_sources: dict[str, str] = {}

        doi = normalize_doi(record.get("doi", ""))
        safe_pdf_path = _safe_managed_pdf_path(record, self.papers_dir)
        if not doi and safe_pdf_path is not None:
            try:
                extracted = self._doi_extractor(safe_pdf_path)
            except Exception:
                extracted = DoiExtractionResult()
                diagnostics.append("PDF DOI detection was unavailable.")
            extracted_doi = normalize_doi(extracted.doi)
            if extracted_doi:
                doi = extracted_doi
                candidates["doi"] = extracted_doi
                field_sources["doi"] = "pdf_doi"
                diagnostics.append(
                    "A DOI was detected from the managed PDF for lookup only; it was not saved."
                )

        if doi and is_probable_doi(doi):
            try:
                crossref = dict(self._crossref_lookup(doi))
                for field in WEB_EDITABLE_METADATA_FIELDS:
                    value = normalize_paper_metadata_value(field, crossref.get(field, ""))
                    if value:
                        candidates[field] = value
                        field_sources[field] = "crossref"
                if candidates:
                    diagnostics.append("Crossref metadata candidate retrieved.")
                else:
                    diagnostics.append("Crossref returned no supported metadata fields.")
            except CrossrefLookupError:
                diagnostics.append("Crossref metadata lookup was unavailable; local fallback was checked.")
            except Exception:
                diagnostics.append("Crossref metadata lookup was unavailable; local fallback was checked.")
        elif record.get("doi", ""):
            diagnostics.append("The stored DOI is not valid enough for Crossref lookup; local fallback was checked.")

        # Existing DOI-less enrichment provides arXiv, PDF-profile, PDF-text, and
        # filename fallbacks. It supplements only fields Crossref did not provide;
        # it never considers existing stored values when constructing a candidate.
        fallback_record = dict(record)
        fallback_record["filepath"] = str(safe_pdf_path) if safe_pdf_path is not None else ""
        try:
            fallback = dict(self._fallback_builder(fallback_record))
        except Exception:
            fallback = {}
            diagnostics.append("Local metadata fallback was unavailable.")

        fallback_source = str(fallback.get("source", "") or "")
        fallback_field_sources = fallback.get("field_sources", {})
        if not isinstance(fallback_field_sources, Mapping):
            fallback_field_sources = {}
        for field in WEB_EDITABLE_METADATA_FIELDS:
            if candidates.get(field):
                continue
            value = normalize_paper_metadata_value(field, fallback.get(field, ""))
            if value:
                candidates[field] = value
                field_sources[field] = str(fallback_field_sources.get(field) or fallback_source)
        diagnostics.extend(_safe_diagnostics(fallback.get("diagnostics", [])))

        fields: list[MetadataEnrichmentField] = []
        sources: list[str] = []
        for field in WEB_EDITABLE_METADATA_FIELDS:
            current_value = current[field]
            candidate_value = candidates.get(field, "")
            source = _source_label(field_sources.get(field, ""))
            if candidate_value:
                if source and source not in sources:
                    sources.append(source)
                state = (
                    "unchanged"
                    if normalize_paper_metadata_value(field, current_value)
                    == normalize_paper_metadata_value(field, candidate_value)
                    else "conflict" if current_value else "available"
                )
            else:
                state = "unavailable"
            fields.append(
                MetadataEnrichmentField(
                    field=field,
                    current_value=current_value,
                    candidate_value=candidate_value,
                    source=source,
                    state=state,
                )
            )

        return MetadataEnrichmentPreview(
            paper_id=paper_id,
            metadata_revision=paper_metadata_revision(record),
            candidate_sources=tuple(sources),
            fields=tuple(fields),
            diagnostics=tuple(_safe_diagnostics(diagnostics)),
        )
