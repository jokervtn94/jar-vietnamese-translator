from __future__ import annotations

import json

from core.diagnostic_compare import compare_reports, format_comparison, load_report
from core.diagnostic_verdict import build_compare_verdict, format_compare_verdict


def _report(name, score, apis, classification, path, action_title, unsupported=None):
    return {
        "jar_name": name,
        "compatibility_score": score,
        "detected_apis": apis,
        "unsupported_apis": unsupported or [],
        "startup_classification": classification,
        "startup_path": path,
        "recommended_actions": [
            {
                "priority": 1,
                "category": "diagnostic",
                "title": action_title,
                "detail": "detail",
            }
        ],
    }


def test_compare_reports_tracks_score_api_startup_and_action_changes():
    old = _report(
        "old.jar",
        60,
        ["m3g", "wma_sms"],
        "likely_startup_blocker",
        ["game.Main", "game.Check"],
        "Kiểm tra startup path",
    )
    new = _report(
        "new.jar",
        82,
        ["m3g", "file_connection"],
        "needs_runtime_test",
        ["game.Main"],
        "Kiểm thử runtime",
    )

    result = compare_reports(old, new)

    assert result.score_delta == 22
    assert result.added_apis == ["file_connection"]
    assert result.removed_apis == ["wma_sms"]
    assert result.classification_changed is True
    assert result.startup_path_changed is True
    assert result.next_action_changed is True

    text = format_comparison(result)
    assert "Score delta: +22" in text
    assert "APIs added: file_connection" in text
    assert "APIs removed: wma_sms" in text
    assert "likely_startup_blocker -> needs_runtime_test" in text
    assert "game.Main -> game.Check" in text
    assert "Kiểm thử runtime" in text


def test_compare_verdict_improved():
    old = _report("old.jar", 60, ["wma_sms"], "likely_startup_blocker", [], "A", ["wma_sms"])
    new = _report("new.jar", 82, [], "needs_runtime_test", [], "B", [])
    comparison = compare_reports(old, new)
    verdict = build_compare_verdict(comparison, old, new)
    assert verdict.label == "IMPROVED"
    assert "Compatibility score +22" in verdict.reasons
    assert any("Unsupported APIs removed" in reason for reason in verdict.reasons)
    assert any("risk reduced" in reason for reason in verdict.reasons)
    assert "VERDICT: IMPROVED" in format_compare_verdict(verdict)


def test_compare_verdict_regressed():
    old = _report("old.jar", 90, [], "compatible_or_unknown", [], "A", [])
    new = _report("new.jar", 65, ["vendor_nokia"], "likely_startup_blocker", [], "B", ["vendor_nokia"])
    verdict = build_compare_verdict(compare_reports(old, new), old, new)
    assert verdict.label == "REGRESSED"
    assert any("Compatibility score -25" in reason for reason in verdict.reasons)
    assert any("Unsupported APIs added" in reason for reason in verdict.reasons)
    assert any("risk increased" in reason for reason in verdict.reasons)


def test_compare_verdict_mixed_and_unchanged():
    old = _report("old.jar", 70, [], "needs_runtime_test", [], "A", ["legacy_api"])
    mixed_new = _report("mixed.jar", 80, ["vendor_api"], "needs_runtime_test", [], "B", ["vendor_api"])
    mixed = build_compare_verdict(compare_reports(old, mixed_new), old, mixed_new)
    assert mixed.label == "MIXED"

    same = _report("same.jar", 70, [], "needs_runtime_test", [], "A", ["legacy_api"])
    unchanged = build_compare_verdict(compare_reports(old, same), old, same)
    assert unchanged.label == "UNCHANGED"


def test_load_report_reads_exported_json(tmp_path):
    path = tmp_path / "sample.compat.json"
    payload = _report("sample.jar", 91, ["m3g"], "needs_runtime_test", [], "Runtime test")
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_report(path)

    assert loaded["jar_name"] == "sample.jar"
    assert loaded["compatibility_score"] == 91


def test_compare_hook_contract_is_present_without_importing_qt():
    source = open("gui/diagnostic_compare_hook.py", encoding="utf-8").read()
    portable = open("app/gui/diagnostic_compare_hook.py", encoding="utf-8").read()

    for text in (source, portable):
        assert 'QLabel("Diagnostic Compare")' in text
        assert 'QPushButton("Compare reports")' in text
        assert "compare_reports(left, right)" in text
        assert "build_compare_verdict(comparison, left, right)" in text
        assert "format_compare_verdict(verdict)" in text
        assert "format_comparison(comparison)" in text
        assert "load_report(left_entry.json_path)" in text
