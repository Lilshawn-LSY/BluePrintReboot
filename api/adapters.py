from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from api.schemas import (
    CandidateQualityCounts,
    CandidateSummaryResponse,
    CanonicalTag,
    EditablePaperMetadata,
    LinkedPaperSummary,
    PaperDetail,
    PaperListItem,
    ProjectDetail,
    ProjectLink,
    ProjectLinkTarget,
    ProjectListItem,
    ProjectTargetState,
    ReaderNoteBaseline,
    ReaderNoteHeader,
    ReaderPdfState,
    ReaderSnapshotResponse,
)


class PaperContractError(ValueError):
    """A domain value cannot be represented by the public Paper API contract."""


class ProjectContractError(ValueError):
    """A domain value cannot be represented by the public Project API contract."""


class TagContractError(ValueError):
    """A domain value cannot be represented by the public Tag API contract."""


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


def _strict_text(value: object, field_name: str, error_type: type[ValueError]) -> str:
    if not isinstance(value, str):
        raise error_type(f"{field_name} must be a string.")
    return value.strip()


def _strict_string_list(
    value: object,
    field_name: str,
    error_type: type[ValueError],
) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise error_type(f"{field_name} must be a list.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise error_type(f"{field_name} must contain only strings.")
        normalized = item.strip()
        if normalized:
            result.append(normalized)
    return result


def _nonnegative_integer(
    value: object,
    field_name: str,
    error_type: type[ValueError],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error_type(f"{field_name} must be a non-negative integer.")
    return value


def adapt_project_list_item(source: Mapping[str, Any]) -> ProjectListItem:
    project_id = _strict_text(source.get("project_id"), "project_id", ProjectContractError)
    name = _strict_text(source.get("name"), "name", ProjectContractError)
    if not project_id or not name:
        raise ProjectContractError("Project identity and name are required.")
    return ProjectListItem(
        project_id=project_id,
        name=name,
        description=_strict_text(
            source.get("description"),
            "description",
            ProjectContractError,
        ),
        status=_strict_text(source.get("status"), "status", ProjectContractError),
        priority=_strict_text(source.get("priority"), "priority", ProjectContractError),
        tags=_strict_string_list(source.get("tags"), "tags", ProjectContractError),
        created_at=_strict_text(
            source.get("created_at"),
            "created_at",
            ProjectContractError,
        ),
        updated_at=_strict_text(
            source.get("updated_at"),
            "updated_at",
            ProjectContractError,
        ),
        link_count=_nonnegative_integer(
            source.get("link_count"),
            "link_count",
            ProjectContractError,
        ),
        linked_paper_count=_nonnegative_integer(
            source.get("linked_paper_count"),
            "linked_paper_count",
            ProjectContractError,
        ),
    )


def _adapt_linked_paper(source: Mapping[str, Any]) -> LinkedPaperSummary:
    paper_id = _strict_text(source.get("paper_id"), "paper.paper_id", ProjectContractError)
    if not paper_id:
        raise ProjectContractError("Linked paper identity is required.")
    archived = source.get("archived")
    if not isinstance(archived, bool):
        raise ProjectContractError("paper.archived must be boolean.")
    return LinkedPaperSummary(
        paper_id=paper_id,
        title=_strict_text(source.get("title"), "paper.title", ProjectContractError),
        first_author=_strict_text(
            source.get("first_author"),
            "paper.first_author",
            ProjectContractError,
        ),
        year=_strict_text(source.get("year"), "paper.year", ProjectContractError),
        status=_strict_text(source.get("status"), "paper.status", ProjectContractError),
        priority=_strict_text(
            source.get("priority"),
            "paper.priority",
            ProjectContractError,
        ),
        tags=_strict_string_list(source.get("tags"), "paper.tags", ProjectContractError),
        archived=archived,
    )


def adapt_project_detail(
    source: Mapping[str, Any],
    *,
    links_limit: int,
    links_offset: int,
) -> ProjectDetail:
    base = adapt_project_list_item(source)
    raw_links = source.get("links")
    if not isinstance(raw_links, (list, tuple)):
        raise ProjectContractError("Project links must be a list.")
    links: list[ProjectLinkTarget] = []
    for raw_link in raw_links:
        if not isinstance(raw_link, Mapping):
            raise ProjectContractError("Project links must be objects.")
        try:
            target_state = ProjectTargetState(
                _strict_text(
                    raw_link.get("target_state"),
                    "link.target_state",
                    ProjectContractError,
                )
            )
        except ValueError:
            raise ProjectContractError("Project target state is unsupported.") from None
        raw_paper = raw_link.get("paper")
        paper = _adapt_linked_paper(raw_paper) if isinstance(raw_paper, Mapping) else None
        if target_state is ProjectTargetState.available and paper is None:
            target_state = ProjectTargetState.unavailable
        if target_state is not ProjectTargetState.available and paper is not None:
            raise ProjectContractError("Unavailable Project targets cannot expose paper data.")
        links.append(
            ProjectLinkTarget(
                link_id=_strict_text(
                    raw_link.get("link_id"),
                    "link.link_id",
                    ProjectContractError,
                ),
                link_type=_strict_text(
                    raw_link.get("link_type"),
                    "link.link_type",
                    ProjectContractError,
                ),
                target_type=_strict_text(
                    raw_link.get("target_type"),
                    "link.target_type",
                    ProjectContractError,
                ),
                target_state=target_state,
                paper_id=_strict_text(
                    raw_link.get("paper_id"),
                    "link.paper_id",
                    ProjectContractError,
                ),
                created_at=_strict_text(
                    raw_link.get("created_at"),
                    "link.created_at",
                    ProjectContractError,
                ),
                paper=paper,
            )
        )
    links.sort(key=lambda link: (link.created_at, link.link_id))
    page = links[links_offset : links_offset + links_limit]
    total = len(links)
    return ProjectDetail(
        **base.model_dump(),
        links=page,
        links_total=total,
        links_limit=links_limit,
        links_offset=links_offset,
        links_has_more=links_offset + len(page) < total,
        orphaned_link_count=_nonnegative_integer(
            source.get("orphaned_link_count"),
            "orphaned_link_count",
            ProjectContractError,
        ),
    )


def adapt_canonical_tag(source: Mapping[str, Any]) -> CanonicalTag:
    canonical_key = _strict_text(
        source.get("canonical_key"),
        "canonical_key",
        TagContractError,
    )
    label = _strict_text(source.get("label"), "label", TagContractError)
    if not canonical_key or not label:
        raise TagContractError("Canonical tag identity and label are required.")
    return CanonicalTag(
        canonical_key=canonical_key,
        label=label,
        category=_strict_text(source.get("category"), "category", TagContractError),
        aliases=_strict_string_list(source.get("aliases"), "aliases", TagContractError),
        status=_strict_text(source.get("status"), "status", TagContractError),
        suggestion_strength=_nonnegative_integer(
            source.get("suggestion_strength"),
            "suggestion_strength",
            TagContractError,
        ),
    )


def adapt_candidate_summary(source: Mapping[str, Any]) -> CandidateSummaryResponse:
    quality = source.get("quality_counts")
    if not isinstance(quality, Mapping):
        raise TagContractError("Candidate quality counts must be an object.")
    try:
        return CandidateSummaryResponse(
            availability=_strict_text(
                source.get("availability"),
                "availability",
                TagContractError,
            ),
            state=_strict_text(source.get("state"), "state", TagContractError),
            source=_strict_text(source.get("source"), "source", TagContractError),
            evaluated_paper_count=_nonnegative_integer(
                source.get("evaluated_paper_count"),
                "evaluated_paper_count",
                TagContractError,
            ),
            candidate_count=_nonnegative_integer(
                source.get("candidate_count"),
                "candidate_count",
                TagContractError,
            ),
            known_canonical_match_count=_nonnegative_integer(
                source.get("known_canonical_match_count"),
                "known_canonical_match_count",
                TagContractError,
            ),
            quality_counts=CandidateQualityCounts(
                high=_nonnegative_integer(quality.get("high"), "quality.high", TagContractError),
                medium=_nonnegative_integer(
                    quality.get("medium"),
                    "quality.medium",
                    TagContractError,
                ),
                weak=_nonnegative_integer(quality.get("weak"), "quality.weak", TagContractError),
                rejected=_nonnegative_integer(
                    quality.get("rejected"),
                    "quality.rejected",
                    TagContractError,
                ),
            ),
        )
    except ValueError as error:
        if isinstance(error, TagContractError):
            raise
        raise TagContractError("Candidate summary contains unsupported values.") from None


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
