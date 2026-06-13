from pathlib import Path
from uuid import uuid4


def make_workspace(name: str) -> Path:
    path = Path("tests") / "_tmp" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
