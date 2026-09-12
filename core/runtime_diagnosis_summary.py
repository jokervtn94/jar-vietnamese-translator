from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class RuntimeDiagnosisSummary:
    log_name: str = ""
    probable_cause: str = ""
    primary_exception: str = "none"
    root_exception: str = "none"
    failing_path: List[str] = field(default_factory=list)
    matched_apis: List[str] = field(default_factory=list)
    startup_overlap: List[str] = field(default_factory=list)
    recommendation: str = ""
    exception_count: int = 0
    high_severity_count: int = 0


def build_runtime_diagnosis_summary(log_path, correlation, timeline) -> RuntimeDiagnosisSummary:
    primary = timeline.primary
    root = timeline.root
    startup_overlap: List[str] = []
    if primary is not None:
        startup_overlap = list(primary.startup_overlap)
    if not startup_overlap:
        startup_overlap = list(getattr(correlation, "matched_startup_classes", []) or [])

    return RuntimeDiagnosisSummary(
        log_name=Path(log_path).name if log_path else "",
        probable_cause=str(getattr(correlation, "probable_cause", "") or ""),
        primary_exception=(primary.error_type if primary is not None else "none"),
        root_exception=(root.error_type if root is not None else "none"),
        failing_path=list(getattr(correlation, "probable_failing_path", []) or []),
        matched_apis=list(getattr(correlation, "matched_apis", []) or []),
        startup_overlap=startup_overlap,
        recommendation=str(getattr(correlation, "recommendation", "") or ""),
        exception_count=len(timeline.events),
        high_severity_count=sum(1 for event in timeline.events if event.severity == "high"),
    )


def format_runtime_diagnosis_summary(summary: RuntimeDiagnosisSummary) -> str:
    return "\n".join([
        "FREEJ2ME / RG35XX RUNTIME DIAGNOSIS",
        f"Log: {summary.log_name or 'unknown'}",
        f"Probable cause: {summary.probable_cause or 'unknown'}",
        f"Primary exception: {summary.primary_exception}",
        f"Root exception: {summary.root_exception}",
        f"Failing path: {' -> '.join(summary.failing_path) or 'not available'}",
        f"Matched APIs: {', '.join(summary.matched_apis) or 'none'}",
        f"Startup overlap: {' -> '.join(summary.startup_overlap) or 'none'}",
        f"Exception count: {summary.exception_count}",
        f"High severity: {summary.high_severity_count}",
        f"Recommendation: {summary.recommendation or 'No recommendation available.'}",
    ])


def write_runtime_diagnosis_summary(log_path, summary: RuntimeDiagnosisSummary) -> Path:
    source = Path(log_path)
    target = source.with_name(source.stem + ".runtime-diagnosis.txt")
    target.write_text(format_runtime_diagnosis_summary(summary) + "\n", encoding="utf-8")
    return target
