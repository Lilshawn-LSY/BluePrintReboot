from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from api.schemas import PaperDetail, PaperListItem, ProjectLink


class PaperContractError(ValueError):
    """A domain value cannot be represented by the public Paper API contract."""


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
