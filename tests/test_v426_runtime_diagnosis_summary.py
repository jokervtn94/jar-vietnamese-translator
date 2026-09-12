from __future__ import annotations

from core.runtime_log_correlator import correlate_runtime_log
from core.runtime_exception_timeline import build_exception_timeline
from core.runtime_diagnosis_summary import (
    build_runtime_diagnosis_summary,
    format_runtime_diagnosis_summary,
    write_runtime_diagnosis_summary,
)


def _sample_log():
    return """
java.lang.IllegalArgumentException: wrapper
    at game.Manager.activate(Manager.java:88)
    at game.MainMIDlet.startApp(MainMIDlet.java:10)
Caused by: java.lang.NoClassDefFoundError: javax/wireless/messaging/MessageConnection
    at game.sms.SmsService.open(SmsService.java:31)
    at game.Manager.activate(Manager.java:88)
"""


def test_runtime_diagnosis_summary_uses_primary_root_path_and_api(tmp_path):
    log = _sample_log()
    report = {
        "detected_apis": ["wma_sms"],
        "startup_path": ["game.MainMIDlet", "game.Manager", "game.sms.SmsService"],
    }
    correlation = correlate_runtime_log(log, report)
    timeline = build_exception_timeline(
        log,
        startup_path=report["startup_path"],
        matched_apis=correlation.matched_apis,
    )
    log_path = tmp_path / "freej2me-core.log"
    log_path.write_text(log, encoding="utf-8")

    summary = build_runtime_diagnosis_summary(log_path, correlation, timeline)

    assert summary.log_name == "freej2me-core.log"
    assert summary.primary_exception == "NoClassDefFoundError"
    assert summary.root_exception == "NoClassDefFoundError"
    assert summary.matched_apis == ["wma_sms"]
    assert summary.failing_path[-1] == "wma_sms"
    assert summary.exception_count == 2
    assert summary.high_severity_count == 1

    text = format_runtime_diagnosis_summary(summary)
    assert "FREEJ2ME / RG35XX RUNTIME DIAGNOSIS" in text
    assert "Primary exception: NoClassDefFoundError" in text
    assert "Matched APIs: wma_sms" in text
    assert "Failing path:" in text


def test_runtime_diagnosis_summary_exports_next_to_log(tmp_path):
    log_path = tmp_path / "game-run.log"
    log_path.write_text("FreeJ2ME started\n", encoding="utf-8")
    correlation = correlate_runtime_log(log_path.read_text(encoding="utf-8"), None)
    timeline = build_exception_timeline(log_path.read_text(encoding="utf-8"))
    summary = build_runtime_diagnosis_summary(log_path, correlation, timeline)

    target = write_runtime_diagnosis_summary(log_path, summary)

    assert target == tmp_path / "game-run.runtime-diagnosis.txt"
    assert target.is_file()
    exported = target.read_text(encoding="utf-8")
    assert "Primary exception: none" in exported
    assert "No high-confidence runtime failure detected" in exported


def test_runtime_log_ui_has_copy_and_export_summary_contract_without_qt_import():
    source = open("gui/runtime_log_hook.py", encoding="utf-8").read()
    portable = open("app/gui/runtime_log_hook.py", encoding="utf-8").read()

    for text in (source, portable):
        assert 'QPushButton("Copy runtime diagnosis")' in text
        assert 'QPushButton("Export diagnosis TXT")' in text
        assert "build_runtime_diagnosis_summary(selected, result, timeline)" in text
        assert "format_runtime_diagnosis_summary(summary)" in text
        assert "write_runtime_diagnosis_summary(log_path, summary)" in text
        assert "QApplication.clipboard().setText" in text
