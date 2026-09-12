from __future__ import annotations

import json
from pathlib import Path

from contracts.module_contract import ModuleContract
from services.paths import config_root, portable_root


class ModuleRegistry:
    def __init__(self, manifest: Path | None = None):
        self.manifest = manifest or (config_root() / "modules.json")

    def load(self) -> dict[str, ModuleContract]:
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        root = portable_root()
        result: dict[str, ModuleContract] = {}
        for name, info in data["modules"].items():
            result[name] = ModuleContract(
                name=name,
                version=str(info["version"]),
                path=root / info["path"],
                kind=info.get("kind", "module"),
                restart_required=bool(info.get("restart_required", True)),
            )
        return result
