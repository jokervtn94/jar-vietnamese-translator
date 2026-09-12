from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class CompareVerdict:
    label: str = "UNCHANGED"
    reasons: List[str] = field(default_factory=list)


def _value(report: Any, name: str, default=None):
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def _classification_rank(value: str) -> int:
    return {
        "compatible_or_unknown": 0,
        "needs_runtime_test": 1,
        "optional_feature_risk": 2,
        "runtime_only_incompatibility": 2,
        "likely_startup_blocker": 3,
    }.get(str(value or "unknown"), 1)


def build_compare_verdict(comparison, left_report: Any, right_report: Any) -> CompareVerdict:
    positive: List[str] = []
    negative: List[str] = []

    if comparison.score_delta > 0:
        positive.append(f"Compatibility score +{comparison.score_delta}")
    elif comparison.score_delta < 0:
        negative.append(f"Compatibility score {comparison.score_delta}")

    left_unsupported = set(_value(left_report, "unsupported_apis", []) or [])
    right_unsupported = set(_value(right_report, "unsupported_apis", []) or [])
    removed = sorted(left_unsupported - right_unsupported)
    added = sorted(right_unsupported - left_unsupported)
    if removed:
        positive.append("Unsupported APIs removed: " + ", ".join(removed))
    if added:
        negative.append("Unsupported APIs added: " + ", ".join(added))

    left_rank = _classification_rank(_value(left_report, "startup_classification", "unknown"))
    right_rank = _classification_rank(_value(right_report, "startup_classification", "unknown"))
    if right_rank < left_rank:
        positive.append("Startup classification risk reduced")
    elif right_rank > left_rank:
        negative.append("Startup classification risk increased")

    if positive and negative:
        return CompareVerdict("MIXED", positive + negative)
    if positive:
        return CompareVerdict("IMPROVED", positive)
    if negative:
        return CompareVerdict("REGRESSED", negative)
    return CompareVerdict("UNCHANGED", ["No material compatibility change detected"])


def format_compare_verdict(verdict: CompareVerdict) -> str:
    lines = [f"VERDICT: {verdict.label}"]
    lines.extend(f"- {reason}" for reason in verdict.reasons)
    return "\n".join(lines)
