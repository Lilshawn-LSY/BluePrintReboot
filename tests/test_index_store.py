from storage.index_store import load_index, update_index_from_scan
from tests.helpers import make_workspace


def test_update_index_from_scan_appends_without_duplicates() -> None:
    workspace = make_workspace("index")
    data_dir = workspace / "data"
    papers_dir = workspace / "papers"
    notes_dir = workspace / "notes"
    index_csv = data_dir / "paper_index.csv"
    papers_dir.mkdir(parents=True)
    notes_dir.mkdir()
    (papers_dir / "Paper.pdf").write_bytes(b"%PDF-1.4\n")

    first = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    second = update_index_from_scan(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)

    assert len(first) == 1
    assert len(second) == 1
    assert load_index(index_csv).iloc[0]["filename"] == "Paper.pdf"
