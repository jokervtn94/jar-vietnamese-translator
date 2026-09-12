from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a JAR Vietnamese Translator modular patch")
    parser.add_argument("patch", help="Path to PATCH.zip")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    app_root = root / "app"
    sys.path.insert(0, str(app_root))
    from services.patch_updater import PatchUpdater

    result = PatchUpdater().apply(args.patch)
    print(f"Patch: {result.patch_id}")
    print(f"Updated: {len(result.applied)} file(s)")
    for path in result.applied:
        print(f"  - {path}")
    print(f"Backup: {result.backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
