from __future__ import annotations

from services import library_read_model
from services.library_read_model import HealthSummary, LibraryStatus, PaperDetail, PaperListItem


class ReadModelUnavailable(Exception):
    """An expected API boundary error with no private storage details."""


def get_health_summary() -> HealthSummary:
    try:
        return library_read_model.build_health_summary()
    except Exception:
        raise ReadModelUnavailable from None


def get_library_status() -> LibraryStatus:
    try:
        return library_read_model.build_library_status()
    except Exception:
        raise ReadModelUnavailable from None


def get_paper_list_items() -> list[PaperListItem]:
    try:
        return library_read_model.build_paper_list_items()
    except Exception:
        raise ReadModelUnavailable from None


def get_paper_detail(paper_id: str) -> PaperDetail | None:
    try:
        return library_read_model.build_paper_detail(paper_id)
    except Exception:
        raise ReadModelUnavailable from None
