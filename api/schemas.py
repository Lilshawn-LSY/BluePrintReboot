from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import Field

from ingest.doi import is_probable_doi, normalize_doi


class StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class HealthSummaryResponse(StrictResponseModel):
    overall_state: str
    blocking_issues: int
    warning_count: int
    corrupt_critical_state_count: int
    quarantine_count: int
    missing_pdf_count: int
    duplicate_review_count: int


class LibraryStatusResponse(StrictResponseModel):
    active_count: int
    archived_count: int
    missing_count: int
    duplicate_count: int
    corrupt_count: int
    quarantine_count: int
    degraded: bool
    workspace_warnings: list[str]


class ArchiveStatus(str, Enum):
    """Archive-state filter for paper collections."""

    active = "active"
    archived = "archived"
    all = "all"


class PaperListItem(StrictResponseModel):
    """Stable summary of one paper without raw storage fields."""

    paper_id: str = Field(description="Stable BluePrintReboot paper identity.")
    title: str
    first_author: str
    year: str = Field(description="Publication year, or an empty string when unknown.")
    status: str = Field(description="Reading progress, kept separate from archive state.")
    priority: str
    tags: list[str]
    archived: bool
    missing_pdf: bool
    health: list[str]


class ProjectLink(StrictResponseModel):
    project_id: str
    link_type: str
    target_type: str


class ProjectListItem(StrictResponseModel):
    """Allowlisted summary of one stored Project."""

    project_id: str
    name: str
    description: str
    status: str
    priority: str
    tags: list[str]
    created_at: str
    updated_at: str
    project_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    link_count: int = Field(ge=0)
    linked_paper_count: int = Field(ge=0)
    linked_note_block_count: int = Field(ge=0)


class LinkedPaperSummary(StrictResponseModel):
    """Bounded paper metadata embedded in a Project link."""

    paper_id: str
    title: str
    first_author: str
    year: str
    status: str
    priority: str
    tags: list[str]
    archived: bool


class ProjectTargetState(str, Enum):
    available = "available"
    orphaned = "orphaned"
    orphaned_note_block = "orphaned_note_block"
    orphaned_paper = "orphaned_paper"
    unavailable = "unavailable"
    not_applicable = "not_applicable"


class LinkedNoteBlockSummary(StrictResponseModel):
    block_id: str
    paper_id: str
    source_paper_title: str
    block_type: Literal[
        "summary", "claim", "method", "evidence", "question", "idea", "limitation"
    ]
    title: str
    text_preview: str = Field(max_length=280)
    page: str
    figure: str
    tags: list[str]


class ProjectLinkTarget(StrictResponseModel):
    link_id: str
    link_type: str
    target_type: str
    target_id: str
    target_state: ProjectTargetState
    paper_id: str
    created_at: str
    paper: LinkedPaperSummary | None
    note_block: LinkedNoteBlockSummary | None


class ProjectDetail(ProjectListItem):
    """One Project plus a bounded page of its real stored links."""

    links: list[ProjectLinkTarget]
    links_total: int = Field(ge=0)
    links_limit: int = Field(ge=1, le=100)
    links_offset: int = Field(ge=0)
    links_has_more: bool
    links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    orphaned_link_count: int = Field(ge=0)


class ProjectCommandState(StrictResponseModel):
    project_id: str
    name: str
    description: str
    status: Literal["active", "paused", "done", "archived"]
    priority: Literal["low", "normal", "high"]
    tags: list[str]
    created_at: str
    updated_at: str
    project_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    link_count: int = Field(ge=0)
    linked_paper_count: int = Field(ge=0)
    linked_note_block_count: int = Field(ge=0)


class PaperLinkCommandState(StrictResponseModel):
    link_id: str
    project_id: str
    paper_id: str
    link_type: Literal[
        "related",
        "background",
        "key_reference",
        "supports_project",
        "raises_question",
        "idea_for_project",
    ]
    created_at: str


class ProjectCommandResponse(StrictResponseModel):
    status: Literal["created", "saved", "no_op", "archived", "already_archived"]
    project: ProjectCommandState


class PaperLinkCommandResponse(StrictResponseModel):
    status: Literal["created", "unchanged", "removed"]
    project: ProjectCommandState
    link: PaperLinkCommandState


class NoteBlockItem(StrictResponseModel):
    id: str
    paper_id: str
    block_type: Literal[
        "summary", "claim", "method", "evidence", "question", "idea", "limitation"
    ]
    title: str
    text: str
    page: str
    figure: str
    quote: str
    tags: list[str]
    created_at: str
    updated_at: str


class NoteBlockSourcePaper(StrictResponseModel):
    paper_id: str
    title: str


class NoteBlockProjectLink(StrictResponseModel):
    link_id: str
    project_id: str
    project_name: str
    project_status: Literal["active", "paused", "done", "archived", "unavailable"]
    note_block_id: str
    link_type: Literal[
        "related",
        "background",
        "key_reference",
        "supports_project",
        "raises_question",
        "idea_for_project",
    ]
    links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class NoteBlockCollectionResponse(StrictResponseModel):
    source_paper: NoteBlockSourcePaper
    items: list[NoteBlockItem]
    total: int = Field(ge=0)
    note_blocks_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_links: list[NoteBlockProjectLink]
    project_links_state: Literal["available", "unavailable"]


class NoteBlockCommandResponse(StrictResponseModel):
    status: Literal["created", "saved", "no_op"]
    block: NoteBlockItem
    note_blocks_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    total: int = Field(ge=0)


class NoteBlockLinkCommandState(StrictResponseModel):
    link_id: str
    project_id: str
    paper_id: str
    note_block_id: str
    link_type: Literal[
        "related",
        "background",
        "key_reference",
        "supports_project",
        "raises_question",
        "idea_for_project",
    ]
    created_at: str


class NoteBlockLinkCommandResponse(StrictResponseModel):
    status: Literal["created", "unchanged", "removed"]
    project: ProjectCommandState
    link: NoteBlockLinkCommandState


class CanonicalTag(StrictResponseModel):
    canonical_key: str
    label: str
    category: str
    aliases: list[str]
    status: str
    suggestion_strength: int = Field(ge=0)


class CandidateQualityCounts(StrictResponseModel):
    high: int = Field(ge=0)
    medium: int = Field(ge=0)
    weak: int = Field(ge=0)
    rejected: int = Field(ge=0)


class CandidateSummaryResponse(StrictResponseModel):
    availability: Literal["available", "unavailable"]
    state: Literal["populated", "empty", "unavailable"]
    source: Literal["paper_index", "none"]
    evaluated_paper_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    known_canonical_match_count: int = Field(ge=0)
    quality_counts: CandidateQualityCounts


class SettingsWorkspaceResource(StrictResponseModel):
    code: Literal[
        "papers",
        "notes",
        "projects",
        "tags",
        "note_blocks",
        "project_links",
    ]
    label: str
    state: Literal["healthy", "warning", "unavailable", "empty"]
    count: int | None = Field(default=None, ge=0)
    summary: str

    @model_validator(mode="after")
    def validate_count_state(self) -> "SettingsWorkspaceResource":
        if self.state == "unavailable" and self.count is not None:
            raise ValueError("Unavailable workspace counts must be null.")
        if self.state != "unavailable" and self.count is None:
            raise ValueError("Available workspace counts must be numeric.")
        if self.state == "empty" and self.count != 0:
            raise ValueError("Empty workspace counts must be zero.")
        return self


class SettingsApplicationSection(StrictResponseModel):
    state: Literal["healthy"]
    product_version: str
    api_state: Literal["available"]
    api_contract_version: str
    summary: str


class SettingsWorkspaceSection(StrictResponseModel):
    state: Literal["healthy", "warning", "unavailable", "empty"]
    resources: list[SettingsWorkspaceResource]
    summary: str


class SettingsIntegrityIssue(StrictResponseModel):
    code: Literal[
        "missing_pdfs",
        "unindexed_pdfs",
        "orphan_notes",
        "orphan_note_blocks",
        "orphan_project_links",
        "corrupt_json",
    ]
    state: Literal["healthy", "warning", "unavailable"]
    count: int | None = Field(default=None, ge=0)
    severity: Literal["warning", "error"]
    explanation: str
    next_action: str

    @model_validator(mode="after")
    def validate_count_state(self) -> "SettingsIntegrityIssue":
        if self.state == "unavailable" and self.count is not None:
            raise ValueError("Unavailable integrity counts must be null.")
        if self.state != "unavailable" and self.count is None:
            raise ValueError("Available integrity counts must be numeric.")
        return self


class SettingsDataIntegritySection(StrictResponseModel):
    state: Literal["healthy", "warning", "unavailable"]
    issues: list[SettingsIntegrityIssue]
    summary: str


class SettingsBackupReadinessSection(StrictResponseModel):
    state: Literal["healthy", "warning", "unavailable"]
    snapshot_available: bool | None
    last_updated_at: str | None
    summary: str


class SettingsSummaryResponse(StrictResponseModel):
    application: SettingsApplicationSection
    workspace: SettingsWorkspaceSection
    data_integrity: SettingsDataIntegritySection
    backup_readiness: SettingsBackupReadinessSection


class PaperDetail(PaperListItem):
    """Safe read-only paper detail built from the frozen domain contract."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "example": {
                "paper_id": "paper-123",
                "title": "Example Research Paper",
                "first_author": "Example Author",
                "year": "2025",
                "status": "reading",
                "priority": "normal",
                "tags": ["methods"],
                "archived": False,
                "missing_pdf": False,
                "health": [],
                "authors": ["Example Author", "Second Author"],
                "journal": "Journal of Reproducible Research",
                "abstract": "A complete stored abstract is returned without summarization or truncation.",
                "keywords": ["reproducibility", "research methods"],
                "arxiv_id": "2501.12345",
                "filename": "example.pdf",
                "relative_pdf_path": "papers/example.pdf",
                "doi": "10.1000/example",
                "project_links": [],
                "note_available": True,
                "extracted_text_available": False,
                "profile_available": True,
                "lifecycle_state": "active",
                "recoverable_warnings": [],
            }
        },
    )

    authors: list[str] = Field(description="Ordered authors from the canonical index authors field.")
    journal: str
    abstract: str = Field(description="Complete stored abstract, or an empty string when unknown.")
    keywords: list[str] = Field(description="Ordered keywords from the canonical index keywords field.")
    arxiv_id: str = Field(description="Canonical or deterministically detected arXiv identifier, without network lookup.")
    filename: str
    relative_pdf_path: str = Field(description="Workspace-relative PDF path; never an absolute local path.")
    doi: str
    project_links: list[ProjectLink]
    note_available: bool
    extracted_text_available: bool
    profile_available: bool
    lifecycle_state: str
    recoverable_warnings: list[str]


class ReaderPdfState(str, Enum):
    available = "available"
    missing = "missing"


class ReaderNoteHeader(StrictResponseModel):
    """Allowlisted canonical Reading Note header values."""

    template_version: str
    paper_id: str
    title: str
    doi: str
    arxiv_id: str
    year: str
    first_author: str
    tags: str


class ReaderNoteBaseline(StrictResponseModel):
    """Identity of the exact saved note bytes returned in the snapshot."""

    exists: bool
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class EditablePaperMetadata(StrictResponseModel):
    title: str
    authors: str
    year: str
    journal: str
    doi: str
    abstract: str
    keywords: str


class ReaderSnapshotResponse(StrictResponseModel):
    """One coherent, read-only Reader load from the domain snapshot builder."""

    paper: PaperDetail
    editable_metadata: EditablePaperMetadata
    metadata_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    tags_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_state: ReaderPdfState
    saved_note_available: bool
    saved_note_content: str
    canonical_note_header: ReaderNoteHeader
    saved_note_baseline: ReaderNoteBaseline
    warnings: list[str]
    unavailable_reason: str


class ManagedPdfScanCandidate(StrictResponseModel):
    """One safe, managed-directory-only PDF scan result."""

    relative_path: str
    filename: str
    status: Literal["new", "already_registered", "invalid", "unavailable"]
    message: str
    can_import: bool
    size_bytes: int = Field(ge=0)


class ManagedPdfScanResponse(StrictResponseModel):
    status: Literal["ok", "unavailable"]
    message: str
    candidates: list[ManagedPdfScanCandidate]


class ManagedPdfImportResult(StrictResponseModel):
    relative_path: str
    filename: str
    status: Literal["imported", "already_registered", "missing", "invalid", "unavailable"]
    message: str
    can_import: bool
    size_bytes: int = Field(ge=0)
    paper_id: str = ""


class ManagedPdfImportResponse(StrictResponseModel):
    message: str
    imported_count: int = Field(ge=0)
    results: list[ManagedPdfImportResult]


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ManagedPdfImportRequest(StrictRequestModel):
    relative_paths: list[str] = Field(min_length=1, max_length=100)

    @field_validator("relative_paths")
    @classmethod
    def validate_relative_paths(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("PDF selections must be relative path strings.")
            path = item.strip().replace("\\", "/")
            posix_path = PurePosixPath(path)
            windows_path = PureWindowsPath(path)
            if (
                not path
                or posix_path.is_absolute()
                or windows_path.is_absolute()
                or windows_path.drive
                or windows_path.root
                or any(part in {"", ".", ".."} for part in posix_path.parts)
                or posix_path.suffix.casefold() != ".pdf"
            ):
                raise ValueError("PDF selections must be safe managed-relative PDF paths.")
            canonical = posix_path.as_posix()
            if canonical not in normalized:
                normalized.append(canonical)
        return normalized


class ProjectTagsMixin:
    @field_validator("tags", mode="before", check_fields=False)
    @classmethod
    def validate_tags(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or len(value) > 25:
            raise ValueError("Project tags must be a bounded list.")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Project tags must contain only strings.")
            tag = item.strip()
            if not tag or len(tag) > 100:
                raise ValueError("Project tags must be non-empty and at most 100 characters.")
            if tag not in normalized:
                normalized.append(tag)
        return normalized


class CreateProjectRequest(ProjectTagsMixin, StrictRequestModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5_000)
    status: Literal["active", "paused", "done"] = "active"
    priority: Literal["low", "normal", "high"] = "normal"
    tags: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be empty.")
        return normalized


class ProjectChanges(ProjectTagsMixin, StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    status: Literal["active", "paused", "done"] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    tags: list[str] | None = Field(default=None, max_length=25)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_present_fields(self) -> "ProjectChanges":
        if not self.model_fields_set:
            raise ValueError("At least one Project change is required.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("Project changes cannot be null.")
        return self


class UpdateProjectRequest(StrictRequestModel):
    changes: ProjectChanges
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArchiveProjectRequest(StrictRequestModel):
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class AddPaperLinkRequest(StrictRequestModel):
    paper_id: str = Field(min_length=1, max_length=200)
    link_type: Literal[
        "related",
        "background",
        "key_reference",
        "supports_project",
        "raises_question",
        "idea_for_project",
    ] = "related"
    expected_links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("paper_id")
    @classmethod
    def validate_paper_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Paper identity must not be empty.")
        return normalized


class RemovePaperLinkRequest(StrictRequestModel):
    expected_links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class NoteBlockTagsMixin:
    @field_validator("tags", mode="before", check_fields=False)
    @classmethod
    def validate_note_block_tags(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or len(value) > 25:
            raise ValueError("Note Block tags must be a bounded list.")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Note Block tags must contain only strings.")
            tag = item.strip()
            if not tag or len(tag) > 100:
                raise ValueError("Note Block tags must be non-empty and at most 100 characters.")
            if tag not in normalized:
                normalized.append(tag)
        return normalized


class CreateNoteBlockRequest(NoteBlockTagsMixin, StrictRequestModel):
    block_type: Literal[
        "summary", "claim", "method", "evidence", "question", "idea", "limitation"
    ]
    title: str = Field(default="", max_length=1_000)
    text: str = Field(default="", max_length=100_000)
    page: str = Field(default="", max_length=100)
    figure: str = Field(default="", max_length=500)
    quote: str = Field(default="", max_length=100_000)
    tags: list[str] = Field(default_factory=list, max_length=25)
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class NoteBlockChanges(NoteBlockTagsMixin, StrictRequestModel):
    block_type: Literal[
        "summary", "claim", "method", "evidence", "question", "idea", "limitation"
    ] | None = None
    title: str | None = Field(default=None, max_length=1_000)
    text: str | None = Field(default=None, max_length=100_000)
    page: str | None = Field(default=None, max_length=100)
    figure: str | None = Field(default=None, max_length=500)
    quote: str | None = Field(default=None, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=25)

    @model_validator(mode="after")
    def validate_present_fields(self) -> "NoteBlockChanges":
        if not self.model_fields_set:
            raise ValueError("At least one Note Block change is required.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("Note Block changes cannot be null.")
        return self


class UpdateNoteBlockRequest(StrictRequestModel):
    changes: NoteBlockChanges
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class AddNoteBlockLinkRequest(StrictRequestModel):
    paper_id: str = Field(min_length=1, max_length=200)
    note_block_id: str = Field(min_length=1, max_length=200)
    link_type: Literal[
        "related",
        "background",
        "key_reference",
        "supports_project",
        "raises_question",
        "idea_for_project",
    ] = "related"
    expected_links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("paper_id", "note_block_id")
    @classmethod
    def validate_identities(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Identity must not be empty.")
        return normalized


class RemoveNoteBlockLinkRequest(StrictRequestModel):
    expected_links_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class MetadataChanges(StrictRequestModel):
    title: str | None = None
    authors: str | None = None
    year: str | None = None
    journal: str | None = None
    doi: str | None = None
    abstract: str | None = None
    keywords: str | None = None

    @field_validator(
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "abstract",
        "keywords",
        mode="before",
    )
    @classmethod
    def validate_string_and_size(cls, value: Any, info) -> str:
        if not isinstance(value, str):
            raise ValueError("Metadata values must be strings.")
        limits = {
            "title": 1_000,
            "authors": 5_000,
            "year": 4,
            "journal": 1_000,
            "doi": 2_048,
            "abstract": 100_000,
            "keywords": 10_000,
        }
        if len(value) > limits[info.field_name]:
            raise ValueError("Metadata value is too large.")
        return value

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if normalized and (
            len(normalized) != 4
            or not normalized.isdigit()
            or not 1000 <= int(normalized) <= 2100
        ):
            raise ValueError("Year must be empty or a reasonable four-digit year.")
        return value

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_doi(value)
        if normalized and not is_probable_doi(normalized):
            raise ValueError("DOI is not valid.")
        return value

    @model_validator(mode="after")
    def validate_present_fields(self) -> "MetadataChanges":
        if not self.model_fields_set:
            raise ValueError("At least one metadata change is required.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("Metadata values must be strings.")
        return self


class MetadataCommandRequest(StrictRequestModel):
    changes: MetadataChanges
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class MetadataEnrichmentPreviewRequest(StrictRequestModel):
    """An intentionally empty, explicit request for non-persistent candidates."""


class MetadataEnrichmentFieldPreview(StrictResponseModel):
    field: Literal["title", "authors", "year", "journal", "doi", "abstract", "keywords"]
    current_value: str
    candidate_value: str
    source: str
    state: Literal["unchanged", "conflict", "available", "unavailable"]


class MetadataEnrichmentPreviewResponse(StrictResponseModel):
    paper_id: str
    metadata_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_sources: list[str]
    fields: list[MetadataEnrichmentFieldPreview]
    diagnostics: list[str]


class PersistedReadingNote(StrictResponseModel):
    exists: bool
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class MetadataCommandResponse(StrictResponseModel):
    status: Literal["saved", "no_op"]
    metadata: EditablePaperMetadata
    metadata_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    changed_fields: list[
        Literal["title", "authors", "year", "journal", "doi", "abstract", "keywords"]
    ]
    note_header_status: Literal["updated", "unchanged", "not_present", "not_required"]
    canonical_note_header: ReaderNoteHeader
    canonical_note_header_text: str
    reading_note: PersistedReadingNote


class PaperTagCommandRequest(StrictRequestModel):
    tag: str = Field(min_length=1, max_length=100)
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Paper tag must not be empty.")
        return normalized


class PaperTagCommandResponse(StrictResponseModel):
    status: Literal["saved", "no_op"]
    tags: list[str]
    tags_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    note_header_status: Literal["updated", "unchanged", "not_present"]
    canonical_note_header: ReaderNoteHeader
    canonical_note_header_text: str
    reading_note: PersistedReadingNote


class ReadingNoteCommandRequest(StrictRequestModel):
    content: str = Field(max_length=2_000_000)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReadingNoteCommandResponse(StrictResponseModel):
    status: Literal["created", "saved", "no_op"]
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class PaginatedPaperList(StrictResponseModel):
    """A deterministic page of papers matching the requested archive filter."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "paper_id": "paper-123",
                        "title": "Example Research Paper",
                        "first_author": "Example Author",
                        "year": "2025",
                        "status": "reading",
                        "priority": "normal",
                        "tags": ["methods"],
                        "archived": False,
                        "missing_pdf": False,
                        "health": [],
                    }
                ],
                "total": 1,
                "limit": 20,
                "offset": 0,
                "has_more": False,
            }
        },
    )

    items: list[PaperListItem]
    total: int = Field(ge=0, description="Matching papers before pagination.")
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool = Field(description="Whether another matching item exists after this page.")


class PaginatedProjectList(StrictResponseModel):
    items: list[ProjectListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool


class PaginatedTagList(StrictResponseModel):
    items: list[CanonicalTag]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool
    source_state: Literal["canonical", "legacy_fallback"]


class APIError(StrictResponseModel):
    detail: str
