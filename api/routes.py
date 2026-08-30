from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Response, UploadFile
from fastapi.responses import FileResponse

from api.adapters import (
    PaperContractError,
    NoteBlockContractError,
    ProjectContractError,
    SettingsContractError,
    TagContractError,
    FullTextContractError,
    adapt_full_text_document,
    adapt_full_text_status,
    adapt_candidate_review_queue_item,
    adapt_candidate_summary,
    adapt_canonical_tag,
    adapt_paper_detail,
    adapt_note_block_collection,
    adapt_note_block_command_result,
    adapt_note_block_link_command_result,
    adapt_paper_link_command_result,
    adapt_paper_list_item,
    adapt_project_command_result,
    adapt_project_detail,
    adapt_project_list_item,
    adapt_reader_snapshot,
    adapt_settings_summary,
)
from api.dependencies import (
    ReadModelUnavailable,
    get_candidate_review_queue,
    get_candidate_summary,
    get_canonical_tags,
    get_health_summary,
    get_full_text_service,
    get_library_status,
    get_metadata_enrichment_service,
    get_managed_pdf,
    get_note_block_collection,
    get_note_block_command_service,
    get_paper_detail,
    get_paper_list_items,
    get_paper_removal_service,
    get_pdf_scan_import_service,
    get_project_detail,
    get_project_command_service,
    get_project_list_items,
    get_reader_command_service,
    get_reader_snapshot,
    get_settings_summary,
    get_tag_candidate_review_service,
    get_tag_governance_service,
)
from api.pdf_files import ManagedPdfResult, ManagedPdfState
from api.schemas import (
    APIError,
    AddNoteBlockLinkRequest,
    AddPaperLinkRequest,
    ArchiveProjectRequest,
    ArchivePaperRequest,
    ArchivePaperResponse,
    ArchiveStatus,
    CandidateSummaryResponse,
    TagCandidateReviewQueueResponse,
    CanonicalTagAliasRequest,
    CanonicalTagCreateRequest,
    CanonicalTagDeprecateRequest,
    CanonicalTagGovernanceResponse,
    CanonicalTagGovernanceSnapshot,
    CanonicalTagUpdateRequest,
    HealthSummaryResponse,
    FullTextDocumentResponse,
    FullTextExtractionRequest,
    FullTextStatusResponse,
    LibraryStatusResponse,
    ManagedPdfImportRequest,
    ManagedPdfImportResponse,
    ManagedPdfReconnectRequest,
    ManagedPdfReconnectResponse,
    ManagedPdfScanResponse,
    RemoveManagedPdfRequest,
    RemoveManagedPdfResponse,
    MetadataCommandRequest,
    MetadataCommandResponse,
    MetadataEnrichmentPreviewRequest,
    MetadataEnrichmentPreviewResponse,
    PaperTagCommandRequest,
    PaperTagCommandResponse,
    TagCandidateApplyRequest,
    TagCandidateApplyResponse,
    TagCandidateCollectionResponse,
    TagCandidateGenerateRequest,
    TagCandidatePromoteRequest,
    TagCandidateReviewRequest,
    NoteBlockCollectionResponse,
    NoteBlockCommandResponse,
    NoteBlockLinkCommandResponse,
    PaginatedPaperList,
    PaginatedProjectList,
    PaginatedTagList,
    PaperDetail,
    PaperLinkCommandResponse,
    ProjectCommandResponse,
    CreateProjectRequest,
    RemovePaperLinkRequest,
    RemoveNoteBlockLinkRequest,
    ReadingNoteCommandRequest,
    ReadingNoteCommandResponse,
    ReadingStatusCommandRequest,
    ReadingStatusCommandResponse,
    ReaderSnapshotResponse,
    SettingsSummaryResponse,
    ProjectDetail,
    UpdateProjectRequest,
    CreateNoteBlockRequest,
    UpdateNoteBlockRequest,
)
from services.library_read_model import (
    HealthSummary,
    LibraryStatus,
    PaperDetail as DomainPaperDetail,
    PaperListItem as DomainPaperListItem,
    ReaderSnapshot as DomainReaderSnapshot,
    filter_paper_list_items,
)
from services.full_text_workflow import FullTextService, FullTextServiceUnavailable
from services.project_read_model import ProjectDetail as DomainProjectDetail, ProjectListItem as DomainProjectListItem
from services.note_block_read_model import NoteBlockCollection as DomainNoteBlockCollection
from services.note_block_commands import (
    NoteBlockCommandConflict,
    NoteBlockCommandInvalid,
    NoteBlockCommandNotFound,
    NoteBlockCommandService,
    NoteBlockCommandUnavailable,
)
from services.project_commands import (
    ProjectArchivedConflict,
    ProjectCommandConflict,
    ProjectCommandInvalid,
    ProjectCommandNotFound,
    ProjectCommandService,
    ProjectCommandUnavailable,
)
from services.reader_commands import ReaderCommandConflict, ReaderCommandNotFound, ReaderCommandService, ReaderCommandUnavailable
from services.metadata_enrichment import (
    MetadataEnrichmentNotFound,
    MetadataEnrichmentService,
    MetadataEnrichmentUnavailable,
)
from services.pdf_scan_import import (
    PdfReconnectConflict,
    PdfReconnectInvalid,
    PdfScanImportService,
    PdfScanImportUnavailable,
)
from services.paper_removal import (
    PaperRemovalConflict,
    PaperRemovalNotFound,
    PaperRemovalService,
    PaperRemovalUnavailable,
)
from services.settings_read_model import SettingsSummary as DomainSettingsSummary
from services.tag_read_model import CandidateReviewQueue as DomainCandidateReviewQueue, CandidateSummary as DomainCandidateSummary, CanonicalTag as DomainCanonicalTag
from services.tag_candidate_review import (
    CandidateCollection,
    TagCandidateReviewConflict,
    TagCandidateReviewInvalid,
    TagCandidateReviewNotFound,
    TagCandidateReviewService,
    TagCandidateReviewUnavailable,
)
from services.tag_governance import (
    CanonicalTagGovernanceService,
    TagGovernanceConflict,
    TagGovernanceInvalid,
    TagGovernanceNotFound,
    TagGovernanceUnavailable,
)


router = APIRouter()

PDF_MISSING_DETAIL = "Managed PDF not found."
PDF_INVALID_DETAIL = "Managed PDF path is invalid."
PDF_UNAVAILABLE_DETAIL = "Managed PDF is temporarily unavailable."
COMMAND_CONFLICT_DETAIL = "The saved Reader state changed. Reload the current version before retrying."
COMMAND_UNAVAILABLE_DETAIL = "The Reader command could not be completed."
METADATA_ENRICHMENT_UNAVAILABLE_DETAIL = "Metadata enrichment could not be completed."
COMMAND_INVALID_DETAIL = "Request validation failed."
PROJECT_COMMAND_CONFLICT_DETAIL = "The saved Project state changed. Reload the current version before retrying."
PROJECT_ARCHIVED_DETAIL = "Archived Projects do not allow this command."
PROJECT_COMMAND_UNAVAILABLE_DETAIL = "The Project command could not be completed."
PROJECT_COMMAND_NOT_FOUND_DETAIL = "The requested Project, Paper, or Paper link was not found."
NOTE_BLOCK_COMMAND_CONFLICT_DETAIL = "The saved Note Block collection changed. Reload the current collection before retrying."
NOTE_BLOCK_COMMAND_UNAVAILABLE_DETAIL = "The Note Block command could not be completed."
NOTE_BLOCK_COMMAND_NOT_FOUND_DETAIL = "The requested Paper or Note Block was not found."
PDF_SCAN_IMPORT_UNAVAILABLE_DETAIL = "The managed PDF scan or import could not be completed."
PAPER_REMOVAL_UNAVAILABLE_DETAIL = "The requested Paper removal could not be completed safely."
TAG_GOVERNANCE_CONFLICT_DETAIL = "The canonical Tag Book changed. Reload the current registry before retrying."
TAG_GOVERNANCE_UNAVAILABLE_DETAIL = "The canonical Tag Book command could not be completed."
TAG_CANDIDATE_CONFLICT_DETAIL = "The candidate review or Paper tags changed. Reload the current candidate review before retrying."
TAG_CANDIDATE_UNAVAILABLE_DETAIL = "The tag candidate review command could not be completed."
FULL_TEXT_UNAVAILABLE_DETAIL = "The full-text extraction state could not be read or updated safely."


def _candidate_collection_response(collection: CandidateCollection) -> TagCandidateCollectionResponse:
    return TagCandidateCollectionResponse(
        paper_id=collection.paper_id,
        review_revision=collection.review_revision,
        tags_revision=collection.tags_revision,
        state=collection.state,
        items=list(collection.items),
    )


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


@router.post(
    "/projects",
    response_model=ProjectCommandResponse,
    summary="Create Project",
    description="Explicitly create one Project with a server-generated stable identity.",
    responses={
        422: {"model": APIError, "description": "The Project fields are invalid."},
        503: {"model": APIError, "description": "The Project could not be persisted consistently."},
    },
)
def create_project(
    request: CreateProjectRequest,
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> ProjectCommandResponse:
    try:
        result = commands.create_project(
            name=request.name,
            description=request.description,
            status=request.status,
            priority=request.priority,
            tags=request.tags,
        )
        return adapt_project_command_result(result)
    except ProjectCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


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


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectCommandResponse,
    summary="Update Project",
    description="Explicitly update allowlisted Project metadata when its revision still matches.",
    responses={
        404: {"model": APIError, "description": "The Project identity is unknown."},
        409: {"model": APIError, "description": "The Project is stale or archived."},
        422: {"model": APIError, "description": "The Project fields are invalid or unsupported."},
        503: {"model": APIError, "description": "The Project could not be persisted consistently."},
    },
)
def update_project(
    request: UpdateProjectRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> ProjectCommandResponse:
    try:
        result = commands.update_project(
            project_id,
            request.changes.model_dump(exclude_unset=True),
            request.expected_revision,
        )
        return adapt_project_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(status_code=404, detail="Project not found.") from None
    except ProjectArchivedConflict:
        raise HTTPException(status_code=409, detail=PROJECT_ARCHIVED_DETAIL) from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except ProjectCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/projects/{project_id}/archive",
    response_model=ProjectCommandResponse,
    summary="Archive Project",
    description="Explicitly archive one Project without deleting it or any linked data.",
    responses={
        404: {"model": APIError, "description": "The Project identity is unknown."},
        409: {"model": APIError, "description": "The Project revision is stale."},
        422: {"model": APIError, "description": "The archive request is invalid."},
        503: {"model": APIError, "description": "The Project could not be archived consistently."},
    },
)
def archive_project(
    request: ArchiveProjectRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> ProjectCommandResponse:
    try:
        result = commands.archive_project(project_id, request.expected_revision)
        return adapt_project_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(status_code=404, detail="Project not found.") from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/projects/{project_id}/paper-links",
    response_model=PaperLinkCommandResponse,
    summary="Add Paper link to Project",
    description="Explicitly add one existing Paper with one allowlisted link type.",
    responses={
        404: {"model": APIError, "description": "The Project or Paper is unknown."},
        409: {"model": APIError, "description": "The link collection is stale or the Project is archived."},
        422: {"model": APIError, "description": "The Paper-link request is invalid."},
        503: {"model": APIError, "description": "The Paper link could not be persisted consistently."},
    },
)
def add_project_paper_link(
    request: AddPaperLinkRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> PaperLinkCommandResponse:
    try:
        result = commands.add_paper_link(
            project_id,
            paper_id=request.paper_id,
            link_type=request.link_type,
            expected_links_revision=request.expected_links_revision,
        )
        return adapt_paper_link_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(
            status_code=404,
            detail=PROJECT_COMMAND_NOT_FOUND_DETAIL,
        ) from None
    except ProjectArchivedConflict:
        raise HTTPException(status_code=409, detail=PROJECT_ARCHIVED_DETAIL) from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except ProjectCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


@router.delete(
    "/projects/{project_id}/paper-links/{link_id}",
    response_model=PaperLinkCommandResponse,
    summary="Remove Paper link from Project",
    description="Explicitly remove one exact Paper link without changing the Paper or Project.",
    responses={
        404: {"model": APIError, "description": "The Project or exact Paper link is unknown."},
        409: {"model": APIError, "description": "The Project link collection is stale."},
        422: {"model": APIError, "description": "The unlink request is invalid."},
        503: {"model": APIError, "description": "The Paper link could not be removed consistently."},
    },
)
def remove_project_paper_link(
    request: RemovePaperLinkRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    link_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> PaperLinkCommandResponse:
    try:
        result = commands.remove_paper_link(
            project_id,
            link_id,
            expected_links_revision=request.expected_links_revision,
        )
        return adapt_paper_link_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(
            status_code=404,
            detail=PROJECT_COMMAND_NOT_FOUND_DETAIL,
        ) from None
    except ProjectArchivedConflict:
        raise HTTPException(status_code=409, detail=PROJECT_ARCHIVED_DETAIL) from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/projects/{project_id}/note-block-links",
    response_model=NoteBlockLinkCommandResponse,
    summary="Add Note Block link to Project",
    description="Explicitly link one existing Paper-owned Note Block to one writable Project.",
    responses={
        404: {"model": APIError, "description": "The Project, Paper, or Note Block is unknown."},
        409: {"model": APIError, "description": "The link collection is stale or the Project is archived."},
        422: {"model": APIError, "description": "The Note Block link request is invalid."},
        503: {"model": APIError, "description": "The Note Block link could not be persisted consistently."},
    },
)
def add_project_note_block_link(
    request: AddNoteBlockLinkRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> NoteBlockLinkCommandResponse:
    try:
        result = commands.add_note_block_link(
            project_id,
            paper_id=request.paper_id,
            note_block_id=request.note_block_id,
            link_type=request.link_type,
            expected_links_revision=request.expected_links_revision,
        )
        return adapt_note_block_link_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(
            status_code=404,
            detail=PROJECT_COMMAND_NOT_FOUND_DETAIL,
        ) from None
    except ProjectArchivedConflict:
        raise HTTPException(status_code=409, detail=PROJECT_ARCHIVED_DETAIL) from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except ProjectCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


@router.delete(
    "/projects/{project_id}/note-block-links/{link_id}",
    response_model=NoteBlockLinkCommandResponse,
    summary="Remove Note Block link from Project",
    description="Explicitly remove one exact Note Block link without changing its Project, Paper, or Note Block.",
    responses={
        404: {"model": APIError, "description": "The Project or exact Note Block link is unknown."},
        409: {"model": APIError, "description": "The Project link collection is stale or archived."},
        422: {"model": APIError, "description": "The unlink request is invalid."},
        503: {"model": APIError, "description": "The Note Block link could not be removed consistently."},
    },
)
def remove_project_note_block_link(
    request: RemoveNoteBlockLinkRequest,
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    link_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ProjectCommandService, Depends(get_project_command_service)],
) -> NoteBlockLinkCommandResponse:
    try:
        result = commands.remove_note_block_link(
            project_id,
            link_id,
            expected_links_revision=request.expected_links_revision,
        )
        return adapt_note_block_link_command_result(result)
    except ProjectCommandNotFound:
        raise HTTPException(
            status_code=404,
            detail=PROJECT_COMMAND_NOT_FOUND_DETAIL,
        ) from None
    except ProjectArchivedConflict:
        raise HTTPException(status_code=409, detail=PROJECT_ARCHIVED_DETAIL) from None
    except ProjectCommandConflict:
        raise HTTPException(
            status_code=409,
            detail=PROJECT_COMMAND_CONFLICT_DETAIL,
        ) from None
    except (ProjectCommandUnavailable, ProjectContractError):
        raise HTTPException(
            status_code=503,
            detail=PROJECT_COMMAND_UNAVAILABLE_DETAIL,
        ) from None


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
    "/tags/review-queue",
    response_model=TagCandidateReviewQueueResponse,
    summary="List Papers with reviewable tag candidates",
    description="Return a bounded queue from persisted candidate reviews. This read never generates or applies candidates.",
    responses={503: {"model": APIError, "description": "The local tag review queue is temporarily unavailable."}},
)
def tag_candidate_review_queue(
    queue: Annotated[DomainCandidateReviewQueue, Depends(get_candidate_review_queue)],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum Papers to return (1-100).")]=50,
    offset: Annotated[int, Query(ge=0, description="Zero-based queue offset.")]=0,
) -> TagCandidateReviewQueueResponse:
    try:
        adapted = [adapt_candidate_review_queue_item(item) for item in queue["items"]]
    except (KeyError, TagContractError):
        raise ReadModelUnavailable from None
    total = len(adapted)
    items = adapted[offset : offset + limit]
    return TagCandidateReviewQueueResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get(
    "/tags/governance",
    response_model=CanonicalTagGovernanceSnapshot,
    summary="Read the mutable canonical Tag Book registry",
    description="Return canonical tag metadata and the deterministic revision required by explicit governance commands.",
)
def tag_governance_snapshot(
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceSnapshot:
    try:
        items, revision = commands.snapshot()
        return CanonicalTagGovernanceSnapshot(items=items, registry_revision=revision)
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/tags",
    response_model=CanonicalTagGovernanceResponse,
    summary="Create a canonical tag",
    description="Explicitly create one active canonical Tag Book entry without changing any stored Paper tag references.",
)
def create_canonical_tag(
    request: CanonicalTagCreateRequest,
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceResponse:
    try:
        result = commands.create_tag(
            label=request.label,
            category=request.category,
            description=request.description,
            suggestion_strength=request.suggestion_strength,
            expected_revision=request.expected_revision,
        )
        return CanonicalTagGovernanceResponse(
            status=result.status,
            tag=result.tag,
            registry_revision=result.registry_revision,
        )
    except TagGovernanceConflict:
        raise HTTPException(status_code=409, detail=TAG_GOVERNANCE_CONFLICT_DETAIL) from None
    except TagGovernanceInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.patch(
    "/tags/{canonical_key}",
    response_model=CanonicalTagGovernanceResponse,
    summary="Edit canonical tag metadata",
    description="Explicitly update bounded canonical tag metadata; canonical identities and historical Paper references are preserved.",
)
def update_canonical_tag(
    request: CanonicalTagUpdateRequest,
    canonical_key: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceResponse:
    try:
        result = commands.update_tag(
            canonical_key,
            changes=request.changes.model_dump(exclude_unset=True),
            expected_revision=request.expected_revision,
        )
        return CanonicalTagGovernanceResponse(
            status=result.status,
            tag=result.tag,
            registry_revision=result.registry_revision,
        )
    except TagGovernanceNotFound:
        raise HTTPException(status_code=404, detail="Canonical tag not found.") from None
    except TagGovernanceConflict:
        raise HTTPException(status_code=409, detail=TAG_GOVERNANCE_CONFLICT_DETAIL) from None
    except TagGovernanceInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/tags/{canonical_key}/aliases",
    response_model=CanonicalTagGovernanceResponse,
    summary="Add a canonical tag alias",
    description="Add one unique alias that predictably resolves to the requested canonical tag without rewriting Paper tags.",
)
def add_canonical_tag_alias(
    request: CanonicalTagAliasRequest,
    canonical_key: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceResponse:
    try:
        result = commands.add_alias(
            canonical_key,
            alias=request.alias,
            expected_revision=request.expected_revision,
        )
        return CanonicalTagGovernanceResponse(status=result.status, tag=result.tag, registry_revision=result.registry_revision)
    except TagGovernanceNotFound:
        raise HTTPException(status_code=404, detail="Canonical tag not found.") from None
    except TagGovernanceConflict:
        raise HTTPException(status_code=409, detail=TAG_GOVERNANCE_CONFLICT_DETAIL) from None
    except TagGovernanceInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.delete(
    "/tags/{canonical_key}/aliases",
    response_model=CanonicalTagGovernanceResponse,
    summary="Remove a canonical tag alias",
    description="Remove one alias from the registry only; Paper values are never rewritten or deleted.",
)
def remove_canonical_tag_alias(
    request: CanonicalTagAliasRequest,
    canonical_key: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceResponse:
    try:
        result = commands.remove_alias(
            canonical_key,
            alias=request.alias,
            expected_revision=request.expected_revision,
        )
        return CanonicalTagGovernanceResponse(status=result.status, tag=result.tag, registry_revision=result.registry_revision)
    except TagGovernanceNotFound:
        raise HTTPException(status_code=404, detail="Canonical tag or alias not found.") from None
    except TagGovernanceConflict:
        raise HTTPException(status_code=409, detail=TAG_GOVERNANCE_CONFLICT_DETAIL) from None
    except TagGovernanceInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/tags/{canonical_key}/deprecate",
    response_model=CanonicalTagGovernanceResponse,
    summary="Deprecate a canonical tag",
    description="Mark a canonical tag deprecated while retaining the registry record and all historical Paper references.",
)
def deprecate_canonical_tag(
    request: CanonicalTagDeprecateRequest,
    canonical_key: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[CanonicalTagGovernanceService, Depends(get_tag_governance_service)],
) -> CanonicalTagGovernanceResponse:
    try:
        result = commands.deprecate_tag(canonical_key, expected_revision=request.expected_revision)
        return CanonicalTagGovernanceResponse(status=result.status, tag=result.tag, registry_revision=result.registry_revision)
    except TagGovernanceNotFound:
        raise HTTPException(status_code=404, detail="Canonical tag not found.") from None
    except TagGovernanceConflict:
        raise HTTPException(status_code=409, detail=TAG_GOVERNANCE_CONFLICT_DETAIL) from None
    except TagGovernanceInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagGovernanceUnavailable:
        raise HTTPException(status_code=503, detail=TAG_GOVERNANCE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/scan",
    response_model=ManagedPdfScanResponse,
    summary="Preview managed PDF scan",
    description=(
        "Discover PDFs already placed in the managed papers directory without creating "
        "or changing any Paper record."
    ),
    responses={
        503: {"model": APIError, "description": "The managed PDF scan could not be completed."},
    },
)
def scan_managed_pdfs(
    commands: Annotated[PdfScanImportService, Depends(get_pdf_scan_import_service)],
) -> ManagedPdfScanResponse:
    try:
        return ManagedPdfScanResponse.model_validate(commands.scan())
    except PdfScanImportUnavailable:
        raise HTTPException(status_code=503, detail=PDF_SCAN_IMPORT_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/import",
    response_model=ManagedPdfImportResponse,
    summary="Register selected managed PDFs",
    description=(
        "Revalidate and register only selected new PDFs from the managed papers directory. "
        "This command does not enrich metadata or create tags."
    ),
    responses={
        422: {"model": APIError, "description": "The managed PDF selection is invalid."},
        503: {"model": APIError, "description": "The managed PDF import could not be completed."},
    },
)
def import_managed_pdfs(
    request: ManagedPdfImportRequest,
    commands: Annotated[PdfScanImportService, Depends(get_pdf_scan_import_service)],
) -> ManagedPdfImportResponse:
    try:
        return ManagedPdfImportResponse.model_validate(commands.import_selected(request.relative_paths))
    except PdfScanImportUnavailable:
        raise HTTPException(status_code=503, detail=PDF_SCAN_IMPORT_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/upload",
    response_model=ManagedPdfImportResponse,
    summary="Upload and register managed PDFs",
    description=(
        "Accept explicit PDF uploads only, stage them in the managed library, and route "
        "them through the same duplicate-safe registration path as managed-directory imports."
    ),
    responses={
        422: {"model": APIError, "description": "The uploaded PDF selection is invalid."},
        503: {"model": APIError, "description": "The managed PDF upload could not be completed."},
    },
)
async def upload_managed_pdfs(
    files: Annotated[list[UploadFile], File(...)],
    commands: Annotated[PdfScanImportService, Depends(get_pdf_scan_import_service)],
) -> ManagedPdfImportResponse:
    try:
        pairs = [(str(upload.filename or ""), upload.file) for upload in files]
        return ManagedPdfImportResponse.model_validate(commands.import_uploaded(pairs))
    except PdfReconnectInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except PdfScanImportUnavailable:
        raise HTTPException(status_code=503, detail=PDF_SCAN_IMPORT_UNAVAILABLE_DETAIL) from None
    finally:
        for upload in files:
            await upload.close()


@router.post(
    "/papers/reconnect",
    response_model=ManagedPdfReconnectResponse,
    summary="Reconnect a missing Paper to an exact managed PDF",
    description=(
        "Explicitly reconnect one missing indexed Paper to one managed-relative PDF only "
        "when its SHA-256 identity remains an unambiguous exact match."
    ),
    responses={
        409: {"model": APIError, "description": "The reconnect candidate changed or is ambiguous."},
        422: {"model": APIError, "description": "The reconnect request is invalid."},
        503: {"model": APIError, "description": "The reconnect could not be persisted consistently."},
    },
)
def reconnect_managed_pdf(
    request: ManagedPdfReconnectRequest,
    commands: Annotated[PdfScanImportService, Depends(get_pdf_scan_import_service)],
) -> ManagedPdfReconnectResponse:
    try:
        return ManagedPdfReconnectResponse.model_validate(
            commands.reconnect(
                paper_id=request.paper_id,
                relative_path=request.relative_path,
            )
        )
    except PdfReconnectConflict:
        raise HTTPException(status_code=409, detail="The reconnect candidate changed or is no longer uniquely safe. Scan again before retrying.") from None
    except PdfReconnectInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except PdfScanImportUnavailable:
        raise HTTPException(status_code=503, detail=PDF_SCAN_IMPORT_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/remove-pdf",
    response_model=RemoveManagedPdfResponse,
    summary="Remove managed PDF bytes with recovery copy",
    description=(
        "Explicitly remove only the managed PDF bytes after a verified recovery copy. "
        "Paper metadata, notes, Note Blocks, Tags, and Project links are preserved."
    ),
)
def remove_managed_pdf(
    request: RemoveManagedPdfRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    removals: Annotated[PaperRemovalService, Depends(get_paper_removal_service)],
) -> RemoveManagedPdfResponse:
    try:
        result = removals.remove_managed_pdf(paper_id, request.expected_pdf_revision)
    except PaperRemovalNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except PaperRemovalConflict:
        raise HTTPException(status_code=409, detail="The managed PDF changed. Reload the Paper before retrying.") from None
    except PaperRemovalUnavailable:
        raise HTTPException(status_code=503, detail=PAPER_REMOVAL_UNAVAILABLE_DETAIL) from None
    return RemoveManagedPdfResponse(**result.__dict__)


@router.post(
    "/papers/{paper_id}/archive",
    response_model=ArchivePaperResponse,
    summary="Archive Paper from active Library",
    description=(
        "Explicitly remove a Paper from active Library views without deleting its metadata, "
        "managed PDF, Reading Note, Note Blocks, Tags, or Project links."
    ),
)
def archive_paper(
    request: ArchivePaperRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    removals: Annotated[PaperRemovalService, Depends(get_paper_removal_service)],
) -> ArchivePaperResponse:
    try:
        result = removals.archive_paper(paper_id, request.expected_lifecycle_revision)
    except PaperRemovalNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except PaperRemovalConflict:
        raise HTTPException(status_code=409, detail="The Paper lifecycle changed. Reload the Paper before retrying.") from None
    except PaperRemovalUnavailable:
        raise HTTPException(status_code=503, detail=PAPER_REMOVAL_UNAVAILABLE_DETAIL) from None
    return ArchivePaperResponse(**result.__dict__)


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
    q: Annotated[str, Query(max_length=200, description="Case-insensitive bounded metadata search.")] = "",
    tag: Annotated[str, Query(max_length=100, description="Exact case-insensitive Paper tag filter.")] = "",
    year: Annotated[str, Query(pattern=r"^$|^[0-9]{4}$", description="Exact four-digit publication year filter.")] = "",
    status: Annotated[str, Query(max_length=100, description="Exact case-insensitive reading-status filter.")] = "",
) -> PaginatedPaperList:
    try:
        filtered = filter_paper_list_items(papers, q=q, tag=tag, year=year, status=status)
        adapted = sorted(
            (adapt_paper_list_item(paper) for paper in filtered),
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


@router.get(
    "/papers/{paper_id}/full-text/status",
    response_model=FullTextStatusResponse,
    summary="Get full-text extraction status",
    description="Return bounded cache, provider, classification, and OCR-needed state without exposing storage paths or source hashes.",
)
def full_text_status(
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    service: Annotated[FullTextService, Depends(get_full_text_service)],
) -> FullTextStatusResponse:
    try:
        status = service.status(paper_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        return adapt_full_text_status(status)
    except FullTextServiceUnavailable:
        raise HTTPException(status_code=503, detail=FULL_TEXT_UNAVAILABLE_DETAIL) from None
    except FullTextContractError:
        raise ReadModelUnavailable from None


@router.get(
    "/papers/{paper_id}/full-text",
    response_model=FullTextDocumentResponse,
    summary="Get canonical cached full text",
    description="Return the canonical cached Markdown or plain-text projection and its bounded extraction state.",
)
def full_text_document(
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    service: Annotated[FullTextService, Depends(get_full_text_service)],
) -> FullTextDocumentResponse:
    try:
        document = service.document(paper_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        return adapt_full_text_document(document)
    except FullTextServiceUnavailable:
        raise HTTPException(status_code=503, detail=FULL_TEXT_UNAVAILABLE_DETAIL) from None
    except FullTextContractError:
        raise ReadModelUnavailable from None


@router.post(
    "/papers/{paper_id}/full-text/extract",
    response_model=FullTextDocumentResponse,
    summary="Explicitly extract full text",
    description="Run the canonical local extraction workflow now. This command is never scheduled automatically.",
)
def extract_full_text(
    request: FullTextExtractionRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    service: Annotated[FullTextService, Depends(get_full_text_service)],
) -> FullTextDocumentResponse:
    try:
        document = service.extract(paper_id, force=request.force)
        if document is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        return adapt_full_text_document(document)
    except FullTextServiceUnavailable:
        raise HTTPException(status_code=503, detail=FULL_TEXT_UNAVAILABLE_DETAIL) from None
    except FullTextContractError:
        raise HTTPException(status_code=503, detail=FULL_TEXT_UNAVAILABLE_DETAIL) from None


@router.get(
    "/papers/{paper_id}/note-blocks",
    response_model=NoteBlockCollectionResponse,
    summary="List structured Note Blocks",
    description="Return the complete bounded stored-order Note Block collection and its deterministic revision.",
    responses={
        404: {"model": APIError, "description": "No Paper has the requested identity."},
        503: {"model": APIError, "description": "The Note Block storage is corrupt or unavailable."},
    },
)
def note_block_collection(
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    collection: Annotated[DomainNoteBlockCollection | None, Depends(get_note_block_collection)],
) -> NoteBlockCollectionResponse:
    if collection is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    try:
        return adapt_note_block_collection(collection)
    except NoteBlockContractError:
        raise ReadModelUnavailable from None


@router.post(
    "/papers/{paper_id}/note-blocks",
    response_model=NoteBlockCommandResponse,
    summary="Create structured Note Block",
    description="Explicitly create one server-owned Note Block at the top of the stored collection when its complete revision matches.",
    responses={
        404: {"model": APIError, "description": "The Paper identity is unknown."},
        409: {"model": APIError, "description": "The Note Block collection revision is stale."},
        422: {"model": APIError, "description": "The Note Block fields are invalid or unsupported."},
        503: {"model": APIError, "description": "The Note Block could not be persisted consistently."},
    },
)
def create_note_block(
    request: CreateNoteBlockRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[NoteBlockCommandService, Depends(get_note_block_command_service)],
) -> NoteBlockCommandResponse:
    try:
        content = request.model_dump(exclude={"expected_revision"})
        result = commands.create_note_block(
            paper_id,
            content,
            request.expected_revision,
        )
        return adapt_note_block_command_result(result)
    except NoteBlockCommandNotFound:
        raise HTTPException(status_code=404, detail=NOTE_BLOCK_COMMAND_NOT_FOUND_DETAIL) from None
    except NoteBlockCommandConflict:
        raise HTTPException(status_code=409, detail=NOTE_BLOCK_COMMAND_CONFLICT_DETAIL) from None
    except NoteBlockCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (NoteBlockCommandUnavailable, NoteBlockContractError):
        raise HTTPException(status_code=503, detail=NOTE_BLOCK_COMMAND_UNAVAILABLE_DETAIL) from None


@router.patch(
    "/papers/{paper_id}/note-blocks/{block_id}",
    response_model=NoteBlockCommandResponse,
    summary="Update structured Note Block",
    description="Explicitly update allowlisted Note Block content when the complete collection revision matches.",
    responses={
        404: {"model": APIError, "description": "The Paper or Note Block identity is unknown."},
        409: {"model": APIError, "description": "The Note Block collection revision is stale."},
        422: {"model": APIError, "description": "The Note Block changes are invalid or unsupported."},
        503: {"model": APIError, "description": "The Note Block could not be persisted consistently."},
    },
)
def update_note_block(
    request: UpdateNoteBlockRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    block_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[NoteBlockCommandService, Depends(get_note_block_command_service)],
) -> NoteBlockCommandResponse:
    try:
        result = commands.update_note_block(
            paper_id,
            block_id,
            request.changes.model_dump(exclude_unset=True),
            request.expected_revision,
        )
        return adapt_note_block_command_result(result)
    except NoteBlockCommandNotFound:
        raise HTTPException(status_code=404, detail=NOTE_BLOCK_COMMAND_NOT_FOUND_DETAIL) from None
    except NoteBlockCommandConflict:
        raise HTTPException(status_code=409, detail=NOTE_BLOCK_COMMAND_CONFLICT_DETAIL) from None
    except NoteBlockCommandInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except (NoteBlockCommandUnavailable, NoteBlockContractError):
        raise HTTPException(status_code=503, detail=NOTE_BLOCK_COMMAND_UNAVAILABLE_DETAIL) from None


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


@router.patch(
    "/papers/{paper_id}/reading-status",
    response_model=ReadingStatusCommandResponse,
    summary="Save Paper reading status",
    description="Explicitly save one existing reading state when its narrow status revision still matches.",
)
def save_reading_status(
    request: ReadingStatusCommandRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[ReaderCommandService, Depends(get_reader_command_service)],
) -> ReadingStatusCommandResponse:
    try:
        result = commands.save_reading_status(
            paper_id,
            request.reading_status,
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
    return ReadingStatusCommandResponse(
        status=result.status,
        reading_status=result.reading_status,
        reading_status_revision=result.reading_status_revision,
    )


@router.post(
    "/papers/{paper_id}/metadata/enrichment-preview",
    response_model=MetadataEnrichmentPreviewResponse,
    summary="Fetch non-persistent metadata enrichment candidates",
    description=(
        "Explicitly retrieve Crossref and existing local/arXiv fallback candidate metadata "
        "for comparison only. This operation never writes Paper metadata; selected values "
        "must be saved separately through the Reader metadata command."
    ),
    responses={
        404: {"model": APIError, "description": "No paper has the requested identity."},
        422: {"model": APIError, "description": "The enrichment request is invalid."},
        503: {"model": APIError, "description": "The preview could not be completed."},
    },
)
def preview_metadata_enrichment(
    _request: MetadataEnrichmentPreviewRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200, description="Stable BluePrintReboot paper identity.")],
    enrichment: Annotated[MetadataEnrichmentService, Depends(get_metadata_enrichment_service)],
) -> MetadataEnrichmentPreviewResponse:
    try:
        preview = enrichment.preview(paper_id)
    except MetadataEnrichmentNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except MetadataEnrichmentUnavailable:
        raise HTTPException(status_code=503, detail=METADATA_ENRICHMENT_UNAVAILABLE_DETAIL) from None
    return MetadataEnrichmentPreviewResponse(
        paper_id=preview.paper_id,
        metadata_revision=preview.metadata_revision,
        candidate_sources=list(preview.candidate_sources),
        fields=[
            {
                "field": field.field,
                "current_value": field.current_value,
                "candidate_value": field.candidate_value,
                "source": field.source,
                "state": field.state,
            }
            for field in preview.fields
        ],
        diagnostics=list(preview.diagnostics),
    )


@router.get(
    "/papers/{paper_id}/tag-candidates",
    response_model=TagCandidateCollectionResponse,
    summary="Get persisted tag candidate review",
    description="Return the current per-Paper candidate review context. Reading it never generates candidates or changes Paper tags.",
)
def get_tag_candidates(
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateCollectionResponse:
    try:
        return _candidate_collection_response(commands.collection(paper_id))
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper or candidate review not found.") from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tag-candidates/generate",
    response_model=TagCandidateCollectionResponse,
    summary="Generate tag candidates for review",
    description="Generate and persist an explicit review context from existing local candidate evidence. This command never applies a Paper tag.",
)
def generate_tag_candidates(
    request: TagCandidateGenerateRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateCollectionResponse:
    try:
        return _candidate_collection_response(
            commands.generate(paper_id, reset_rejections=request.reset_rejections)
        )
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper not found.") from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tag-candidates/{candidate_id}/approve",
    response_model=TagCandidateCollectionResponse,
    summary="Approve a resolved tag candidate",
    description="Record explicit review approval only. Approval does not apply the tag to the Paper.",
)
def approve_tag_candidate(
    request: TagCandidateReviewRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    candidate_id: Annotated[str, Path(min_length=64, max_length=64)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateCollectionResponse:
    try:
        return _candidate_collection_response(
            commands.approve(
                paper_id,
                candidate_id,
                expected_review_revision=request.expected_review_revision,
            )
        )
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper or candidate review not found.") from None
    except TagCandidateReviewConflict:
        raise HTTPException(status_code=409, detail=TAG_CANDIDATE_CONFLICT_DETAIL) from None
    except TagCandidateReviewInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tag-candidates/{candidate_id}/reject",
    response_model=TagCandidateCollectionResponse,
    summary="Reject a tag candidate",
    description="Persist an explicit rejection. Rejected candidates remain excluded from normal review until explicitly regenerated with reset enabled.",
)
def reject_tag_candidate(
    request: TagCandidateReviewRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    candidate_id: Annotated[str, Path(min_length=64, max_length=64)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateCollectionResponse:
    try:
        return _candidate_collection_response(
            commands.reject(
                paper_id,
                candidate_id,
                expected_review_revision=request.expected_review_revision,
            )
        )
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper or candidate review not found.") from None
    except TagCandidateReviewConflict:
        raise HTTPException(status_code=409, detail=TAG_CANDIDATE_CONFLICT_DETAIL) from None
    except TagCandidateReviewInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tag-candidates/{candidate_id}/promote",
    response_model=TagCandidateCollectionResponse,
    summary="Promote a candidate to a canonical tag",
    description="Create or resolve one active canonical tag through the Tag Book, preserving the candidate review context without changing Paper tags.",
)
def promote_tag_candidate(
    request: TagCandidatePromoteRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    candidate_id: Annotated[str, Path(min_length=64, max_length=64)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateCollectionResponse:
    try:
        return _candidate_collection_response(
            commands.promote(
                paper_id,
                candidate_id,
                expected_review_revision=request.expected_review_revision,
                label=request.label,
                category=request.category,
            )
        )
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper or candidate review not found.") from None
    except TagCandidateReviewConflict:
        raise HTTPException(status_code=409, detail=TAG_CANDIDATE_CONFLICT_DETAIL) from None
    except TagCandidateReviewInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tag-candidates/{candidate_id}/apply",
    response_model=TagCandidateApplyResponse,
    summary="Apply an approved or resolved tag candidate to a Paper",
    description="Explicitly apply the active canonical tag through the existing Paper tag command path. Candidate generation and approval alone never perform this mutation.",
)
def apply_tag_candidate(
    request: TagCandidateApplyRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200)],
    candidate_id: Annotated[str, Path(min_length=64, max_length=64)],
    commands: Annotated[TagCandidateReviewService, Depends(get_tag_candidate_review_service)],
) -> TagCandidateApplyResponse:
    try:
        result = commands.apply(
            paper_id,
            candidate_id,
            expected_review_revision=request.expected_review_revision,
            expected_tags_revision=request.expected_tags_revision,
        )
        paper_tag = result.paper_tag_result
        return TagCandidateApplyResponse(
            candidate=result.candidate,
            review_revision=result.review_revision,
            paper_tag={
                "status": paper_tag.status,
                "tags": list(paper_tag.tags),
                "tags_revision": paper_tag.tags_revision,
                "note_header_status": paper_tag.note_header_status,
                "canonical_note_header": paper_tag.canonical_note_header,
                "canonical_note_header_text": paper_tag.canonical_note_header_text,
                "reading_note": {
                    "exists": paper_tag.reading_note.exists,
                    "content": paper_tag.reading_note.content,
                    "sha256": paper_tag.reading_note.sha256,
                    "size_bytes": paper_tag.reading_note.size_bytes,
                },
            },
        )
    except TagCandidateReviewNotFound:
        raise HTTPException(status_code=404, detail="Paper or candidate review not found.") from None
    except TagCandidateReviewConflict:
        raise HTTPException(status_code=409, detail=TAG_CANDIDATE_CONFLICT_DETAIL) from None
    except TagCandidateReviewInvalid:
        raise HTTPException(status_code=422, detail=COMMAND_INVALID_DETAIL) from None
    except TagCandidateReviewUnavailable:
        raise HTTPException(status_code=503, detail=TAG_CANDIDATE_UNAVAILABLE_DETAIL) from None


@router.post(
    "/papers/{paper_id}/tags",
    response_model=PaperTagCommandResponse,
    summary="Add one Paper tag",
    description=(
        "Explicitly add one normalized Paper tag when the supplied deterministic "
        "tag revision still matches."
    ),
    responses={
        404: {"model": APIError, "description": "No paper has the requested identity."},
        409: {"model": APIError, "description": "The Paper tag revision is stale."},
        422: {"model": APIError, "description": "The requested tag is invalid."},
        503: {"model": APIError, "description": "The persistent command could not complete consistently."},
    },
)
def add_paper_tag(
    request: PaperTagCommandRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200, description="Stable BluePrintReboot paper identity.")],
    commands: Annotated[ReaderCommandService, Depends(get_reader_command_service)],
) -> PaperTagCommandResponse:
    try:
        result = commands.add_paper_tag(
            paper_id,
            request.tag,
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
    return PaperTagCommandResponse(
        status=result.status,
        tags=list(result.tags),
        tags_revision=result.tags_revision,
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


@router.delete(
    "/papers/{paper_id}/tags",
    response_model=PaperTagCommandResponse,
    summary="Remove one Paper tag",
    description=(
        "Explicitly remove one normalized Paper tag when the supplied deterministic "
        "tag revision still matches. Removing an absent tag returns a truthful no-op."
    ),
    responses={
        404: {"model": APIError, "description": "No paper has the requested identity."},
        409: {"model": APIError, "description": "The Paper tag revision is stale."},
        422: {"model": APIError, "description": "The requested tag is invalid."},
        503: {"model": APIError, "description": "The persistent command could not complete consistently."},
    },
)
def remove_paper_tag(
    request: PaperTagCommandRequest,
    paper_id: Annotated[str, Path(min_length=1, max_length=200, description="Stable BluePrintReboot paper identity.")],
    commands: Annotated[ReaderCommandService, Depends(get_reader_command_service)],
) -> PaperTagCommandResponse:
    try:
        result = commands.remove_paper_tag(
            paper_id,
            request.tag,
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
    return PaperTagCommandResponse(
        status=result.status,
        tags=list(result.tags),
        tags_revision=result.tags_revision,
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
