from ingest.tag_suggester import merge_tags, suggest_tags_for_record


def test_suggest_tags_for_record_from_metadata_and_text() -> None:
    record = {
        "title": "A CRISPR method for Arabidopsis root apical meristem analysis",
        "journal": "Plant Biology",
        "filename": "paper.pdf",
        "doi": "10.1000/example",
        "tags": "method",
    }
    extra_text = "Single cell RNA sequencing detected reactive oxygen species and auxin."

    assert suggest_tags_for_record(record, extra_text=extra_text) == [
        "plant-biology",
        "arabidopsis",
        "root",
        "meristem",
        "ros",
        "auxin",
        "single-cell",
        "scrna-seq",
        "crispr",
    ]


def test_merge_tags_preserves_existing_and_avoids_duplicates() -> None:
    assert merge_tags("plant-biology, crispr", ["CRISPR", "single cell", "root"]) == (
        "plant-biology, crispr, single-cell, root"
    )
