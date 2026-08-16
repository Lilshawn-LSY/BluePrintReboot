from __future__ import annotations

import json
from pathlib import Path

from services.tag_book import load_tag_book
from services.tag_candidate_quality import measure_candidate_quality_baseline


CORPUS_PATH = Path(__file__).parent / "fixtures" / "tag_candidate_quality_corpus.json"


def test_tag_candidate_quality_baseline_is_deterministic() -> None:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    first = measure_candidate_quality_baseline(corpus, load_tag_book())
    second = measure_candidate_quality_baseline(corpus, load_tag_book())

    assert first == second
    assert first["case_count"] == 3
    assert first["expected_candidate_count"] == 2
    assert first["expected_present_count"] == 2
    assert first["miss_count"] == 0
    assert first["false_positive_count"] == 1
    assert first["precision_like"] == 2 / 3
    assert first["cases"][1]["false_positives"] == ["performed-a-genome-wide-crispr-screen"]
