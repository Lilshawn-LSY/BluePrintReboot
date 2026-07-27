from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import FileResponse

from api.adapters import (
    PaperContractError,
    ProjectContractError,
    SettingsContractError,
    TagContractError,
    adapt_candidate_summary,
    adapt_canonical_tag,
    adapt_paper_detail,
    adapt_paper_list_item,
    adapt_project_detail,
    adapt_project_list_item,
    adapt_reader_snapshot,
    adapt_settings_summary,
)
from api.dependencies import (
    ReadModelUnavailable,
    get_candidate_summary,
    get_canonical_tags,
    get_health_summary,
    get_library_status,
    get_managed_pdf,
    get_paper_detail,
    get_paper_list_items,
    get_project_detail,
    get_project_list_items,
    get_reader_command_service,
    get_reader_snapshot,
    get_settings_summary,
)
from api.pdf_files import ManagedPdfResult, ManagedPdfState
from api.schemas import (
    APIError,
    ArchiveStatus,
    CandidateSummaryResponse,
    HealthSummaryResponse,
    LibraryStatusResponse,
    MetadataCommandRequest,
    MetadataCommandResponse,
    PaginatedPaperList,
    PaginatedProjectList,
    PaginatedTagList,
    PaperDetail,
    ReadingNoteCommandRequest,
    ReadingNoteCommandResponse,
    ReaderSnapshotResponse,
    SettingsSummaryResponse,
    ProjectDetail,
)
from services.library_read_model import HealthSummary, LibraryStatus, PaperDetail as DomainPaperDetail, PaperListItem as DomainPaperListItem, ReaderSnapshot as DomainReaderSnapshot
from services.project_read_model import ProjectDetail as DomainProjectDetail, ProjectListItem as DomainProjectListItem
from services.reader_commands import ReaderCommandConflict, ReaderCommandNotFound, ReaderCommandService, ReaderCommandUnavailable
from services.settings_read_model import SettingsSummary as DomainSettingsSummary
from services.tag_read_model import CandidateSummary as DomainCandidateSummary, CanonicalTag as DomainCanonicalTag


router = APIRouter()

PDF_MISSING_DETAIL = "Managed PDF not found."
PDF_INVALID_DETAIL = "Managed PDF path is invalid."
PDF_UNAVAILABLE_DETAIL = "Managed PDF is temporarily unavailable."
COMMAND_CONFLICT_DETAIL = "The saved Reader state changed. Reload the current version before retrying."
COMMAND_UNAVAILABLE_DETAIL = "The Reader command could not be completed."
COMMAND_INVALID_DETAIL = "Request validation failed."


@router.get("/health", response_model=HealthSummaryResponse)
def health(summary: Annotated[HealthSummary, Depends(get_health_summary)]) -> HealthSummary:
    return summary


@router.get("/library/status", response_model=LibraryStatusResponse)
def library_status(status: Annotated[LibraryStatus, Depends(get_library_status)]) -> LibraryStatus:
    return status


@router.get(
    "/settings/summary",
    response_model=SettingsSummaryResponse,
    summary="Get safe Settings summary",
    description=(
        "Return bounded application, workspace, data-integrity, and backup-readiness "
        "facts without exposing paths, records, hashes, environment data, or actions."
    ),
    responses={
        503: {
            "model": APIError,
            "description": "The safe Settings read model is temporarily unavailable.",
        }
    },
)
def settings_summary(
    summary: Annotated[DomainSettingsSummary, Depends(get_settings_summary)],
) -> SettingsSummaryResponse:
    try:
        return adapt_settings_summary(summary)
    except SettingsContractError:
        raise ReadModelUnavailable from None


@router.get(
    "/projects",
    response_model=PaginatedProjectList,
    summary="List Projects",
    description="Return a deterministic, bounded page of allowlisted Project summaries.",
)
def list_projects(
    projects: Annotated[list[DomainProjectListItem], Depends(get_project_list_items)],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of Projects to return (1-100).")] = 20,
    offset: Annotated[int, Query(ge=0, description="Zero-based Project offset.")] = 0,
) -> PaginatedProjectList:
    try:
        adapted = sorted(
            (adapt_project_list_item(project) for project in projects),
            key=lambda project: (project.name.casefold(), project.project_id),
        )
    except ProjectContractError:
        raise ReadModelUnavailable from None
    total = len(adapted)
    items = adapted[offset : offset + limit]
    return PaginatedProjectList(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get(
    "/projects/{project_id}",
    response_model=ProjectDetail,
    summary="Get Project detail",
    description="Return one Project and a bounded page of its stored links and allowlisted paper summaries.",
    responses={
        404: {
            "model": APIError,
            "description": "No Project has the requested identity.",
            "content": {"application/json": {"example": {"detail": "Project not found."}}},
        },
        503: {
            "model": APIError,
            "description": "The local Project read model is temporarily unavailable.",
        },
    },
)
def project_detail(
    project_id: Annotated[str, Path(min_length=1, description="Stable Project identity.")],
    project: Annotated[DomainProjectDetail | None, Depends(get_project_detail)],
    links_limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of Project links to return (1-100).")] = 20,
    links_offset: Annotated[int, Query(ge=0, description="Zero-based Project-link offset.")] = 0,
) -> ProjectDetail:
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        return adapt_project_detail(
            project,
            links_limit=links_limit,
            links_offset=links_offset,
        )
    except ProjectContractError:
        raise ReadModelUnavailable from None


@router.get(
    "/tags",
    response_model=PaginatedTagList,
    summary="List canonical tags",
    description="Return a deterministic, bounded page of the canonical Tag Book allowlist.",
)
def list_tags(
    tag_result: Annotated[tuple[list[DomainCanonicalTag], bool], Depends(get_canonical_tags)],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of canonical tags to return (1-100).")] = 20,
    offset: Annotated[int, Query(ge=0, description="Zero-based canonical-tag offset.")] = 0,
) -> PaginatedTagList:
    tags, loaded_from_fallback = tag_result
    try:
        adapted = sorted(
            (adapt_canonical_tag(tag) for tag in tags),
            key=lambda tag: (tag.label.casefold(), tag.canonical_key),
        )
    except TagContractError:
        raise ReadModelUnavailable from None
    total = len(adapted)
    items = adapted[offset : offset + limit]
    return PaginatedTagList(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
        source_state="legacy_fallback" if loaded_from_fallback else "canonical",
    )


@router.get(
    "/tags/summary",
    response_model=CandidateSummaryResponse,
    summary="Get Tag candidate summary",
    description="Return counts derived from existing local candidate evidence without exposing source content.",
    responses={
        503: {
            "model": APIError,
            "description": "The local Tag Book read model is temporarily unavailable.",
        }
    },
)
def tag_candidate_summary(
    summary: Annotated[DomainCandidateSummary, Depends(get_candidate_summary)],
) -> CandidateSummaryResponse:
    try:
        return adapt_candidate_summary(summary)
    except TagContractError:
        raise ReadModelUnavailable from None


@router.get(
    "/papers",
    response_model=PaginatedPaperList,
    summary="List papers",
    description=(
        "Return a deterministic page of paper summaries. `total` is calculated after the "
        "archive filter and before pagination; the default filter includes active papers only."
    ),
)
def list_papers(
    papers: Annotated[list[DomainPaperListItem], Depends(get_paper_list_items)],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of papers to return (1-100).")] = 20,
    offset: Annotated[int, Query(ge=0, description="Zero-based offset within the filtered collection.")] = 0,
    archive_status: Annotated[
        ArchiveStatus,
        Query(description="Archive filter: `active` excludes archived papers, `archived` returns only archived papers, and `all` returns both."),
    ] = ArchiveStatus.active,
) -> PaginatedPaperList:
    try:
        adapted = sorted(
            (adapt_paper_list_item(paper) for paper in papers),
            key=lambda paper: (paper.title.casefold(), paper.paper_id),
        )
    except PaperContractError:
        raise ReadModelUnavailable from None
    if archive_status is ArchiveStatus.active:
        matching = [paper for paper in adapted if not paper.archived]
    elif archive_status is ArchiveStatus.archived:
        matching = [paper for paper in adapted if paper.archived]
    else:
        matching = adapted
    total = len(matching)
    items = matching[offset : offset + limit]
    return PaginatedPaperList(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get(
    "/papers/{paper_id}",
    response_model=PaperDetail,
    summary="Get paper detail",
    description="Return one active or archived paper by its stable paper identity.",
    responses={
        404: {
            "model": APIError,
            "description": "No paper has the requested identity.",
            "content": {"application/json": {"example": {"detail": "Paper not found."}}},
        }
    },
)
def paper_detail(
    paper_id: Annotated[str, Path(min_length=1, description="Stable BluePrintReboot paper identity.")],
    paper: Annotated[DomainPaperDetail | None, Depends(get_paper_detail)],
) -> PaperDetail:
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    try:
        return adapt_paper_detail(paper)
    except PaperContractError:
        raise ReadModelUnavailable from None


@router.get(
    "/papers/{paper_id}/reader",
    response_model=ReaderSnapshotResponse,
    summary="Get read-only Reader snapshot",
    description="Return paper, PDF availability, and the exact persisted Reading Note in one coherent read-only response.",
    responses={
        404: {
            "model": APIError,
            "description": "No paper has the requested identity.",
            "content": {"application/json": {"example": {"detail": "Paper not found."}}},
        },
        503: {
            "model": APIError,
            "description": "The local Reader read model is temporarily unavailable.",
        },
    },
)
def reader_snapshot(
    paper_id: Annotated[str, Path(min_length=1, description="Stable BluePrintReboot paper identity.")],
    snapshot: Annotated[DomainReaderSnapshot | None, Depends(get_reader_snapshot)],
) -> ReaderSnapshotResponse:
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    try:
        return adapt_reader_snapshot(snapshot)
    except PaperContractError:
        raise ReadModelUnavailable from None


@router.patch(
    "/papers/{paper_id}/metadata",
    response_model=MetadataCommandResponse,
    summary="Save Reader paper metadata",
    description=(
        "Explicitly save the allowlisted bibliographic metadata fields when the supplied "
        "deterministic metadata revision still matches."
    ),
    responses={
        404: {"model": APIError, "description": "No paper has the requested identity."},
        409: {"model": APIError, "description": "The metadata revision is stale."},
        422: {"model": APIError, "description": "The request is invalid or contains an unsupported field."},
        503: {"model": APIError, "description": "The persistent command could not complete consistently."},
    },
)
def save_reader_metadata(
    request: MetadataCommandRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200, description="Stable BluePrintReboot paper identity.")],
    commands: Annotated[ReaderCommandService, Depends(get_reader_command_service)],
) -> MetadataCommandResponse:
    try:
        result = commands.save_metadata(
            paper_id,
            request.changes.model_dump(exclude_unset=True),
            request.expected_revision,
        )
    except ReaderCommandNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except ReaderCommandConflict:
        raise HTTPException(status_code=409, detail=COMMAND_CONFLICT_DETAIL) from None
    except ValueError:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except ReaderCommandUnavailable:
        raise HTTPException(status_code=503, detail=COMMAND_UNAVAILABLE_DETAIL) from None
    return MetadataCommandResponse(
        status=result.status,
        metadata=result.metadata,
        metadata_revision=result.metadata_revision,
        changed_fields=list(result.changed_fields),
        note_header_status=result.note_header_status,
        canonical_note_header=result.canonical_note_header,
        canonical_note_header_text=result.canonical_note_header_text,
        reading_note={
            "exists": result.reading_note.exists,
            "content": result.reading_note.content,
            "sha256": result.reading_note.sha256,
            "size_bytes": result.reading_note.size_bytes,
        },
    )


@router.put(
    "/papers/{paper_id}/reading-note",
    response_model=ReadingNoteCommandResponse,
    summary="Save Reader Reading Note",
    description=(
        "Explicitly save the complete Reading Note after canonicalizing its header against "
        "current paper metadata, provided the persisted SHA-256 baseline still matches."
    ),
    responses={
        404: {"model": APIError, "description": "No paper has the requested identity."},
        409: {"model": APIError, "description": "The persisted Reading Note hash is stale."},
        422: {"model": APIError, "description": "The request is invalid."},
        503: {"model": APIError, "description": "The persistent command could not complete consistently."},
    },
)
def save_reader_reading_note(
    request: ReadingNoteCommandRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200, description="Stable BluePrintReboot paper identity.")],
    commands: Annotated[ReaderCommandService, Depends(get_reader_command_service)],
) -> ReadingNoteCommandResponse:
    try:
        result = commands.save_reading_note(
            paper_id,
            request.content,
            request.expected_sha256,
        )
    except ReaderCommandNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except ReaderCommandConflict:
        raise HTTPException(status_code=409, detail=COMMAND_CONFLICT_DETAIL) from None
    except ReaderCommandUnavailable:
        raise HTTPException(status_code=503, detail=COMMAND_UNAVAILABLE_DETAIL) from None
    return ReadingNoteCommandResponse(
        status=result.status,
        content=result.content,
        sha256=result.sha256,
        size_bytes=result.size_bytes,
    )


@router.get(
    "/papers/{paper_id}/pdf",
    response_class=FileResponse,
    summary="Read managed paper PDF",
    description="Stream one indexed PDF from the canonical managed papers directory.",
    responses={
        200: {
            "description": "The managed PDF byte stream.",
            "content": {"application/pdf": {}},
        },
        404: {
            "model": APIError,
            "description": "The paper identity is unknown or its managed PDF is missing.",
        },
        409: {
            "model": APIError,
            "description": "The indexed path is not a safe managed PDF path.",
        },
        503: {
            "model": APIError,
            "description": "The managed PDF cannot currently be read.",
        },
    },
)
def paper_pdf(
    paper_id: Annotated[str, Path(min_length=1, description="Stable BluePrintReboot paper identity.")],
    pdf: Annotated[ManagedPdfResult, Depends(get_managed_pdf)],
) -> Response:
    if pdf.state is ManagedPdfState.unknown_paper:
        raise HTTPException(status_code=404, detail="Paper not found.")
    if pdf.state is ManagedPdfState.missing:
        raise HTTPException(status_code=404, detail=PDF_MISSING_DETAIL)
    if pdf.state is ManagedPdfState.invalid:
        raise HTTPException(status_code=409, detail=PDF_INVALID_DETAIL)
    if pdf.state is ManagedPdfState.unavailable:
        raise HTTPException(status_code=503, detail=PDF_UNAVAILABLE_DETAIL)
    if pdf.path is None or pdf.stat_result is None or not pdf.filename:
        raise HTTPException(status_code=503, detail=PDF_UNAVAILABLE_DETAIL)
    return FileResponse(
        pdf.path,
        media_type="application/pdf",
        filename=pdf.filename,
        stat_result=pdf.stat_result,
        content_disposition_type="inline",
    )
