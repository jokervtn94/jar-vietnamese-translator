from __future__ import annotations

import json

from core.diagnostic_compare import compare_reports, format_comparison, load_report


def _report(name, score, apis, classification, path, action_title):
    return {
        "jar_name": name,
        "compatibility_score": score,
        "detected_apis": apis,
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
        assert "format_comparison(comparison)" in text
        assert "load_report(left_entry.json_path)" in text
