
from dataclasses import dataclass, field
from typing import List
from pathlib import Path

from core.compatibility_analyzer import CompatibilityAnalyzer
from core.glyph_analyzer import GlyphAnalyzer
from core.activation_flow_analyzer import ActivationFlowAnalyzer

@dataclass
class ReadinessIssue:
    level: str
    category: str
    source: str
    message: str

@dataclass
class BuildReadinessReport:
    status: str = "READY"
    total_strings: int = 0
    translated_strings: int = 0
    untranslated_strings: int = 0
    translated_ratio: float = 0.0
    binary_safe: int = 0
    binary_unsafe: int = 0
    compatibility_risk: str = "unknown"
    runtime_risk: str = "unknown"
    runtime_score: int = 100
    target_profile: str = "FreeJ2ME / RG35XX"
    activation_risk: str = "unknown"
    activation_score: int = 0
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
            r.issues.append(ReadinessIssue("WARNING","translation","Project",f"{r.untranslated_strings} of {r.total_strings} strings are still untranslated."))
        else:
            r.issues.append(ReadinessIssue("INFO","translation","Project","All detected strings are translated."))

        for s in all_strings:
            if s.kind.startswith("binary:"):
                if s.kind.endswith(":safe"):
                    r.binary_safe += 1
                else:
                    r.binary_unsafe += 1
        if r.binary_unsafe:
            r.issues.append(ReadinessIssue("WARNING","binary","JAR",f"{r.binary_unsafe} binary strings are raw/unknown and will remain locked."))
        if r.binary_safe:
            r.issues.append(ReadinessIssue("INFO","binary","JAR",f"{r.binary_safe} binary strings have recognized framing."))

        compat=CompatibilityAnalyzer().analyze(result.jar_path,result,project)
        r.compatibility_risk=compat.overall_risk
        r.runtime_risk=getattr(compat,"runtime_risk","unknown")
        r.runtime_score=int(getattr(compat,"compatibility_score",100))
        runtime=getattr(compat,"runtime",None)
        target=getattr(runtime,"rg35xx",None) if runtime is not None else None

        if compat.overall_risk == "high":
            r.issues.append(ReadinessIssue("WARNING","compatibility","JAR","Overall compatibility risk is HIGH (encoding, font, or runtime dependency)."))
        elif compat.overall_risk == "medium":
            r.issues.append(ReadinessIssue("WARNING","compatibility","JAR","Overall compatibility risk is MEDIUM (encoding, font, or runtime dependency)."))
        else:
            r.issues.append(ReadinessIssue("INFO","compatibility","JAR",f"Overall compatibility risk is {compat.overall_risk.upper()}."))

        if target is not None:
            r.runtime_score=int(getattr(target,"score",r.runtime_score))
            unsupported=list(getattr(target,"unsupported",[]) or [])
            conditional=list(getattr(target,"conditional",[]) or [])
            if unsupported:
                r.issues.append(ReadinessIssue("WARNING","runtime","FreeJ2ME / RG35XX","Unsupported API dependencies: " + ", ".join(unsupported) + "."))
            if conditional:
                r.issues.append(ReadinessIssue("WARNING","runtime","FreeJ2ME / RG35XX","Conditional API dependencies require runtime testing: " + ", ".join(conditional) + "."))
            r.issues.append(ReadinessIssue("INFO" if not unsupported and not conditional else "WARNING","runtime","FreeJ2ME / RG35XX",f"Target runtime score: {r.runtime_score}/100; risk: {getattr(target,'risk',r.runtime_risk).upper()}."))

        if runtime is not None and getattr(runtime,"uses_wma_sms",False):
            targets=list(getattr(runtime,"sms_targets",[]) or [])
            endpoint=(" Endpoints: " + ", ".join(targets[:5]) + ".") if targets else ""
            r.issues.append(ReadinessIssue("WARNING","wma_sms","FreeJ2ME / RG35XX","Legacy WMA/SMS dependency detected. Real SMS transport must remain disabled; blocked transport must not be treated as successful activation." + endpoint))

        try:
            activation=ActivationFlowAnalyzer().analyze(result.jar_path)
            r.activation_risk=activation.risk
            r.activation_score=activation.score
            if activation.risk != "low":
                classes=", ".join(activation.suspicious_classes[:5]) or "no named class"
                flags=[]
                if activation.likely_activation_gate:
                    flags.append("activation/registration gate")
                if activation.likely_payment_flow:
                    flags.append("payment/subscription flow")
                if activation.wma_linked:
                    flags.append("WMA/SMS-linked")
                r.issues.append(ReadinessIssue(
                    "WARNING","activation","JAR",
                    f"Legacy flow risk {activation.risk.upper()} ({activation.score}/100): "
                    + (", ".join(flags) or "suspicious activation/payment indicators")
                    + f". Suspicious classes: {classes}. Analysis is read-only; do not assume SMS blocking equals activation success."
                ))
            else:
                r.issues.append(ReadinessIssue("INFO","activation","JAR","No strong legacy activation/payment-flow indicators were detected."))
        except Exception as e:
            r.activation_risk="unknown"
            r.issues.append(ReadinessIssue("WARNING","activation","JAR",f"Activation/payment flow scan could not complete: {e}"))

        glyph=GlyphAnalyzer().analyze(result.jar_path,result,project)
        r.glyph_risk=glyph.risk
        if glyph.maps and glyph.missing_chars:
            chars=" ".join(sorted(glyph.missing_chars,key=lambda c: ord(c)))
            if len(chars)>140:
                chars=chars[:140]+"..."
            r.issues.append(ReadinessIssue("WARNING","glyph","Fonts",f"{len(glyph.missing_chars)} required glyphs are missing: {chars}"))
        elif glyph.maps and not glyph.missing_chars:
            r.issues.append(ReadinessIssue("INFO","glyph","Fonts","Parsed font maps contain all required characters."))
        else:
            r.issues.append(ReadinessIssue("WARNING","glyph","Fonts","No parseable glyph map was found; custom sprite-font coverage is unverified."))

        source=Path(result.jar_path)
        if not source.exists():
            r.issues.append(ReadinessIssue("BLOCKED","source","JAR","Source JAR no longer exists."))

        if any(i.level=="BLOCKED" for i in r.issues):
            r.status="BLOCKED"
        elif any(i.level=="WARNING" for i in r.issues):
            r.status="WARNING"
        else:
            r.status="READY"
        return r
