from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.paper_text_profile import (
    PaperTextProfile,
    coerce_paper_text_profile,
    paper_text_profile_from_dict,
    paper_text_profile_to_dict,
)
from storage.atomic_json import JsonStoreError, atomic_write_json, read_json_file
from storage.paths import PAPER_PROFILES_DIR


def paper_profile_path(paper_id: str, profile_dir: Path = PAPER_PROFILES_DIR) -> Path:
    return Path(profile_dir) / f"{paper_id}.json"


def profile_exists(paper_id: str, profile_dir: Path = PAPER_PROFILES_DIR) -> bool:
    return paper_profile_path(paper_id, profile_dir).exists()


def load_profile(paper_id: str, profile_dir: Path = PAPER_PROFILES_DIR) -> PaperTextProfile | None:
    path = paper_profile_path(paper_id, profile_dir)
    if not path.exists():
        return None
    try:
        payload = read_json_file(path, store_name="Paper text profile cache")
    except JsonStoreError:
        return None
    if not isinstance(payload, Mapping):
        return None
    return paper_text_profile_from_dict({**payload, "paper_id": payload.get("paper_id") or paper_id})


def save_profile(
    profile: PaperTextProfile | Mapping[str, Any],
    profile_dir: Path = PAPER_PROFILES_DIR,
) -> Path:
    normalized = coerce_paper_text_profile(profile)
    path = paper_profile_path(normalized.paper_id, profile_dir)
    return atomic_write_json(
        path,
        paper_text_profile_to_dict(normalized),
        indent=2,
        ensure_ascii=False,
        trailing_newline=True,
    )


def delete_profile(paper_id: str, profile_dir: Path = PAPER_PROFILES_DIR) -> bool:
    path = paper_profile_path(paper_id, profile_dir)
    if not path.exists():
        return False
    path.unlink()
    return True
