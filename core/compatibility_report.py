from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import json

from core.startup_blocking_assessment import assess_startup_blocking


@dataclass
class RecommendedAction:
    priority: int
    category: str
    title: str
    detail: str


@dataclass
class CompatibilityExport:
    schema: str = "jar-translator.compatibility-report.v1"
    generated_at_utc: str = ""
    jar_name: str = ""
    target: str = "FreeJ2ME / RG35XX"
    midp_profile: str = "unknown"
    cldc_configuration: str = "unknown"
    compatibility_score: int = 100
    runtime_risk: str = "low"
    detected_apis: List[str] = field(default_factory=list)
    api_sources: Dict[str, List[str]] = field(default_factory=dict)
    unsupported_apis: List[str] = field(default_factory=list)
    conditional_apis: List[str] = field(default_factory=list)
    messaging_endpoints: List[str] = field(default_factory=list)
    legacy_flow_risk: str = "low"
    legacy_flow_score: int = 0
    suspicious_classes: List[str] = field(default_factory=list)
    suspicious_resources: List[str] = field(default_factory=list)
    startup_reachable: bool = False
    startup_path: List[str] = field(default_factory=list)
    startup_classification: str = "compatible_or_unknown"
    startup_severity: str = "low"
    startup_title: str = "Không thấy blocker startup rõ ràng"
    startup_reasons: List[str] = field(default_factory=list)
    recommendation: str = ""
    recommended_actions: List[RecommendedAction] = field(default_factory=list)
    diagnostic_note: str = "Read-only diagnostic output; no external transport or application state changes are performed."


def _action_value(action, name: str, default=""):
    if isinstance(action, dict):
        return action.get(name, default)
    return getattr(action, name, default)


def format_recommended_action(action) -> str:
    if action is None:
        return ""
    priority = _action_value(action, "priority", 4)
    title = _action_value(action, "title", "")
    detail = _action_value(action, "detail", "")
    text = f"P{priority} · {title}".rstrip()
    return text + ((" · " + detail) if detail else "")


def diagnostic_summary(report: CompatibilityExport) -> str:
    top = report.recommended_actions[0] if report.recommended_actions else None
    path = " -> ".join(report.startup_path) if report.startup_path else "not found"
    lines = [
        "JAR RG35XX DIAGNOSTIC SUMMARY",
        f"JAR: {report.jar_name}",
        f"Target: {report.target}",
        f"Runtime: {report.compatibility_score}/100 · {report.runtime_risk.upper()}",
        f"Assessment: {report.startup_title} · {report.startup_severity.upper()}",
        f"Detected APIs: {', '.join(report.detected_apis) or 'none'}",
        f"Unsupported APIs: {', '.join(report.unsupported_apis) or 'none'}",
        f"Conditional APIs: {', '.join(report.conditional_apis) or 'none'}",
        f"Startup path: {path}",
    ]
    if top is not None:
        lines.append("Next action: " + format_recommended_action(top))
    lines.append(report.diagnostic_note)
    return "\n".join(lines)


class CompatibilityReportExporter:
    @staticmethod
    def _recommended_actions(runtime_report, flow_report, startup_path: List[str]) -> List[RecommendedAction]:
        target = getattr(runtime_report, "rg35xx", None)
        unsupported = sorted(getattr(target, "unsupported", []) or []) if target is not None else []
        conditional = sorted(getattr(target, "conditional", []) or []) if target is not None else []
        suspicious = list(getattr(flow_report, "suspicious_classes", []) or [])
        actions: List[RecommendedAction] = []

        if startup_path:
            actions.append(RecommendedAction(
                1,
                "startup_path",
                "Kiểm tra class trên startup path",
                " -> ".join(startup_path),
            ))
        if unsupported:
            actions.append(RecommendedAction(
                2 if startup_path else 1,
                "unsupported_api",
                "Kiểm tra API chưa được target runtime hỗ trợ",
                ", ".join(unsupported),
            ))
        if suspicious and not startup_path:
            actions.append(RecommendedAction(
                2,
                "suspicious_class",
                "Kiểm tra class nghi vấn",
                ", ".join(suspicious[:5]),
            ))
        if conditional:
            actions.append(RecommendedAction(
                3,
                "conditional_api",
                "Kiểm thử API conditional trực tiếp trên RG35XX",
                ", ".join(conditional),
            ))
        if not actions:
            actions.append(RecommendedAction(
                4,
                "runtime_test",
                "Chạy kiểm thử thực tế trên FreeJ2ME / RG35XX",
                "Không có blocker tĩnh rõ ràng; xác nhận hành vi bằng runtime test.",
            ))
        return sorted(actions, key=lambda item: (item.priority, item.category, item.title))

    def build(self, jar_path: str, runtime_report, flow_report) -> CompatibilityExport:
        target = getattr(runtime_report, "rg35xx", None)
        assessment = assess_startup_blocking(runtime_report, flow_report)
        dependency = getattr(flow_report, "dependency", None)
        reachable = [
            p for p in getattr(dependency, "activation_paths", [])
            if getattr(p, "startup_reachable", False) and getattr(p, "path", None)
        ]
        startup_path = list(max(reachable, key=lambda p: len(p.path)).path) if reachable else []
        actions = self._recommended_actions(runtime_report, flow_report, startup_path)
        return CompatibilityExport(
            generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            jar_name=Path(jar_path).name,
            midp_profile=str(getattr(runtime_report, "midp_profile", "unknown")),
            cldc_configuration=str(getattr(runtime_report, "cldc_configuration", "unknown")),
            compatibility_score=int(getattr(target, "score", getattr(runtime_report, "compatibility_score", 100))),
            runtime_risk=str(getattr(target, "risk", getattr(runtime_report, "runtime_risk", "low"))),
            detected_apis=sorted(getattr(runtime_report, "detected_apis", set()) or []),
            api_sources={k: sorted(v) for k, v in sorted((getattr(runtime_report, "api_sources", {}) or {}).items())},
            unsupported_apis=sorted(getattr(target, "unsupported", []) or []),
            conditional_apis=sorted(getattr(target, "conditional", []) or []),
            messaging_endpoints=list(getattr(runtime_report, "sms_targets", []) or []),
            legacy_flow_risk=str(getattr(flow_report, "risk", "low")),
            legacy_flow_score=int(getattr(flow_report, "score", 0)),
            suspicious_classes=list(getattr(flow_report, "suspicious_classes", []) or []),
            suspicious_resources=list(getattr(flow_report, "suspicious_resources", []) or []),
            startup_reachable=bool(getattr(flow_report, "startup_activation_reachable", False)),
            startup_path=startup_path,
            startup_classification=assessment.classification,
            startup_severity=assessment.severity,
            startup_title=assessment.title,
            startup_reasons=list(assessment.reasons),
            recommendation=assessment.recommendation,
            recommended_actions=actions,
        )

    @staticmethod
    def to_json(report: CompatibilityExport) -> str:
        return json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"

    @staticmethod
    def to_text(report: CompatibilityExport) -> str:
        lines = [
            "JAR COMPATIBILITY REPORT",
            "=" * 72,
            f"JAR: {report.jar_name}",
            f"Target: {report.target}",
            f"Generated (UTC): {report.generated_at_utc}",
            "",
            f"MIDP: {report.midp_profile}",
            f"CLDC: {report.cldc_configuration}",
            f"Runtime score: {report.compatibility_score}/100",
            f"Runtime risk: {report.runtime_risk.upper()}",
            f"Detected APIs: {', '.join(report.detected_apis) or 'none'}",
            f"Unsupported APIs: {', '.join(report.unsupported_apis) or 'none'}",
            f"Conditional APIs: {', '.join(report.conditional_apis) or 'none'}",
            f"Messaging endpoints: {', '.join(report.messaging_endpoints) or 'none'}",
            "",
            f"Legacy flow risk: {report.legacy_flow_risk.upper()} ({report.legacy_flow_score}/100)",
            f"Suspicious classes: {', '.join(report.suspicious_classes) or 'none'}",
            f"Startup classification: {report.startup_classification}",
            f"Startup severity: {report.startup_severity.upper()}",
            f"Startup reachable: {'yes' if report.startup_reachable else 'no'}",
            "Startup path: " + (" -> ".join(report.startup_path) if report.startup_path else "not found"),
            f"Recommendation: {report.recommendation}",
            "",
            "RECOMMENDED ACTIONS",
        ]
        for action in report.recommended_actions:
            lines.append(format_recommended_action(action))
        lines.extend(["", report.diagnostic_note, ""])
        return "\n".join(lines)

    def write_pair(self, base_path: str | Path, report: CompatibilityExport):
        base = Path(base_path)
        if base.suffix:
            base = base.with_suffix("")
        json_path = base.with_suffix(".compat.json")
        text_path = base.with_suffix(".compat.txt")
        json_path.write_text(self.to_json(report), encoding="utf-8")
        text_path.write_text(self.to_text(report), encoding="utf-8")
        return json_path, text_path
