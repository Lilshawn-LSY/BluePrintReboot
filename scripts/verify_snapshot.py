from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.backup_snapshot import verify_backup_snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a BluePrintReboot backup ZIP in place without extracting it."
    )
    parser.add_argument("snapshot", type=Path, help="Path to the backup snapshot ZIP")
    args = parser.parse_args(argv)
    result = verify_backup_snapshot(args.snapshot)
    if result["valid"]:
        print(
            f"Snapshot verification passed: {result['checked_files']} files checked; "
            "no files were extracted."
        )
        return 0
    print("Snapshot verification failed; no files were extracted:")
    for error in result["errors"]:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
