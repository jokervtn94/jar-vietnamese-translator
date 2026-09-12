from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List
import json
import os


@dataclass
class DiagnosticHistoryEntry:
    generated_at_utc: str
    jar_name: str
    compatibility_score: int
    runtime_risk: str
    startup_title: str
    startup_severity: str
    next_action: str
    json_path: str
    text_path: str


def default_history_path() -> Path:
    if os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "JAR Vietnamese Translator"
    elif os.environ.get("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"]) / "jar-vietnamese-translator"
    else:
        root = Path.home() / ".config" / "jar-vietnamese-translator"
    return root / "diagnostic_history.json"


class DiagnosticHistoryStore:
    def __init__(self, path: str | Path | None = None, max_items: int = 10):
        self.path = Path(path) if path is not None else default_history_path()
        self.max_items = max(1, int(max_items))

    def load(self) -> List[DiagnosticHistoryEntry]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        entries: List[DiagnosticHistoryEntry] = []
        for item in raw[: self.max_items]:
            if not isinstance(item, dict):
                continue
            try:
                entries.append(DiagnosticHistoryEntry(**item))
            except TypeError:
                continue
        return entries

    def save(self, entries: List[DiagnosticHistoryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in entries[: self.max_items]]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def add(self, report, json_path: str | Path, text_path: str | Path) -> DiagnosticHistoryEntry:
        actions = list(getattr(report, "recommended_actions", []) or [])
        top = actions[0] if actions else None
        if isinstance(top, dict):
            priority = top.get("priority", 4)
            title = top.get("title", "")
            detail = top.get("detail", "")
        else:
            priority = getattr(top, "priority", 4) if top is not None else 4
            title = getattr(top, "title", "") if top is not None else ""
            detail = getattr(top, "detail", "") if top is not None else ""
        next_action = f"P{priority} · {title}" + ((" · " + detail) if detail else "")

        entry = DiagnosticHistoryEntry(
            generated_at_utc=str(getattr(report, "generated_at_utc", "")),
            jar_name=str(getattr(report, "jar_name", "")),
            compatibility_score=int(getattr(report, "compatibility_score", 100)),
            runtime_risk=str(getattr(report, "runtime_risk", "unknown")),
            startup_title=str(getattr(report, "startup_title", "")),
            startup_severity=str(getattr(report, "startup_severity", "unknown")),
            next_action=next_action,
            json_path=str(Path(json_path).resolve()),
            text_path=str(Path(text_path).resolve()),
        )

        entries = [item for item in self.load() if item.json_path != entry.json_path]
        entries.insert(0, entry)
        self.save(entries)
        return entry
