from __future__ import annotations

from core.runtime_log_correlator import correlate_runtime_log, format_runtime_log_correlation


def test_missing_class_is_correlated_with_detected_api_and_startup_path():
    log = """
java.lang.NoClassDefFoundError: javax/wireless/messaging/MessageConnection
    at game.MainMIDlet.startApp(MainMIDlet.java:10)
"""
    report = {
        "detected_apis": ["wma_sms", "m3g"],
        "startup_path": ["game.MainMIDlet", "game.Manager"],
    }

    result = correlate_runtime_log(log, report)

    assert result.findings
    assert result.findings[0].error_type == "NoClassDefFoundError"
    assert result.findings[0].api_hint == "wma_sms"
    assert result.matched_apis == ["wma_sms"]
    assert result.matched_startup_classes == ["game.MainMIDlet"]
    assert result.stack_frames == ["game.MainMIDlet"]
    assert result.probable_failing_path == ["game.MainMIDlet", "wma_sms"]
    assert "Runtime cannot resolve required class" in result.probable_cause
    text = format_runtime_log_correlation(result)
    assert "Matched APIs: wma_sms" in text
    assert "game.MainMIDlet" in text
    assert "Probable failing path: game.MainMIDlet -> wma_sms" in text


def test_stack_trace_builds_probable_game_path_before_api():
    log = """
java.lang.NoClassDefFoundError: javax/wireless/messaging/MessageConnection
    at game.sms.SmsService.open(SmsService.java:31)
    at game.Manager.activate(Manager.java:88)
    at game.MainMIDlet.startApp(MainMIDlet.java:10)
"""
    report = {
        "detected_apis": ["wma_sms"],
        "startup_path": ["game.MainMIDlet", "game.Manager", "game.sms.SmsService"],
    }

    result = correlate_runtime_log(log, report)

    assert result.stack_frames == [
        "game.sms.SmsService",
        "game.Manager",
        "game.MainMIDlet",
    ]
    assert result.matched_startup_classes == [
        "game.MainMIDlet",
        "game.Manager",
        "game.sms.SmsService",
    ]
    assert result.probable_failing_path == [
        "game.MainMIDlet",
        "game.Manager",
        "game.sms.SmsService",
        "wma_sms",
    ]


def test_verify_error_gets_bytecode_diagnostic():
    log = "java.lang.VerifyError: game/MainMIDlet\n"
    result = correlate_runtime_log(log, {"startup_path": ["game.MainMIDlet"]})

    assert result.findings[0].error_type == "VerifyError"
    assert result.findings[0].severity == "high"
    assert "Bytecode verification failed" in result.probable_cause


def test_clean_log_returns_no_high_confidence_failure():
    result = correlate_runtime_log("FreeJ2ME started successfully\nFPS: 60\n", None)

    assert result.findings == []
    assert result.matched_apis == []
    assert result.probable_cause == "No high-confidence runtime failure detected"
    assert result.probable_failing_path == []


def test_runtime_log_ui_contract_is_present_without_importing_qt():
    source = open("gui/runtime_log_hook.py", encoding="utf-8").read()
    portable = open("app/gui/runtime_log_hook.py", encoding="utf-8").read()

    for text in (source, portable):
        assert 'QLabel("Runtime Log Diagnostic")' in text
        assert 'QPushButton("Open log file")' in text
        assert "log_text = load_log(selected)" in text
        assert "correlate_runtime_log(log_text, report)" in text
        assert "_runtime_compat_export" in text
