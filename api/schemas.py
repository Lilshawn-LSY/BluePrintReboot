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

    filename: str
    relative_pdf_path: str = Field(description="Workspace-relative PDF path; never an absolute local path.")
    doi: str
    project_links: list[ProjectLink]
    note_available: bool
    extracted_text_available: bool
    profile_available: bool
    lifecycle_state: str
    recoverable_warnings: list[str]


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
