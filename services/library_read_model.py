from __future__ import annotations

from typing import Any, Mapping


def paper_lifecycle_summary(record: Mapping[str, Any], *, pdf_exists: bool) -> dict[str, Any]:
    archived = str(record.get("is_archived", "false")).lower() == "true"
    return {
        "paper_id": str(record.get("paper_id", "")),
        "lifecycle_state": "archived" if archived else "active",
        "is_archived": archived,
        "archived_at": str(record.get("archived_at", "")),
        "pdf_state": "available" if pdf_exists else "missing",
        "readable": bool(pdf_exists),
    }


def library_health_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    corrupt = [item for item in report.get("corrupt_json", []) if isinstance(item, Mapping)]
    return {
        "duplicate_candidate_count": len(report.get("duplicate_pdf_hashes", [])),
        "ignored_duplicate_count": len(report.get("ignored_duplicates", [])),
        "corrupt_critical_state_count": sum(item.get("storage_class") == "critical user state" for item in corrupt),
        "corrupt_rebuildable_cache_count": sum(item.get("storage_class") == "rebuildable cache" for item in corrupt),
        "quarantined_cache_count": len(report.get("quarantined_caches", [])),
        "library_state": "healthy" if report.get("healthy") else "degraded but readable",
    }
