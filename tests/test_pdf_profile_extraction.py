from services.pdf_profile_extraction import clean_pdf_text_for_profile, extract_pdf_profile_from_text


REVIEW_FIXTURE_TEXT = """Downloaded from example.org on 2026-07-06
REVIEW
Lateral Root Development in Plant Stress Responses
Jane Doe1, John Smith2
doi: 10.1234/example.review

Abstract
Plants coordinate biochemical responses
and includes lateral root developmental programs across stress contexts.

Keywords
lateral root; Arabidopsis; biochemical responses

Introduction
Review articles summarize the current literature.
1
"""


def test_pdf_text_cleanup_joins_soft_wrapped_paragraph_lines() -> None:
    cleaned = clean_pdf_text_for_profile(REVIEW_FIXTURE_TEXT)

    assert "Downloaded from" not in cleaned
    assert "biochemical responses and includes" in cleaned
    assert "\nAbstract\n" in f"\n{cleaned}"
    assert "\nKeywords\n" in f"\n{cleaned}"


def test_pdf_profile_extracts_review_front_matter() -> None:
    profile = extract_pdf_profile_from_text(REVIEW_FIXTURE_TEXT)

    assert profile.title == "Lateral Root Development in Plant Stress Responses"
    assert profile.authors == "Jane Doe, John Smith"
    assert profile.abstract.startswith("Plants coordinate biochemical responses and includes")
    assert profile.keywords == ["lateral root", "Arabidopsis", "biochemical responses"]
    assert profile.doi == "10.1234/example.review"
    assert profile.article_type == "review"
    assert profile.section_headings[:3] == ["Review", "Abstract", "Keywords"]


def test_pdf_profile_detects_research_article_from_sections() -> None:
    profile = extract_pdf_profile_from_text(
        """A Research Paper
Alice Example

Abstract
We tested a model.

Methods
Cells were profiled.

Results
The result was measured.

Discussion
The result is discussed.
"""
    )

    assert profile.article_type == "research"
    assert {"Abstract", "Methods", "Results", "Discussion"} <= set(profile.section_headings)
