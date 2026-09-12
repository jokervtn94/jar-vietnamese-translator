from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CompareRecommendation:
    title: str
    detail: str


def _value(report: Any, name: str, default=None):
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def _rank(value: str) -> int:
    return {
        "compatible_or_unknown": 0,
        "needs_runtime_test": 1,
        "optional_feature_risk": 2,
        "runtime_only_incompatibility": 2,
        "likely_startup_blocker": 3,
    }.get(str(value or "unknown"), 1)


def build_compare_recommendation(comparison, verdict, left_report: Any, right_report: Any) -> CompareRecommendation:
    left_unsupported = set(_value(left_report, "unsupported_apis", []) or [])
    right_unsupported = set(_value(right_report, "unsupported_apis", []) or [])
    added_unsupported = sorted(right_unsupported - left_unsupported)
    removed_unsupported = sorted(left_unsupported - right_unsupported)

    left_rank = _rank(_value(left_report, "startup_classification", "unknown"))
    right_rank = _rank(_value(right_report, "startup_classification", "unknown"))

    if verdict.label == "REGRESSED":
        if added_unsupported:
            return CompareRecommendation(
                "Ưu tiên kiểm tra API mới phát sinh",
                ", ".join(added_unsupported),
            )
        if right_rank > left_rank:
            return CompareRecommendation(
                "Ưu tiên kiểm tra thay đổi startup",
                f"{_value(left_report, 'startup_classification', 'unknown')} -> {_value(right_report, 'startup_classification', 'unknown')}",
            )
        return CompareRecommendation(
            "Ưu tiên xem lại thay đổi làm giảm compatibility score",
            f"Score delta {comparison.score_delta:+d}",
        )

    if verdict.label == "IMPROVED":
        if removed_unsupported:
            return CompareRecommendation(
                "Cải thiện chính: API không tương thích đã giảm",
                ", ".join(removed_unsupported),
            )
        if right_rank < left_rank:
            return CompareRecommendation(
                "Cải thiện chính: startup classification tốt hơn",
                f"{_value(left_report, 'startup_classification', 'unknown')} -> {_value(right_report, 'startup_classification', 'unknown')}",
            )
        return CompareRecommendation(
            "Cải thiện chính: compatibility score tăng",
            f"Score delta {comparison.score_delta:+d}",
        )

    if verdict.label == "MIXED":
        if added_unsupported:
            detail = "Rủi ro mới: " + ", ".join(added_unsupported)
            if removed_unsupported:
                detail += " · Cải thiện: " + ", ".join(removed_unsupported)
            return CompareRecommendation("Kết quả trái chiều · ưu tiên phần rủi ro", detail)
        if right_rank > left_rank:
            return CompareRecommendation(
                "Kết quả trái chiều · ưu tiên kiểm tra startup",
                f"Score delta {comparison.score_delta:+d}",
            )
        return CompareRecommendation(
            "Kết quả trái chiều · cần xem diff chi tiết",
            f"Score delta {comparison.score_delta:+d}",
        )

    return CompareRecommendation(
        "Không có thay đổi đáng kể",
        "Tiếp tục runtime smoke test trên FreeJ2ME / RG35XX để xác nhận hành vi thực tế.",
    )


def format_compare_recommendation(recommendation: CompareRecommendation) -> str:
    return f"RECOMMENDATION: {recommendation.title}\n- {recommendation.detail}"
