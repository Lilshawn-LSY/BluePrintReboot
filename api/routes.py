from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_health_summary, get_library_status
from api.schemas import HealthSummaryResponse, LibraryStatusResponse
from services.library_read_model import HealthSummary, LibraryStatus


router = APIRouter()


@router.get("/health", response_model=HealthSummaryResponse)
def health(summary: Annotated[HealthSummary, Depends(get_health_summary)]) -> HealthSummary:
    return summary


@router.get("/library/status", response_model=LibraryStatusResponse)
def library_status(status: Annotated[LibraryStatus, Depends(get_library_status)]) -> LibraryStatus:
    return status
