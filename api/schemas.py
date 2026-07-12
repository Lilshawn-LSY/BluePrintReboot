from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
