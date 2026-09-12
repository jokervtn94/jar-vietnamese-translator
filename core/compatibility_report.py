from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import json

from core.startup_blocking_assessment import assess_startup_blocking


@dataclass
class CompatibilityExport:
    schema: str = "jar-translator.compatibility-report.v1"
    generated_at_utc: str = ""
    jar_name: str = ""
    jar_path: str = ""
    target: str = "FreeJ2ME / RG35XX"
    midp_profile: str = "unknown"
    cldc_configuration: str = "unknown"
    compatibility_score: int = 100
    runtime_risk: str = "low"
    detected_apis: List[str] = field(default_factory=list)
    api_sources: Dict[str, List[str]] = field(default_factory=dict)
    unsupported_apis: List[str] = field(default_factory=list)
    conditional_apis: List[str] = field(default_factory=list)
    sms_targets: List[str] = field(default_factory=list)
    activation_risk: str = "low"
    activation_score: int = 0
    likely_activation_gate: bool = False
    likely_payment_flow: bool = False
    wma_linked: bool = False
    suspicious_classes: List[str] = field(default_factory=list)
    suspicious_resources: List[str] = field(default_factory=list)
    startup_reachable: bool = False
    startup_path: List[str] = field(default_factory=list)
    startup_classification: str = "compatible_or_unknown"
    startup_severity: str = "low"
    startup_title: str = "Không thấy blocker startup rõ ràng"
    startup_reasons: List[str] = field(default_factory=list)
    recommendation: str = ""
    safety_note: str = (
        "Diagnostic report only. Real SMS transport remains disabled; a blocked SMS "
        "request must not be treated as successful activation or purchase."
    )


class CompatibilityReportExporter:
    """Build deterministic JSON/TXT diagnostics from existing read-only analyzers."""

    def build(self, jar_path: str, runtime_report, activation_report) -> CompatibilityExport:
        target = getattr(runtime_report, "rg35xx", None)
        assessment = assess_startup_blocking(runtime_report, activation_report)
        reachable = [
            p for p in getattr(getattr(activation_report, "dependency", None), "activation_paths", [])
            if getattr(p, "startup_reachable", False) and getattr(p, "path", None)
        ]
        startup_path = list(max(reachable, key=lambda p: len(p.path)).path) if reachable else []

        return CompatibilityExport(
            generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            jar_name=Path(jar_path).name,
            jar_path=str(jar_path),
            midp_profile=str(getattr(runtime_report, "midp_profile", "unknown")),
            cldc_configuration=str(getattr(runtime_report, "cldc_configuration", "unknown")),
            compatibility_score=int(getattr(target, "score", getattr(runtime_report, "compatibility_score", 100))),
            runtime_risk=str(getattr(target, "risk", getattr(runtime_report, "runtime_risk", "low"))),
            detected_apis=sorted(getattr(runtime_report, "detected_apis", set()) or []),
            api_sources={k: sorted(v) for k, v in sorted((getattr(runtime_report, "api_sources", {}) or {}).items())},
            unsupported_apis=sorted(getattr(target, "unsupported", []) or []),
            conditional_apis=sorted(getattr(target, "conditional", []) or []),
            sms_targets=list(getattr(runtime_report, "sms_targets", []) or []),
            activation_risk=str(getattr(activation_report, "risk", "low")),
            activation_score=int(getattr(activation_report, "score", 0)),
            likely_activation_gate=bool(getattr(activation_report, "likely_activation_gate", False)),
            likely_payment_flow=bool(getattr(activation_report, "likely_payment_flow", False)),
            wma_linked=bool(getattr(activation_report, "wma_linked", False)),
            suspicious_classes=list(getattr(activation_report, "suspicious_classes", []) or []),
            suspicious_resources=list(getattr(activation_report, "suspicious_resources", []) or []),
            startup_reachable=bool(getattr(activation_report, "startup_activation_reachable", False)),
            startup_path=startup_path,
            startup_classification=assessment.classification,
            startup_severity=assessment.severity,
            startup_title=assessment.title,
            startup_reasons=list(assessment.reasons),
            recommendation=assessment.recommendation,
        )

    @staticmethod
    def to_json(report: CompatibilityExport) -> str:
        return json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    @staticmethod
    def to_text(report: CompatibilityExport) -> str:
        lines = [
            "JAR COMPATIBILITY REPORT",
            "=" * 72,
            f"JAR: {report.jar_name}",
            f"Target: {report.target}",
            f"Generated (UTC): {report.generated_at_utc}",
            "",
            "RUNTIME",
            f"MIDP: {report.midp_profile}",
            f"CLDC: {report.cldc_configuration}",
            f"Score: {report.compatibility_score}/100",
            f"Risk: {report.runtime_risk.upper()}",
            f"Detected APIs: {', '.join(report.detected_apis) or 'none'}",
            f"Unsupported APIs: {', '.join(report.unsupported_apis) or 'none'}",
            f"Conditional APIs: {', '.join(report.conditional_apis) or 'none'}",
            f"SMS endpoints: {', '.join(report.sms_targets) or 'none'}",
            "",
            "ACTIVATION / PAYMENT",
            f"Risk: {report.activation_risk.upper()} ({report.activation_score}/100)",
            f"Activation gate: {'yes' if report.likely_activation_gate else 'no'}",
            f"Payment flow: {'yes' if report.likely_payment_flow else 'no'}",
            f"WMA linked: {'yes' if report.wma_linked else 'no'}",
            f"Suspicious classes: {', '.join(report.suspicious_classes) or 'none'}",
            "",
            "STARTUP ASSESSMENT",
            f"Classification: {report.startup_classification}",
            f"Severity: {report.startup_severity.upper()}",
            f"Title: {report.startup_title}",
            f"Startup reachable: {'yes' if report.startup_reachable else 'no'}",
            "Path: " + (" -> ".join(report.startup_path) if report.startup_path else "not found"),
        ]
        if report.startup_reasons:
            lines.append("Reasons:")
            lines.extend(f"- {reason}" for reason in report.startup_reasons)
        lines.extend([
            f"Recommendation: {report.recommendation}",
            "",
            "SAFETY / INTERPRETATION",
            report.safety_note,
            "",
        ])
        return "\n".join(lines)

    def write_pair(self, base_path: str | Path, report: CompatibilityExport) -> tuple[Path, Path]:
        base = Path(base_path)
        if base.suffix.lower() in {".json", ".txt"}:
            base = base.with_suffix("")
        json_path = base.with_suffix(".compat.json")
        text_path = base.with_suffix(".compat.txt")
        json_path.write_text(self.to_json(report), encoding="utf-8")
        text_path.write_text(self.to_text(report), encoding="utf-8")
        return json_path, text_path
