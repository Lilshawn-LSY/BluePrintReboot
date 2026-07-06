from core.paper_text_profile import PaperTextProfile
from storage.paper_profile_store import (
    delete_profile,
    load_profile,
    paper_profile_path,
    profile_exists,
    save_profile,
)
from tests.helpers import make_workspace


def test_profile_path_is_paper_id_based() -> None:
    profile_dir = make_workspace("paper-profile-paths")

    assert paper_profile_path("paper-1", profile_dir) == profile_dir / "paper-1.json"


def test_profile_save_load_roundtrip_and_delete() -> None:
    profile_dir = make_workspace("paper-profile-roundtrip")
    profile = PaperTextProfile(
        paper_id="paper-1",
        title="Profile title",
        abstract="Profile abstract",
        keywords=["synthetic biology", "Arabidopsis"],
        note_sections={"Methods": "Structured note method."},
        sources={"title": "paper_index", "note_sections.Methods": "note_blocks"},
        confidence={"title": "high", "abstract": "high", "keywords": "high", "note_sections": "high"},
        generated_at="2026-07-06T00:00:00+00:00",
    )

    saved_path = save_profile(profile, profile_dir)
    loaded = load_profile("paper-1", profile_dir)

    assert saved_path == profile_dir / "paper-1.json"
    assert profile_exists("paper-1", profile_dir) is True
    assert loaded is not None
    assert loaded.to_dict() == profile.to_dict()
    assert delete_profile("paper-1", profile_dir) is True
    assert profile_exists("paper-1", profile_dir) is False
    assert delete_profile("paper-1", profile_dir) is False


def test_invalid_profile_json_is_not_reusable() -> None:
    profile_dir = make_workspace("paper-profile-invalid")
    path = paper_profile_path("paper-1", profile_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert load_profile("paper-1", profile_dir) is None
