from pathlib import Path

import pandas as pd
import pytest

from storage.identities import is_safe_paper_id, require_safe_paper_id
from storage.index_store import save_index
from storage.note_store import note_path_for


@pytest.mark.parametrize(
    "paper_id",
    ["", ".", "..", "../escape", "sub/path", r"sub\path", "C:escape", "paper-id ", "paper\x00id"],
)
def test_unsafe_paper_ids_are_rejected_at_filename_boundaries(paper_id: str, tmp_path: Path) -> None:
    assert is_safe_paper_id(paper_id) is False
    with pytest.raises(ValueError):
        require_safe_paper_id(paper_id)
    with pytest.raises(ValueError):
        note_path_for({"paper_id": paper_id}, notes_dir=tmp_path / "notes")


def test_valid_existing_paper_ids_are_not_transformed() -> None:
    for paper_id in ("paper-1", "legacy.paper_2024", "A B"):
        assert require_safe_paper_id(paper_id) == paper_id


@pytest.mark.parametrize("paper_id", ["CON", "con.txt", "NUL", "COM1", "LPT9.md"])
def test_windows_reserved_paper_ids_are_rejected(paper_id: str) -> None:
    assert is_safe_paper_id(paper_id) is False


def test_index_write_rejects_unsafe_identity_without_replacing_valid_state(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    save_index(pd.DataFrame([{"paper_id": "paper-1", "filename": "paper.pdf"}]), index_csv)
    before = index_csv.read_bytes()

    with pytest.raises(ValueError, match="unsafe"):
        save_index(pd.DataFrame([{"paper_id": "../escape", "filename": "paper.pdf"}]), index_csv)

    assert index_csv.read_bytes() == before
