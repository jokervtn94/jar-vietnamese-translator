from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

ALLOWED_PREFIXES = ("app/", "config/", "assets/")


def git_changed(base: str, head: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=AM", base, head, "--", *ALLOWED_PREFIXES],
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def make_patch(root: Path, files: list[str], output: Path, patch_id: str) -> Path:
    entries = []
    valid = []
    for rel in files:
        rel = rel.replace("\\", "/")
        if not rel.startswith(ALLOWED_PREFIXES):
            continue
        path = root / rel
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": rel, "sha256": digest, "size": path.stat().st_size})
        valid.append((rel, path))

    manifest = {
        "format": "jvt-patch-v1",
        "patch_id": patch_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "restart_required": True,
        "files": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for rel, path in valid:
            zf.write(path, f"files/{rel}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--output", required=True)
    parser.add_argument("--patch-id", required=True)
    args = parser.parse_args()

    root = Path.cwd()
    files = list(args.file)
    if args.base:
        files.extend(git_changed(args.base, args.head))
    files = sorted(set(files))
    make_patch(root, files, Path(args.output), args.patch_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
