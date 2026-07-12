from services.library_read_model import library_health_summary, paper_lifecycle_summary


def test_read_models_distinguish_lifecycle_and_degraded_states() -> None:
    assert paper_lifecycle_summary({"paper_id": "p1", "is_archived": "false"}, pdf_exists=True)["lifecycle_state"] == "active"
    archived = paper_lifecycle_summary({"paper_id": "p1", "is_archived": "true", "archived_at": "now"}, pdf_exists=False)
    assert archived["lifecycle_state"] == "archived"
    assert archived["pdf_state"] == "missing"
    summary = library_health_summary({"healthy": False, "duplicate_pdf_hashes": [{}], "ignored_duplicates": [{}], "quarantined_caches": [{}], "corrupt_json": [{"storage_class": "critical user state"}, {"storage_class": "rebuildable cache"}]})
    assert summary == {"duplicate_candidate_count": 1, "ignored_duplicate_count": 1, "corrupt_critical_state_count": 1, "corrupt_rebuildable_cache_count": 1, "quarantined_cache_count": 1, "library_state": "degraded but readable"}
