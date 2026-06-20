import pytest

from storage.project_link_store import (
    create_project_link,
    delete_links_for_project,
    delete_project_link,
    list_links_for_paper,
    list_links_for_project,
    list_links_for_target,
    list_project_links,
    project_links_path,
    update_project_link,
)
from tests.helpers import make_workspace


LINK_FIELDS = {
    "id",
    "project_id",
    "target_type",
    "target_id",
    "paper_id",
    "link_type",
    "note",
    "created_at",
}


def test_missing_project_links_file_returns_empty_list() -> None:
    base_dir = make_workspace("project-links-missing")

    assert list_project_links(base_dir) == []
    assert not project_links_path(base_dir).exists()


def test_create_paper_link_writes_valid_schema() -> None:
    base_dir = make_workspace("project-links-paper")

    link = create_project_link(
        "project-1",
        "paper",
        "paper-1",
        link_type="key_reference",
        note="Core background paper.",
        base_dir=base_dir,
    )

    assert LINK_FIELDS <= set(link)
    assert link["target_type"] == "paper"
    assert link["target_id"] == "paper-1"
    assert link["paper_id"] == "paper-1"
    assert list_project_links(base_dir) == [link]


def test_create_note_block_link_includes_paper_context() -> None:
    base_dir = make_workspace("project-links-block")

    link = create_project_link(
        "project-1",
        "note_block",
        "block-1",
        paper_id="paper-1",
        link_type="supports_project",
        base_dir=base_dir,
    )

    assert link["target_type"] == "note_block"
    assert link["target_id"] == "block-1"
    assert link["paper_id"] == "paper-1"


@pytest.mark.parametrize(
    ("field", "value"),
    (("target_type", "dataset"), ("link_type", "duplicates")),
)
def test_invalid_project_link_choices_are_rejected(field, value) -> None:
    base_dir = make_workspace(f"project-links-invalid-{field}")
    kwargs = {
        "project_id": "project-1",
        "target_type": "paper",
        "target_id": "paper-1",
        "base_dir": base_dir,
        field: value,
    }

    with pytest.raises(ValueError, match=field):
        create_project_link(**kwargs)


def test_duplicate_project_link_returns_existing_link() -> None:
    base_dir = make_workspace("project-links-duplicate")
    first = create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)

    duplicate = create_project_link(
        "project-1",
        "paper",
        "paper-1",
        note="Different note does not duplicate the relationship.",
        base_dir=base_dir,
    )

    assert duplicate == first
    assert list_project_links(base_dir) == [first]


def test_update_project_link_edits_metadata_and_preserves_target_fields() -> None:
    base_dir = make_workspace("project-links-update")
    link = create_project_link(
        "project-1",
        "note_block",
        "block-1",
        paper_id="paper-1",
        link_type="related",
        note="Original note",
        base_dir=base_dir,
    )

    updated = update_project_link(
        link["id"],
        {
            "id": "replacement",
            "project_id": "project-2",
            "target_type": "paper",
            "target_id": "paper-2",
            "paper_id": "paper-2",
            "created_at": "replacement",
            "link_type": "supports_project",
            "note": "Updated note",
        },
        base_dir=base_dir,
    )

    for field in ("id", "project_id", "target_type", "target_id", "paper_id", "created_at"):
        assert updated[field] == link[field]
    assert updated["link_type"] == "supports_project"
    assert updated["note"] == "Updated note"


def test_update_project_link_rejects_invalid_type_without_changing_link() -> None:
    base_dir = make_workspace("project-links-update-invalid")
    link = create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)

    with pytest.raises(ValueError, match="link_type"):
        update_project_link(link["id"], {"link_type": "invalid"}, base_dir=base_dir)

    assert list_project_links(base_dir) == [link]


def test_update_missing_project_link_does_not_create_link() -> None:
    base_dir = make_workspace("project-links-update-missing")

    with pytest.raises(KeyError):
        update_project_link("missing", {"note": "No link"}, base_dir=base_dir)

    assert list_project_links(base_dir) == []


def test_update_project_link_keeps_duplicate_prevention() -> None:
    base_dir = make_workspace("project-links-update-duplicate")
    related = create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)
    background = create_project_link(
        "project-1",
        "paper",
        "paper-1",
        link_type="background",
        base_dir=base_dir,
    )

    with pytest.raises(ValueError, match="Duplicate"):
        update_project_link(background["id"], {"link_type": "related"}, base_dir=base_dir)

    assert list_project_links(base_dir) == [related, background]


def test_project_link_filters_preserve_stored_order() -> None:
    base_dir = make_workspace("project-links-filters")
    paper_link = create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)
    block_link = create_project_link(
        "project-1",
        "note_block",
        "block-1",
        paper_id="paper-1",
        link_type="raises_question",
        base_dir=base_dir,
    )
    create_project_link("project-2", "paper", "paper-2", base_dir=base_dir)

    assert list_links_for_project("project-1", base_dir) == [paper_link, block_link]
    assert list_links_for_target("note_block", "block-1", base_dir) == [block_link]
    assert list_links_for_paper("paper-1", base_dir) == [paper_link, block_link]


def test_delete_project_link_is_safe() -> None:
    base_dir = make_workspace("project-links-delete")
    link = create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)

    assert delete_project_link(link["id"], base_dir) is True
    assert list_project_links(base_dir) == []
    assert delete_project_link("missing", base_dir) is False


def test_delete_links_for_project_only_removes_matching_links() -> None:
    base_dir = make_workspace("project-links-delete-project")
    create_project_link("project-1", "paper", "paper-1", base_dir=base_dir)
    remaining = create_project_link("project-2", "paper", "paper-2", base_dir=base_dir)

    assert delete_links_for_project("project-1", base_dir) == 1
    assert list_project_links(base_dir) == [remaining]
