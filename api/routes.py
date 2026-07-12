from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from api.adapters import PaperContractError, adapt_paper_detail, adapt_paper_list_item
from api.dependencies import ReadModelUnavailable, get_health_summary, get_library_status, get_paper_detail, get_paper_list_items
from api.schemas import APIError, ArchiveStatus, HealthSummaryResponse, LibraryStatusResponse, PaginatedPaperList, PaperDetail, PaperListItem
from services.library_read_model import HealthSummary, LibraryStatus, PaperDetail as DomainPaperDetail, PaperListItem as DomainPaperListItem


router = APIRouter()


@router.get("/health", response_model=HealthSummaryResponse)
def health(summary: Annotated[HealthSummary, Depends(get_health_summary)]) -> HealthSummary:
    return summary


@router.get("/library/status", response_model=LibraryStatusResponse)
def library_status(status: Annotated[LibraryStatus, Depends(get_library_status)]) -> LibraryStatus:
    return status


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
