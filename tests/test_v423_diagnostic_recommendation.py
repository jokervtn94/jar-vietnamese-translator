from __future__ import annotations

from core.diagnostic_compare import compare_reports
from core.diagnostic_recommendation import (
    build_compare_recommendation,
    format_compare_recommendation,
)
from core.diagnostic_verdict import build_compare_verdict


def _report(name, score, unsupported, classification):
    return {
        "jar_name": name,
        "compatibility_score": score,
        "detected_apis": list(unsupported),
        "unsupported_apis": list(unsupported),
        "startup_classification": classification,
        "startup_path": ["game.Main"],
        "recommended_actions": [],
    }


def _recommend(left, right):
    comparison = compare_reports(left, right)
    verdict = build_compare_verdict(comparison, left, right)
    return verdict, build_compare_recommendation(comparison, verdict, left, right)


def test_regressed_prioritizes_new_unsupported_api():
    left = _report("old.jar", 90, [], "needs_runtime_test")
    right = _report("new.jar", 70, ["vendor_nokia"], "needs_runtime_test")
    verdict, recommendation = _recommend(left, right)

    assert verdict.label == "REGRESSED"
    assert "API" in recommendation.title
    assert "vendor_nokia" in recommendation.detail


def test_improved_highlights_removed_unsupported_api():
    left = _report("old.jar", 60, ["wma_sms"], "likely_startup_blocker")
    right = _report("new.jar", 85, [], "needs_runtime_test")
    verdict, recommendation = _recommend(left, right)

    assert verdict.label == "IMPROVED"
    assert "Cải thiện chính" in recommendation.title
    assert "wma_sms" in recommendation.detail


def test_mixed_prioritizes_risk_signal():
    left = _report("old.jar", 70, ["legacy_a"], "needs_runtime_test")
    right = _report("new.jar", 82, ["legacy_b"], "needs_runtime_test")
    verdict, recommendation = _recommend(left, right)

    assert verdict.label == "MIXED"
    assert "ưu tiên phần rủi ro" in recommendation.title
    assert "legacy_b" in recommendation.detail
    assert "legacy_a" in recommendation.detail


def test_unchanged_recommends_runtime_smoke_test():
    left = _report("old.jar", 80, [], "needs_runtime_test")
    right = _report("new.jar", 80, [], "needs_runtime_test")
    verdict, recommendation = _recommend(left, right)

    assert verdict.label == "UNCHANGED"
    assert "Không có thay đổi đáng kể" in recommendation.title
    text = format_compare_recommendation(recommendation)
    assert "RECOMMENDATION:" in text
    assert "runtime smoke test" in text


def test_compare_ui_includes_recommendation_without_importing_qt():
    for path in ("gui/diagnostic_compare_hook.py", "app/gui/diagnostic_compare_hook.py"):
        source = open(path, encoding="utf-8").read()
        assert "build_compare_recommendation(comparison, verdict, left, right)" in source
        assert "format_compare_recommendation(recommendation)" in source
        assert "recommendation.title" in source
