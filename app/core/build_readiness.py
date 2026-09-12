
from dataclasses import dataclass, field
from typing import List
from pathlib import Path

from core.compatibility_analyzer import CompatibilityAnalyzer
from core.glyph_analyzer import GlyphAnalyzer

@dataclass
class ReadinessIssue:
    level: str       # INFO / WARNING / BLOCKED
    category: str
    source: str
    message: str

@dataclass
class BuildReadinessReport:
    status: str = "READY"   # READY / WARNING / BLOCKED
    total_strings: int = 0
    translated_strings: int = 0
    untranslated_strings: int = 0
    translated_ratio: float = 0.0
    binary_safe: int = 0
    binary_unsafe: int = 0
    compatibility_risk: str = "unknown"
    glyph_risk: str = "unknown"
    issues: List[ReadinessIssue] = field(default_factory=list)

    @property
    def blocked_count(self):
        return sum(1 for i in self.issues if i.level == "BLOCKED")

    @property
    def warning_count(self):
        return sum(1 for i in self.issues if i.level == "WARNING")

class BuildReadinessAnalyzer:
    def analyze(self, result, project):
        r=BuildReadinessReport()

        # Translation coverage
        all_strings=[s for _,s in result.all_strings()] if result else []
        r.total_strings=len(all_strings)
        r.translated_strings=sum(1 for s in all_strings if project.get(s.key).strip())
        r.untranslated_strings=max(0,r.total_strings-r.translated_strings)
        r.translated_ratio=(r.translated_strings/r.total_strings) if r.total_strings else 0.0

        if r.total_strings == 0:
            r.issues.append(ReadinessIssue("BLOCKED","scan","JAR","No translatable strings were detected."))
        elif r.translated_strings == 0:
            r.issues.append(ReadinessIssue("BLOCKED","translation","Project","No translated strings are available to build."))
        elif r.untranslated_strings > 0:
            r.issues.append(ReadinessIssue(
                "WARNING","translation","Project",
                f"{r.untranslated_strings} of {r.total_strings} strings are still untranslated."
            ))
        else:
            r.issues.append(ReadinessIssue("INFO","translation","Project","All detected strings are translated."))

        # Binary summary
        for s in all_strings:
            if s.kind.startswith("binary:"):
                if s.kind.endswith(":safe"):
                    r.binary_safe += 1
                else:
                    r.binary_unsafe += 1
        if r.binary_unsafe:
            r.issues.append(ReadinessIssue(
                "WARNING","binary","JAR",
                f"{r.binary_unsafe} binary strings are raw/unknown and will remain locked."
            ))
        if r.binary_safe:
            r.issues.append(ReadinessIssue(
                "INFO","binary","JAR",
                f"{r.binary_safe} binary strings have recognized framing."
            ))

        # Encoding / font compatibility
        compat=CompatibilityAnalyzer().analyze(result.jar_path,result,project)
        r.compatibility_risk=compat.overall_risk
        if compat.overall_risk == "high":
            r.issues.append(ReadinessIssue(
                "WARNING","compatibility","JAR",
                "Encoding/font compatibility risk is HIGH."
            ))
        elif compat.overall_risk == "medium":
            r.issues.append(ReadinessIssue(
                "WARNING","compatibility","JAR",
                "Encoding/font compatibility risk is MEDIUM."
            ))
        else:
            r.issues.append(ReadinessIssue(
                "INFO","compatibility","JAR",
                f"Encoding/font compatibility risk is {compat.overall_risk.upper()}."
            ))

        # Glyph map status
        glyph=GlyphAnalyzer().analyze(result.jar_path,result,project)
        r.glyph_risk=glyph.risk
        if glyph.maps and glyph.missing_chars:
            chars=" ".join(sorted(glyph.missing_chars,key=lambda c: ord(c)))
            if len(chars)>140:
                chars=chars[:140]+"..."
            r.issues.append(ReadinessIssue(
                "WARNING","glyph","Fonts",
                f"{len(glyph.missing_chars)} required glyphs are missing: {chars}"
            ))
        elif glyph.maps and not glyph.missing_chars:
            r.issues.append(ReadinessIssue(
                "INFO","glyph","Fonts","Parsed font maps contain all required characters."
            ))
        else:
            r.issues.append(ReadinessIssue(
                "WARNING","glyph","Fonts",
                "No parseable glyph map was found; custom sprite-font coverage is unverified."
            ))

        # Source JAR checks
        source=Path(result.jar_path)
        if not source.exists():
            r.issues.append(ReadinessIssue("BLOCKED","source","JAR","Source JAR no longer exists."))

        # Final state
        if any(i.level=="BLOCKED" for i in r.issues):
            r.status="BLOCKED"
        elif any(i.level=="WARNING" for i in r.issues):
            r.status="WARNING"
        else:
            r.status="READY"
        return r
