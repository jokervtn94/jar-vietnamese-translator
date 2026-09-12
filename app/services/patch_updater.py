from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from services.paths import portable_root, updates_root


@dataclass
class PatchResult:
    patch_id: str
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    backup_dir: str = ""


class PatchError(RuntimeError):
    pass


class PatchUpdater:
    """Transactional updater for small module/UI patches."""

    FORMAT = "jvt-patch-v1"

    def apply(self, patch_zip: str | Path) -> PatchResult:
        patch_zip = Path(patch_zip)
        root = portable_root().resolve()
        if not patch_zip.is_file():
            raise PatchError(f"Không tìm thấy patch: {patch_zip}")

        with tempfile.TemporaryDirectory(prefix="jvt_patch_") as td:
            temp = Path(td)
            with zipfile.ZipFile(patch_zip, "r") as zf:
                zf.extractall(temp)

            manifest_path = temp / "manifest.json"
            if not manifest_path.is_file():
                raise PatchError("Patch thiếu manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("format") != self.FORMAT:
                raise PatchError("Sai định dạng patch")

            patch_id = str(manifest.get("patch_id") or patch_zip.stem)
            backup = updates_root() / "backups" / f"{datetime.now():%Y%m%d_%H%M%S}_{patch_id}"
            backup.mkdir(parents=True, exist_ok=True)
            result = PatchResult(patch_id=patch_id, backup_dir=str(backup))
            changed: list[tuple[Path, Path | None]] = []

            try:
                for entry in manifest.get("files", []):
                    rel = Path(entry["path"])
                    if rel.is_absolute() or ".." in rel.parts:
                        raise PatchError(f"Path patch không hợp lệ: {rel}")
                    src = (temp / "files" / rel).resolve()
                    dst = (root / rel).resolve()
                    if root not in dst.parents and dst != root:
                        raise PatchError(f"Patch vượt ra ngoài thư mục app: {rel}")
                    if not src.is_file():
                        raise PatchError(f"Patch thiếu file: {rel}")

                    digest = hashlib.sha256(src.read_bytes()).hexdigest()
                    if digest.lower() != str(entry["sha256"]).lower():
                        raise PatchError(f"SHA-256 không khớp: {rel}")

                    old_backup = None
                    if dst.exists():
                        old_backup = backup / rel
                        old_backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dst, old_backup)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    changed.append((dst, old_backup))
                    result.applied.append(rel.as_posix())
            except Exception:
                for dst, old_backup in reversed(changed):
                    if old_backup and old_backup.exists():
                        shutil.copy2(old_backup, dst)
                    elif dst.exists():
                        dst.unlink()
                raise

            history = updates_root() / "patch_history.jsonl"
            with history.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "patch_id": patch_id,
                    "applied": result.applied,
                    "backup_dir": result.backup_dir,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }, ensure_ascii=False) + "\n")
            return result
