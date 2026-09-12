from __future__ import annotations

from core.runtime_exception_timeline import build_exception_timeline, format_exception_timeline


def test_caused_by_high_severity_event_becomes_root_and_primary():
    log = """
java.lang.IllegalArgumentException: wrapper
    at game.Manager.activate(Manager.java:21)
    at game.MainMIDlet.startApp(MainMIDlet.java:10)
Caused by: java.lang.NoClassDefFoundError: javax/wireless/messaging/MessageConnection
    at game.sms.SmsService.open(SmsService.java:42)
    at game.Manager.activate(Manager.java:20)
"""
    timeline = build_exception_timeline(
        log,
        startup_path=["game.MainMIDlet", "game.Manager", "game.sms.SmsService"],
        matched_apis=["wma_sms"],
    )

    assert len(timeline.events) == 2
    assert timeline.root is not None
    assert timeline.primary is not None
    assert timeline.root.error_type == "NoClassDefFoundError"
    assert timeline.primary.error_type == "NoClassDefFoundError"
    assert timeline.primary.startup_overlap == ["game.Manager", "game.sms.SmsService"]

    text = format_exception_timeline(timeline)
    assert "ROOT" in text
    assert "PRIMARY" in text
    assert "Priority failure: NoClassDefFoundError" in text
    assert "game.Manager" in text
    assert "game.sms.SmsService" in text


def test_without_caused_by_first_exception_is_root_but_stronger_event_can_be_primary():
    log = """
java.lang.IllegalArgumentException: first
    at game.MainMIDlet.startApp(MainMIDlet.java:10)
java.lang.VerifyError: game/Renderer
    at game.Renderer.init(Renderer.java:5)
"""
    timeline = build_exception_timeline(log, startup_path=["game.MainMIDlet"], matched_apis=[])

    assert timeline.root_index == 0
    assert timeline.root.error_type == "IllegalArgumentException"
    assert timeline.primary.error_type == "VerifyError"


def test_empty_log_has_no_timeline_events():
    timeline = build_exception_timeline("FreeJ2ME started successfully\n", [], [])
    assert timeline.events == []
    assert timeline.primary is None
    assert timeline.root is None
    assert format_exception_timeline(timeline) == "EXCEPTION TIMELINE\n- none"


def test_runtime_log_ui_uses_exception_timeline_without_importing_qt():
    source = open("gui/runtime_log_hook.py", encoding="utf-8").read()
    portable = open("app/gui/runtime_log_hook.py", encoding="utf-8").read()

    for text in (source, portable):
        assert "build_exception_timeline(" in text
        assert "format_exception_timeline(timeline)" in text
        assert "Priority failure:" in text
