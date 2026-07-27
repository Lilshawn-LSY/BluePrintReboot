from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from api.schemas import (
    EditablePaperMetadata,
    PaperDetail,
    PaperListItem,
    ProjectLink,
    ReaderNoteBaseline,
    ReaderNoteHeader,
    ReaderPdfState,
    ReaderSnapshotResponse,
)


class PaperContractError(ValueError):
    """A domain value cannot be represented by the public Paper API contract."""


def _required_identity(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise PaperContractError(f"Paper {field_name} is required.")
    return normalized


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value or "").strip()


def _year(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    normalized = str(value).strip()
    return "" if normalized.casefold() in {"nan", "none"} else normalized


def _boolean(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise PaperContractError(f"Paper {field_name} must be boolean.")


def _string_list(value: object) -> list[str]:
    source = value if isinstance(value, (list, tuple)) else _text(value).split(",")
    return [normalized for item in source if (normalized := _text(item))]


def _author_list(value: object) -> list[str]:
    source = value if isinstance(value, (list, tuple)) else _text(value).split(";")
    return [normalized for item in source if (normalized := _text(item))]


def _safe_filename(value: object) -> str:
    normalized = _text(value).replace("\\", "/")
    return PurePosixPath(normalized).name if normalized else ""


def _safe_relative_path(value: object) -> str:
    normalized = _text(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized:
        return ""
    if path.is_absolute() or PureWindowsPath(normalized).is_absolute() or ".." in path.parts:
        raise PaperContractError("Paper PDF path must be workspace-relative.")
    return path.as_posix()


def adapt_paper_list_item(source: Mapping[str, Any]) -> PaperListItem:
    return PaperListItem(
        paper_id=_required_identity(source.get("paper_id"), "paper_id"),
        title=_required_identity(source.get("title"), "title"),
        first_author=_text(source.get("first_author")),
        year=_year(source.get("year")),
        status=_text(source.get("status")) or "unread",
        priority=_text(source.get("priority")) or "normal",
        tags=_string_list(source.get("tags")),
        archived=_boolean(source.get("archived", False), "archived"),
        missing_pdf=_boolean(source.get("missing_pdf", False), "missing_pdf"),
        health=_string_list(source.get("health")),
    )


def adapt_paper_detail(source: Mapping[str, Any]) -> PaperDetail:
    base = adapt_paper_list_item(source)
    links = source.get("project_links", [])
    if not isinstance(links, (list, tuple)):
        raise PaperContractError("Paper project_links must be a list.")
    project_links = [
        ProjectLink(
            project_id=_text(link.get("project_id")),
            link_type=_text(link.get("link_type")),
            target_type=_text(link.get("target_type")),
        )
        for link in links
        if isinstance(link, Mapping)
    ]
    return PaperDetail(
        **base.model_dump(),
        authors=_author_list(source.get("authors")),
        journal=_text(source.get("journal")),
        abstract=_text(source.get("abstract")),
        keywords=_string_list(source.get("keywords")),
        arxiv_id=_text(source.get("arxiv_id")),
        filename=_safe_filename(source.get("filename")),
        relative_pdf_path=_safe_relative_path(source.get("relative_pdf_path")),
        doi=_text(source.get("doi")),
        project_links=project_links,
        note_available=_boolean(source.get("note_available", False), "note_available"),
        extracted_text_available=_boolean(
            source.get("extracted_text_available", False),
            "extracted_text_available",
        ),
        profile_available=_boolean(source.get("profile_available", False), "profile_available"),
        lifecycle_state=_text(source.get("lifecycle_state")) or ("archived" if base.archived else "active"),
        recoverable_warnings=_string_list(source.get("recoverable_warnings")),
    )


def _strict_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise PaperContractError(f"Reader {field_name} must be a string.")
    return value


def _reader_warnings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise PaperContractError("Reader warnings must be a list.")
    warnings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PaperContractError("Reader warnings must contain only strings.")
        normalized = item.strip()
        if normalized and normalized not in warnings:
            warnings.append(normalized)
    return warnings


def adapt_reader_snapshot(source: Mapping[str, Any]) -> ReaderSnapshotResponse:
    """Adapt one domain snapshot without re-reading or recomputing saved state."""

    paper_source = source.get("paper")
    header_source = source.get("canonical_note_header")
    baseline_source = source.get("saved_note_baseline")
    if not isinstance(paper_source, Mapping):
        raise PaperContractError("Reader paper must be an object.")
    if not isinstance(header_source, Mapping):
        raise PaperContractError("Reader canonical_note_header must be an object.")
    if not isinstance(baseline_source, Mapping):
        raise PaperContractError("Reader saved_note_baseline must be an object.")

    raw_pdf_state = _strict_string(source.get("pdf_state"), "pdf_state")
    try:
        pdf_state = ReaderPdfState(raw_pdf_state)
    except ValueError:
        raise PaperContractError("Reader pdf_state is not supported.") from None

    saved_note_available = source.get("saved_note_available")
    if not isinstance(saved_note_available, bool):
        raise PaperContractError("Reader saved_note_available must be boolean.")
    saved_note_content = _strict_string(source.get("saved_note_content"), "saved_note_content")
    if not saved_note_available and saved_note_content:
        raise PaperContractError("Reader unavailable saved note cannot expose content.")
    unavailable_reason = _strict_string(source.get("unavailable_reason"), "unavailable_reason")

    paper = adapt_paper_detail(paper_source)
    expected_pdf_state = ReaderPdfState.missing if paper.missing_pdf else ReaderPdfState.available
    if pdf_state is not expected_pdf_state:
        raise PaperContractError("Reader pdf_state conflicts with paper availability.")
    if pdf_state is ReaderPdfState.missing and not unavailable_reason.strip():
        raise PaperContractError("Reader missing PDF state requires an unavailable reason.")
    if pdf_state is ReaderPdfState.available and unavailable_reason:
        raise PaperContractError("Reader available PDF state cannot include an unavailable reason.")

    header = ReaderNoteHeader(
        template_version=_strict_string(header_source.get("template_version"), "canonical_note_header.template_version"),
        paper_id=_strict_string(header_source.get("paper_id"), "canonical_note_header.paper_id"),
        title=_strict_string(header_source.get("title"), "canonical_note_header.title"),
        doi=_strict_string(header_source.get("doi"), "canonical_note_header.doi"),
        arxiv_id=_strict_string(header_source.get("arxiv_id"), "canonical_note_header.arxiv_id"),
        year=_strict_string(header_source.get("year"), "canonical_note_header.year"),
        first_author=_strict_string(header_source.get("first_author"), "canonical_note_header.first_author"),
        tags=_strict_string(header_source.get("tags"), "canonical_note_header.tags"),
    )
    if header.paper_id != paper.paper_id:
        raise PaperContractError("Reader canonical note identity conflicts with paper identity.")

    metadata_source = source.get("editable_metadata")
    if not isinstance(metadata_source, Mapping):
        raise PaperContractError("Reader editable_metadata must be an object.")
    editable_metadata = EditablePaperMetadata(
        title=_strict_string(metadata_source.get("title"), "editable_metadata.title"),
        authors=_strict_string(metadata_source.get("authors"), "editable_metadata.authors"),
        year=_strict_string(metadata_source.get("year"), "editable_metadata.year"),
        journal=_strict_string(metadata_source.get("journal"), "editable_metadata.journal"),
        doi=_strict_string(metadata_source.get("doi"), "editable_metadata.doi"),
        abstract=_strict_string(metadata_source.get("abstract"), "editable_metadata.abstract"),
        keywords=_strict_string(metadata_source.get("keywords"), "editable_metadata.keywords"),
    )
    metadata_revision = _strict_string(source.get("metadata_revision"), "metadata_revision")
    if len(metadata_revision) != 64 or any(
        character not in "0123456789abcdef" for character in metadata_revision
    ):
        raise PaperContractError("Reader metadata_revision must be a lowercase SHA-256 value.")

    note_exists = baseline_source.get("exists")
    if not isinstance(note_exists, bool):
        raise PaperContractError("Reader saved_note_baseline.exists must be boolean.")
    sha256 = _strict_string(baseline_source.get("sha256"), "saved_note_baseline.sha256")
    size_bytes = baseline_source.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise PaperContractError("Reader saved_note_baseline.size_bytes must be a non-negative integer.")
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise PaperContractError("Reader saved_note_baseline.sha256 must be a lowercase SHA-256 value.")
    if saved_note_available and not note_exists:
        raise PaperContractError("Reader saved note availability conflicts with note existence.")
    if saved_note_available:
        encoded = saved_note_content.encode("utf-8")
        if size_bytes != len(encoded) or sha256 != hashlib.sha256(encoded).hexdigest():
            raise PaperContractError("Reader saved note baseline conflicts with saved content.")

    return ReaderSnapshotResponse(
        paper=paper,
        editable_metadata=editable_metadata,
        metadata_revision=metadata_revision,
        pdf_state=pdf_state,
        saved_note_available=saved_note_available,
        saved_note_content=saved_note_content,
        canonical_note_header=header,
        saved_note_baseline=ReaderNoteBaseline(
            exists=note_exists,
            sha256=sha256,
            size_bytes=size_bytes,
        ),
        warnings=_reader_warnings(source.get("warnings")),
        unavailable_reason=unavailable_reason,
    )
