from dataclasses import dataclass, field, asdict
from typing import List

@dataclass
class ExtractedString:
    source: str
    value: str
    kind: str
    index: int = -1
    encoding: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}\u241f{self.kind}\u241f{self.index}\u241f{self.value}"

    def to_dict(self):
        data = asdict(self)
        data["key"] = self.key
        return data

@dataclass
class Candidate:
    source: str
    source_type: str
    strings: List[ExtractedString] = field(default_factory=list)
    score: int = 0
    reasons: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "source": self.source,
            "source_type": self.source_type,
            "score": self.score,
            "reasons": self.reasons,
            "strings": [s.to_dict() for s in self.strings],
        }

@dataclass
class JarScanResult:
    jar_path: str
    entries: List[str] = field(default_factory=list)
    manifest: str = ""
    candidates: List[Candidate] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "jar_path": self.jar_path,
            "entries": self.entries,
            "manifest": self.manifest,
            "candidates": [c.to_dict() for c in self.candidates],
            "diagnostics": self.diagnostics,
        }

    def all_strings(self):
        for candidate in self.candidates:
            for string in candidate.strings:
                yield candidate, string
