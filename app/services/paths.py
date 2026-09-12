from __future__ import annotations

import os
from pathlib import Path


def portable_root() -> Path:
    configured = os.environ.get("JVT_PORTABLE_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[2]


def app_root() -> Path:
    return portable_root() / "app"


def config_root() -> Path:
    return portable_root() / "config"


def updates_root() -> Path:
    path = portable_root() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_root() -> Path:
    path = portable_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
