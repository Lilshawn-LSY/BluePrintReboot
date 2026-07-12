from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = PROJECT_ROOT / "papers"
NOTES_DIR = PROJECT_ROOT / "notes"
EXPORTS_DIR = PROJECT_ROOT / "exports"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
NOTE_BLOCKS_DIR = DATA_DIR / "note_blocks"
PAPER_PROFILES_DIR = DATA_DIR / "paper_profiles"
PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_JSON = PROJECTS_DIR / "projects.json"
PROJECT_LINKS_JSON = PROJECTS_DIR / "project_links.json"
INDEX_CSV = DATA_DIR / "paper_index.csv"
NOTE_IMPORTS_JSON = DATA_DIR / "note_imports.json"
LIFECYCLE_DECISIONS_JSON = DATA_DIR / "lifecycle_decisions.json"
RECOVERY_DIR = EXPORTS_DIR / "recovery"
QUARANTINE_DIR = DATA_DIR / "quarantine"


def ensure_workspace_dirs() -> None:
    for directory in (
        DATA_DIR,
        PAPERS_DIR,
        NOTES_DIR,
        EXPORTS_DIR,
        EXTRACTED_TEXT_DIR,
        NOTE_BLOCKS_DIR,
        PAPER_PROFILES_DIR,
        PROJECTS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
