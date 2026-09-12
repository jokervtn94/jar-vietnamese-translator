from __future__ import annotations

from pathlib import Path

_THEME_FILE = Path(__file__).resolve().parents[1] / "themes" / "monokai_light.qss"


def load_fluent_light_theme() -> str:
    try:
        return _THEME_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_fluent_dark_theme() -> str:
    return load_fluent_light_theme()
