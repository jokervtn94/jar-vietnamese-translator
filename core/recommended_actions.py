from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RecommendedAction:
    priority: int
    category: str
    title: str
    detail: str


def build_recommended_actions(runtime_report, flow_report, assessment) -> List[RecommendedAction]:
    """Create read-only diagnostic next steps ordered by practical value."""
    actions: List[RecommendedAction] = []
    target = getattr(runtime_report, "rg35xx", None)
    unsupported = list(getattr(target, "unsupported", []) or []) if target is not None else []
    conditional = list(getattr(target, "conditional", []) or []) if target is not None else []

    dependency = getattr(flow_report, "dependency", None)
    reachable = [
        p for p in getattr(dependency, "activation_paths", [])
        if getattr(p, "startup_reachable", False) and getattr(p, "path", None)
    ]
    deepest = max(reachable, key=lambda p: len(p.path), default=None)

    if deepest is not None:
        actions.append(RecommendedAction(
            1,
            "startup_path",
            "Kiểm tra class trên startup path",
            " -> ".join(deepest.path),
        ))

    if unsupported:
        actions.append(RecommendedAction(
            1 if deepest is None else 2,
            "unsupported_api",
            "Kiểm tra API chưa được target runtime hỗ trợ",
            ", ".join(sorted(unsupported)),
        ))

    suspicious = list(getattr(flow_report, "suspicious_classes", []) or [])
    if suspicious and deepest is None:
        actions.append(RecommendedAction(
            2,
            "suspicious_class",
            "Kiểm tra class legacy-flow nghi vấn",
            ", ".join(suspicious[:5]),
        ))

    if conditional:
        actions.append(RecommendedAction(
            3,
            "conditional_api",
            "Kiểm thử API conditional trực tiếp trên RG35XX",
            ", ".join(sorted(conditional)),
        ))

    if not actions:
        actions.append(RecommendedAction(
            4,
            "runtime_test",
            "Chạy kiểm thử thực tế trên FreeJ2ME / RG35XX",
            "Không có blocker tĩnh rõ ràng; xác nhận hành vi bằng runtime test.",
        ))

    actions.sort(key=lambda item: (item.priority, item.category, item.title))
    return actions
