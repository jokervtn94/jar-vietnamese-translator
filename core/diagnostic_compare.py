from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DiagnosticComparison:
    left_name: str = ""
    right_name: str = ""
    score_delta: int = 0
    added_apis: List[str] = field(default_factory=list)
    removed_apis: List[str] = field(default_factory=list)
    classification_changed: bool = False
    left_classification: str = ""
    right_classification: str = ""
    startup_path_changed: bool = False
    left_startup_path: str = ""
    right_startup_path: str = ""
    next_action_changed: bool = False
    left_next_action: str = ""
    right_next_action: str = ""


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


def compare_reports(left: Any, right: Any) -> DiagnosticComparison:
    left_apis = set(_value(left, "detected_apis", []) or [])
    right_apis = set(_value(right, "detected_apis", []) or [])

    left_path = " -> ".join(_value(left, "startup_path", []) or []) or "not found"
    right_path = " -> ".join(_value(right, "startup_path", []) or []) or "not found"
    left_class = str(_value(left, "startup_classification", "unknown"))
    right_class = str(_value(right, "startup_classification", "unknown"))
    left_action = _top_action(left)
    right_action = _top_action(right)

    return DiagnosticComparison(
        left_name=str(_value(left, "jar_name", "left")),
        right_name=str(_value(right, "jar_name", "right")),
        score_delta=int(_value(right, "compatibility_score", 0) or 0)
        - int(_value(left, "compatibility_score", 0) or 0),
        added_apis=sorted(right_apis - left_apis),
        removed_apis=sorted(left_apis - right_apis),
        classification_changed=left_class != right_class,
        left_classification=left_class,
        right_classification=right_class,
        startup_path_changed=left_path != right_path,
        left_startup_path=left_path,
        right_startup_path=right_path,
        next_action_changed=left_action != right_action,
        left_next_action=left_action,
        right_next_action=right_action,
    )


def format_comparison(compare: DiagnosticComparison) -> str:
    delta = f"{compare.score_delta:+d}"
    lines = [
        "RG35XX DIAGNOSTIC COMPARE",
        f"{compare.left_name} -> {compare.right_name}",
        f"Score delta: {delta}",
        f"APIs added: {', '.join(compare.added_apis) or 'none'}",
        f"APIs removed: {', '.join(compare.removed_apis) or 'none'}",
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
