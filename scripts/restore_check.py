from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.restore_readiness import check_disposable_restore_target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only snapshot and disposable restore-target readiness check.")
    parser.add_argument("snapshot", type=Path, help="Original snapshot ZIP; it is never modified")
    parser.add_argument("target", type=Path, help="Existing empty disposable directory outside this repository")
    args = parser.parse_args(argv)
    result = check_disposable_restore_target(args.snapshot, args.target, protected_root=PROJECT_ROOT)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
