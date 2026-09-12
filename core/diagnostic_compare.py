from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
import json


STARTUP_BLOCKER = "likely_startup_blocker"


@dataclass
class DiagnosticComparison:
    left_name: str = ""
    right_name: str = ""
    score_delta: int = 0
    added_apis: List[str] = field(default_factory=list)
    removed_apis: List[str] = field(default_factory=list)
    added_unsupported_apis: List[str] = field(default_factory=list)
    removed_unsupported_apis: List[str] = field(default_factory=list)
    classification_changed: bool = False
    left_classification: str = ""
    right_classification: str = ""
    startup_path_changed: bool = False
    left_startup_path: str = ""
    right_startup_path: str = ""
    next_action_changed: bool = False
    left_next_action: str = ""
    right_next_action: str = ""
    verdict: str = "UNCHANGED"
    verdict_reasons: List[str] = field(default_factory=list)


def load_report(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Compatibility report JSON must contain an object")
    return data


def _value(report: Any, name: str, default=None):
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def _top_action(report: Any) -> str:
    actions = _value(report, "recommended_actions", []) or []
    if not actions:
        return "none"
    top = actions[0]
    if isinstance(top, dict):
        priority = top.get("priority", "?")
        title = top.get("title", "")
        detail = top.get("detail", "")
    else:
        priority = getattr(top, "priority", "?")
        title = getattr(top, "title", "")
        detail = getattr(top, "detail", "")
    return f"P{priority} · {title}" + (f" · {detail}" if detail else "")


def _verdict(
    score_delta: int,
    added_unsupported: List[str],
    removed_unsupported: List[str],
    left_class: str,
    right_class: str,
) -> tuple[str, List[str]]:
    positive: List[str] = []
    negative: List[str] = []

    if score_delta > 0:
        positive.append(f"Compatibility score tăng {score_delta} điểm")
    elif score_delta < 0:
        negative.append(f"Compatibility score giảm {abs(score_delta)} điểm")

    if removed_unsupported:
        positive.append("Unsupported API đã giảm: " + ", ".join(removed_unsupported))
    if added_unsupported:
        negative.append("Phát sinh unsupported API: " + ", ".join(added_unsupported))

    left_blocked = left_class == STARTUP_BLOCKER
    right_blocked = right_class == STARTUP_BLOCKER
    if left_blocked and not right_blocked:
        positive.append("Startup blocker đã được gỡ khỏi phân loại tĩnh")
    elif not left_blocked and right_blocked:
        negative.append("Xuất hiện startup blocker mới trong phân loại tĩnh")

    if positive and negative:
        return "MIXED", positive + negative
    if positive:
        return "IMPROVED", positive
    if negative:
        return "REGRESSED", negative
    return "UNCHANGED", ["Không có thay đổi đủ mạnh để đổi verdict"]


def compare_reports(left: Any, right: Any) -> DiagnosticComparison:
    left_apis = set(_value(left, "detected_apis", []) or [])
    right_apis = set(_value(right, "detected_apis", []) or [])
    left_unsupported = set(_value(left, "unsupported_apis", []) or [])
    right_unsupported = set(_value(right, "unsupported_apis", []) or [])

    left_path = " -> ".join(_value(left, "startup_path", []) or []) or "not found"
    right_path = " -> ".join(_value(right, "startup_path", []) or []) or "not found"
    left_class = str(_value(left, "startup_classification", "unknown"))
    right_class = str(_value(right, "startup_classification", "unknown"))
    left_action = _top_action(left)
    right_action = _top_action(right)
    score_delta = int(_value(right, "compatibility_score", 0) or 0) - int(
        _value(left, "compatibility_score", 0) or 0
    )
    added_unsupported = sorted(right_unsupported - left_unsupported)
    removed_unsupported = sorted(left_unsupported - right_unsupported)
    verdict, verdict_reasons = _verdict(
        score_delta,
        added_unsupported,
        removed_unsupported,
        left_class,
        right_class,
    )

    return DiagnosticComparison(
        left_name=str(_value(left, "jar_name", "left")),
        right_name=str(_value(right, "jar_name", "right")),
        score_delta=score_delta,
        added_apis=sorted(right_apis - left_apis),
        removed_apis=sorted(left_apis - right_apis),
        added_unsupported_apis=added_unsupported,
        removed_unsupported_apis=removed_unsupported,
        classification_changed=left_class != right_class,
        left_classification=left_class,
        right_classification=right_class,
        startup_path_changed=left_path != right_path,
        left_startup_path=left_path,
        right_startup_path=right_path,
        next_action_changed=left_action != right_action,
        left_next_action=left_action,
        right_next_action=right_action,
        verdict=verdict,
        verdict_reasons=verdict_reasons,
    )


def format_comparison(compare: DiagnosticComparison) -> str:
    delta = f"{compare.score_delta:+d}"
    lines = [
        f"VERDICT: {compare.verdict}",
        *[f"- {reason}" for reason in compare.verdict_reasons],
        "",
        "RG35XX DIAGNOSTIC COMPARE",
        f"{compare.left_name} -> {compare.right_name}",
        f"Score delta: {delta}",
        f"APIs added: {', '.join(compare.added_apis) or 'none'}",
        f"APIs removed: {', '.join(compare.removed_apis) or 'none'}",
        f"Unsupported added: {', '.join(compare.added_unsupported_apis) or 'none'}",
        f"Unsupported removed: {', '.join(compare.removed_unsupported_apis) or 'none'}",
        (
            f"Classification: {compare.left_classification} -> {compare.right_classification}"
            if compare.classification_changed
            else f"Classification: unchanged ({compare.right_classification})"
        ),
        (
            "Startup path:\n"
            f"  A: {compare.left_startup_path}\n"
            f"  B: {compare.right_startup_path}"
            if compare.startup_path_changed
            else f"Startup path: unchanged ({compare.right_startup_path})"
        ),
        (
            "Next action:\n"
            f"  A: {compare.left_next_action}\n"
            f"  B: {compare.right_next_action}"
            if compare.next_action_changed
            else f"Next action: unchanged ({compare.right_next_action})"
        ),
    ]
    return "\n".join(lines)
