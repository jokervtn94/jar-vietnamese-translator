from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
import re


ERROR_TYPES = (
    "ClassNotFoundException",
    "NoClassDefFoundError",
    "UnsupportedOperationException",
    "VerifyError",
    "SecurityException",
    "OutOfMemoryError",
    "NullPointerException",
    "IllegalArgumentException",
)

API_HINTS = {
    "javax.wireless.messaging": "wma_sms",
    "javax.microedition.m3g": "m3g",
    "javax.bluetooth": "bluetooth",
    "javax.microedition.io.file": "file_connection",
    "javax.microedition.media": "media",
    "com.nokia": "vendor_nokia",
    "com.samsung": "vendor_samsung",
    "com.siemens": "vendor_siemens",
    "com.sonyericsson": "vendor_sonyericsson",
    "com.motorola": "vendor_motorola",
}


@dataclass
class RuntimeLogFinding:
    error_type: str
    symbol: str = ""
    line: str = ""
    api_hint: str = ""
    severity: str = "medium"


@dataclass
class RuntimeLogCorrelation:
    findings: List[RuntimeLogFinding] = field(default_factory=list)
    matched_apis: List[str] = field(default_factory=list)
    matched_startup_classes: List[str] = field(default_factory=list)
    probable_cause: str = "No high-confidence runtime failure detected"
    recommendation: str = "Run another smoke test with a full FreeJ2ME log if the game still fails."


def load_log(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _value(report: Any, name: str, default=None):
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def _extract_symbol(line: str, error_type: str) -> str:
    tail = line.split(error_type, 1)[-1]
    tail = tail.lstrip(": ")
    token = re.split(r"[\s;,]", tail, maxsplit=1)[0] if tail else ""
    return token.replace("/", ".")


def _api_hint(text: str) -> str:
    normalized = text.replace("/", ".").lower()
    for prefix, api in API_HINTS.items():
        if prefix.lower() in normalized:
            return api
    return ""


def correlate_runtime_log(log_text: str, compatibility_report: Any | None = None) -> RuntimeLogCorrelation:
    findings: List[RuntimeLogFinding] = []
    seen = set()

    for raw in log_text.splitlines():
        line = raw.strip()
        for error_type in ERROR_TYPES:
            if error_type not in line:
                continue
            symbol = _extract_symbol(line, error_type)
            api = _api_hint(line + " " + symbol)
            severity = "high" if error_type in {
                "ClassNotFoundException",
                "NoClassDefFoundError",
                "VerifyError",
                "OutOfMemoryError",
            } else "medium"
            key = (error_type, symbol, line)
            if key not in seen:
                seen.add(key)
                findings.append(RuntimeLogFinding(error_type, symbol, line, api, severity))

    report_apis = set(_value(compatibility_report, "detected_apis", []) or []) if compatibility_report else set()
    matched_apis = sorted({f.api_hint for f in findings if f.api_hint and (not report_apis or f.api_hint in report_apis)})

    startup_path = _value(compatibility_report, "startup_path", []) or [] if compatibility_report else []
    startup_classes = {str(item).replace("/", ".") for item in startup_path}
    matched_startup = sorted({
        cls for cls in startup_classes
        if any(cls and cls in (f.line.replace("/", ".") + " " + f.symbol) for f in findings)
    })

    if any(f.error_type in {"ClassNotFoundException", "NoClassDefFoundError"} for f in findings):
        missing = next((f.symbol for f in findings if f.error_type in {"ClassNotFoundException", "NoClassDefFoundError"} and f.symbol), "required class")
        cause = f"Runtime cannot resolve required class: {missing}"
        recommendation = "Check whether the target runtime provides the referenced API/class and compare it with the compatibility report before rebuilding the JAR."
    elif any(f.error_type == "VerifyError" for f in findings):
        cause = "Bytecode verification failed on the target runtime"
        recommendation = "Inspect the reported class and Java ME profile assumptions; rebuild without unsafe bytecode changes and retest."
    elif any(f.error_type == "UnsupportedOperationException" for f in findings):
        cause = "A runtime operation is present but unsupported by the target environment"
        recommendation = "Correlate the failing operation with detected APIs and test a runtime/build that supports that feature."
    elif any(f.error_type == "OutOfMemoryError" for f in findings):
        cause = "The runtime ran out of memory during execution"
        recommendation = "Reduce memory pressure where possible and retest with an appropriate heap/runtime configuration."
    elif findings:
        cause = f"Runtime exception detected: {findings[0].error_type}"
        recommendation = "Inspect the first exception and its stack trace together with the detected startup path."
    else:
        cause = "No high-confidence runtime failure detected"
        recommendation = "Run another smoke test with a full FreeJ2ME log if the game still fails."

    if matched_startup:
        recommendation += " The failure intersects the static startup path: " + " -> ".join(matched_startup) + "."
    if matched_apis:
        recommendation += " Related detected APIs: " + ", ".join(matched_apis) + "."

    return RuntimeLogCorrelation(
        findings=findings,
        matched_apis=matched_apis,
        matched_startup_classes=matched_startup,
        probable_cause=cause,
        recommendation=recommendation,
    )


def format_runtime_log_correlation(result: RuntimeLogCorrelation) -> str:
    lines = [
        "FREEJ2ME RUNTIME LOG CORRELATION",
        f"Probable cause: {result.probable_cause}",
        f"Matched APIs: {', '.join(result.matched_apis) or 'none'}",
        f"Startup classes: {' -> '.join(result.matched_startup_classes) or 'none'}",
        f"Recommendation: {result.recommendation}",
        "",
        "Findings:",
    ]
    if not result.findings:
        lines.append("- none")
    else:
        for finding in result.findings[:20]:
            detail = f" · {finding.symbol}" if finding.symbol else ""
            api = f" · API={finding.api_hint}" if finding.api_hint else ""
            lines.append(f"- [{finding.severity.upper()}] {finding.error_type}{detail}{api}")
    return "\n".join(lines)
