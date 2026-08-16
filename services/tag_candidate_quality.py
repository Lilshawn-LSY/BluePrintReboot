from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from services.tag_book import explain_tag_book_suggestions, normalize_tag


def measure_candidate_quality_baseline(
    corpus: Sequence[Mapping[str, Any]],
    tag_book: Mapping[str, Any],
) -> dict[str, Any]:
    """Measure a small deterministic candidate corpus without tuning its generator.

    The metric intentionally treats only selectable, non-rejected suggestions as
    predicted candidate values. It reports expected presence, misses, and extra
    values, rather than assigning an invented confidence-based score.
    """

    expected_total = 0
    present_count = 0
    missing: list[str] = []
    false_positive_count = 0
    per_case: list[dict[str, Any]] = []
    for raw_case in corpus:
        case_id = str(raw_case.get("id", "")).strip()
        record = raw_case.get("record", {})
        expected_values = raw_case.get("expected_candidates", [])
        if not case_id or not isinstance(record, Mapping) or not isinstance(expected_values, list):
            raise ValueError("Candidate quality corpus cases need id, record, and expected_candidates.")
        expected = {normalize_tag(value) for value in expected_values if normalize_tag(value)}
        actual = {
            normalize_tag(item.get("canonical") or item.get("tag") or item.get("display"))
            for item in explain_tag_book_suggestions(dict(record), dict(tag_book))
            if item.get("selectable", True) and item.get("quality") != "rejected"
        }
        actual.discard("")
        hits = sorted(expected & actual)
        case_missing = sorted(expected - actual)
        extras = sorted(actual - expected)
        expected_total += len(expected)
        present_count += len(hits)
        missing.extend(f"{case_id}:{value}" for value in case_missing)
        false_positive_count += len(extras)
        per_case.append(
            {
                "id": case_id,
                "expected": sorted(expected),
                "present": hits,
                "missing": case_missing,
                "false_positives": extras,
            }
        )
    denominator = present_count + false_positive_count
    return {
        "case_count": len(corpus),
        "expected_candidate_count": expected_total,
        "expected_present_count": present_count,
        "miss_count": len(missing),
        "missing": missing,
        "false_positive_count": false_positive_count,
        "precision_like": present_count / denominator if denominator else None,
        "cases": per_case,
    }
