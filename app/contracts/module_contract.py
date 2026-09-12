from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleContract:
    name: str
    version: str
    path: Path
    kind: str
    restart_required: bool = True
