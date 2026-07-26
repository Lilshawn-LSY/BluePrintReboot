from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic import Field


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

    sha256: str = Field(pattern=r"^(?:|[0-9a-f]{64})$")
    size_bytes: int = Field(ge=0)


class ReaderSnapshotResponse(StrictResponseModel):
    """One coherent, read-only Reader load from the domain snapshot builder."""

    paper: PaperDetail
    pdf_state: ReaderPdfState
    saved_note_available: bool
    saved_note_content: str
    canonical_note_header: ReaderNoteHeader
    saved_note_baseline: ReaderNoteBaseline
    warnings: list[str]
    unavailable_reason: str


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


class APIError(StrictResponseModel):
    detail: str
