from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ingest.crossref import CrossrefLookupError, lookup_crossref_metadata
from ingest.doi import extract_doi_from_text, is_probable_doi, normalize_doi
from ingest.text_extractor import extract_full_text_from_pdf
from services.metadata_fallback import (
    build_doi_less_metadata_candidate,
    pdf_evidence_field_source,
)
from services.paper_metadata_mutation import (
    WEB_EDITABLE_METADATA_FIELDS,
    normalize_paper_metadata_value,
    normalized_web_metadata,
    paper_metadata_revision,
)
from storage.extracted_text_store import extraction_cache_status, load_cached_extracted_text
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


LOCAL_PDF_EVIDENCE_CHAR_LIMIT = 30000


@dataclass(frozen=True)
class LocalPdfEvidence:
    """Bounded, non-persisting PDF text used only during one metadata preview."""

    text: str = ""
    provider: str = "none"
    origin: str = "none"
    content_format: str = "plain_text"
    diagnostics: tuple[str, ...] = ()


_SOURCE_LABELS = {
    "crossref": "Crossref",
    "pdf_doi": "PDF-derived DOI",
    "pdf_doi_pdf_inspector": "PDF-derived DOI · pdf-inspector",
    "pdf_doi_markitdown": "PDF-derived DOI · MarkItDown fallback",
    "pdf_doi_pypdf": "PDF-derived DOI · pypdf fallback",
    "arxiv_id": "arXiv",
    "pdf_profile": "PDF-derived profile",
    "pdf_profile_pdf_inspector": "PDF-derived profile · pdf-inspector",
    "pdf_profile_markitdown": "PDF-derived profile · MarkItDown fallback",
    "pdf_profile_pypdf": "PDF-derived profile · pypdf fallback",
    "pdf_text_guess": "PDF text guess",
    "pdf_text_guess_pdf_inspector": "PDF text guess · pdf-inspector",
    "pdf_text_guess_markitdown": "PDF text guess · MarkItDown fallback",
    "pdf_text_guess_pypdf": "PDF text guess · pypdf fallback",
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
        elif lowered.startswith("used current canonical pdf extraction cache"):
            message = "Used the current canonical PDF extraction cache for local metadata evidence."
        elif lowered.startswith("the canonical extraction cache is stale"):
            message = "The canonical extraction cache is stale; current PDF evidence was read without replacing it."
        elif lowered.startswith("read current pdf with pdf-inspector"):
            message = "Read current PDF evidence with pdf-inspector without persisting an extraction cache."
        elif lowered.startswith("read current pdf with markitdown"):
            message = "Read current PDF evidence with the MarkItDown fallback without persisting an extraction cache."
        elif lowered.startswith("read current pdf with pypdf"):
            message = "Read current PDF evidence with the pypdf fallback without persisting an extraction cache."
        elif lowered.startswith("no readable current pdf evidence"):
            message = "No readable current PDF evidence was available for local metadata preview."
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


def resolve_local_pdf_evidence(
    paper_id: str,
    pdf_path: Path | None,
    *,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> LocalPdfEvidence:
    """Read current canonical evidence or preview-extract once without writes."""

    if pdf_path is None or not pdf_path.is_file():
        return LocalPdfEvidence(
            diagnostics=("No readable current PDF evidence was available for local metadata preview.",),
        )

    cache_diagnostics: list[str] = []
    try:
        status = extraction_cache_status(paper_id, cache_dir, pdf_path=pdf_path)
    except Exception:
        status = {}
    if bool(status.get("has_reusable_text_cache")) and not bool(status.get("is_stale")):
        try:
            cached_text = load_cached_extracted_text(paper_id, cache_dir)
        except Exception:
            cached_text = ""
        if cached_text.strip():
            return LocalPdfEvidence(
                text=cached_text[:LOCAL_PDF_EVIDENCE_CHAR_LIMIT],
                provider=_bounded_evidence_provider(status.get("provider") or status.get("source")),
                origin="cache",
                content_format=_bounded_content_format(status.get("content_format")),
                diagnostics=("Used current canonical PDF extraction cache for local metadata evidence.",),
            )
    if bool(status.get("is_stale")):
        cache_diagnostics.append(
            "The canonical extraction cache is stale; current PDF evidence was read without replacing it."
        )

    try:
        extracted = extract_full_text_from_pdf(pdf_path)
    except Exception:
        extracted = None
    text = str(getattr(extracted, "text", "") or "")
    provider = _bounded_evidence_provider(
        getattr(extracted, "provider", "") or getattr(extracted, "source", "")
    )
    if text.strip():
        provider_diagnostic = {
            "pdf-inspector": "Read current PDF with pdf-inspector for non-persisting metadata evidence.",
            "markitdown": "Read current PDF with MarkItDown fallback for non-persisting metadata evidence.",
            "pypdf": "Read current PDF with pypdf fallback for non-persisting metadata evidence.",
        }.get(provider, "No readable current PDF evidence was available for local metadata preview.")
        return LocalPdfEvidence(
            text=text[:LOCAL_PDF_EVIDENCE_CHAR_LIMIT],
            provider=provider,
            origin="preview",
            content_format=_bounded_content_format(getattr(extracted, "content_format", "")),
            diagnostics=tuple([*cache_diagnostics, provider_diagnostic]),
        )
    return LocalPdfEvidence(
        provider=provider,
        origin="preview",
        diagnostics=tuple([
            *cache_diagnostics,
            "No readable current PDF evidence was available for local metadata preview.",
        ]),
    )


def _bounded_evidence_provider(value: object) -> str:
    provider = str(value or "").strip().casefold()
    return provider if provider in {"pdf-inspector", "markitdown", "pypdf"} else "none"


def _bounded_content_format(value: object) -> str:
    return "markdown" if str(value or "").strip() == "markdown" else "plain_text"


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
        local_evidence_resolver: Callable[[str, Path | None], LocalPdfEvidence] | None = None,
        arxiv_request_get: Callable[..., Any] | None = None,
    ) -> None:
        self.index_csv = Path(index_csv)
        self.papers_dir = Path(papers_dir)
        self.extracted_text_dir = Path(extracted_text_dir)
        self._crossref_lookup = crossref_lookup or lookup_crossref_metadata
        self._fallback_builder = fallback_builder
        self._local_evidence_resolver = local_evidence_resolver or (
            lambda paper_id, pdf_path: resolve_local_pdf_evidence(
                paper_id,
                pdf_path,
                cache_dir=self.extracted_text_dir,
            )
        )
        self._arxiv_request_get = arxiv_request_get

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
        local_evidence: LocalPdfEvidence | None = None

        def evidence() -> LocalPdfEvidence:
            nonlocal local_evidence
            if local_evidence is None:
                try:
                    local_evidence = self._local_evidence_resolver(paper_id, safe_pdf_path)
                except Exception:
                    local_evidence = LocalPdfEvidence(
                        diagnostics=("No readable current PDF evidence was available for local metadata preview.",),
                    )
                diagnostics.extend(local_evidence.diagnostics)
            return local_evidence

        if not doi:
            pdf_evidence = evidence()
            try:
                extracted_doi = normalize_doi(extract_doi_from_text(pdf_evidence.text))
            except Exception:
                extracted_doi = ""
                diagnostics.append("PDF DOI detection was unavailable.")
            if extracted_doi:
                doi = extracted_doi
                candidates["doi"] = extracted_doi
                field_sources["doi"] = pdf_evidence_field_source(
                    "pdf_doi",
                    pdf_evidence.provider,
                )
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
            if self._fallback_builder is not None:
                fallback = dict(self._fallback_builder(fallback_record))
            else:
                pdf_evidence = evidence()
                fallback = dict(
                    build_doi_less_metadata_candidate(
                        fallback_record,
                        pdf_text=pdf_evidence.text,
                        pdf_evidence_provider=pdf_evidence.provider,
                        cache_dir=self.extracted_text_dir,
                        request_get=self._arxiv_request_get,
                    )
                )
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
