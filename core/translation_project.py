import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

@dataclass
class TranslationProject:
    jar_path: str = ""
    translations: Dict[str, str] = field(default_factory=dict)
    project_path: str = ""
    dirty: bool = False

    def get(self, key: str) -> str:
        return self.translations.get(key, "")

    def set(self, key: str, value: str):
        value = value.strip()
        old = self.translations.get(key, "")
        if value:
            if old == value:
                return
            self.translations[key] = value
        else:
            if key not in self.translations:
                return
            self.translations.pop(key, None)
        self.dirty = True

    def clear_all(self):
        if self.translations:
            self.translations.clear()
            self.dirty = True

    def stats(self, result):
        total = sum(1 for _ in result.all_strings()) if result else 0
        translated = 0
        if result:
            translated = sum(1 for _, s in result.all_strings() if self.get(s.key))
        return total, translated

    def _payload(self, result=None):
        payload = {
            "format": "jar-translator-project-v2",
            "app_version": "4.14",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "jar_path": self.jar_path,
            "translations": self.translations,
        }
        if result:
            payload["source_summary"] = {
                "entries": len(result.entries),
                "candidates": len(result.candidates),
                "strings": sum(1 for _ in result.all_strings()),
            }
        return payload

    def save(self, path: str, result=None):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._payload(result), f, ensure_ascii=False, indent=2)
        self.project_path = path
        self.dirty = False

    def autosave(self, path: str, result=None):
        """Write a recovery snapshot without changing normal save state."""
        payload = self._payload(result)
        payload["autosave"] = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("format") != "jar-translator-project-v2":
            raise ValueError("Not a JAR Translator V2 project file")
        return cls(
            jar_path=payload.get("jar_path", ""),
            translations=dict(payload.get("translations", {})),
            project_path="" if payload.get("autosave") else path,
            dirty=bool(payload.get("autosave")),
        )

    def export_csv(self, result, path: str):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "source", "source_type", "score", "kind", "index", "encoding", "original", "vietnamese"])
            for c, s in result.all_strings():
                w.writerow([s.key, c.source, c.source_type, c.score, s.kind, s.index, s.encoding, s.value, self.get(s.key)])

    def import_csv(self, path: str, result) -> tuple[int, int]:
        valid = {s.key for _, s in result.all_strings()}
        imported = skipped = 0
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("key") or "").strip()
                vi = (row.get("vietnamese") or "").strip()
                if not key:
                    original = row.get("original", "")
                    source = row.get("source", "")
                    kind = row.get("kind", "")
                    try:
                        index = int(row.get("index", -1))
                    except ValueError:
                        index = -1
                    key = f"{source}\u241f{kind}\u241f{index}\u241f{original}"
                if key in valid and vi:
                    self.translations[key] = vi
                    imported += 1
                else:
                    skipped += 1
        if imported:
            self.dirty = True
        return imported, skipped
