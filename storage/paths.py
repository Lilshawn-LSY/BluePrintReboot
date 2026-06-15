from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = PROJECT_ROOT / "papers"
NOTES_DIR = PROJECT_ROOT / "notes"
EXPORTS_DIR = PROJECT_ROOT / "exports"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
INDEX_CSV = DATA_DIR / "paper_index.csv"


def ensure_workspace_dirs() -> None:
    for directory in (DATA_DIR, PAPERS_DIR, NOTES_DIR, EXPORTS_DIR, EXTRACTED_TEXT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
