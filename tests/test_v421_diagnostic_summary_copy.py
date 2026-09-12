from core.compatibility_report import CompatibilityExport
from gui.runtime_compat_hook import _diagnostic_summary


def test_diagnostic_summary_includes_startup_path_and_top_action():
    export = CompatibilityExport(
        jar_name="game.jar",
        target="FreeJ2ME / RG35XX",
        compatibility_score=72,
        runtime_risk="high",
        detected_apis=["m3g", "wma_sms"],
        unsupported_apis=["wma_sms"],
        conditional_apis=["m3g"],
        startup_title="Likely startup blocker",
        startup_severity="high",
        startup_path=["game.MainMIDlet", "game.Manager", "game.guard.Check"],
        recommended_actions=[
            {
                "priority": 1,
                "category": "startup_path",
                "title": "Kiểm tra class trên startup path",
                "detail": "game.MainMIDlet -> game.Manager -> game.guard.Check",
            },
            {
                "priority": 2,
                "category": "unsupported_api",
                "title": "Kiểm tra API chưa được target runtime hỗ trợ",
                "detail": "wma_sms",
            },
        ],
    )

    text = _diagnostic_summary(export)

    assert "JAR RG35XX DIAGNOSTIC SUMMARY" in text
    assert "Runtime: 72/100 · HIGH" in text
    assert "Assessment: Likely startup blocker · HIGH" in text
    assert "game.MainMIDlet -> game.Manager -> game.guard.Check" in text
    assert "Next action: P1" in text
    assert "Kiểm tra class trên startup path" in text


def test_runtime_hook_exposes_next_action_and_copy_controls():
    source = open("gui/runtime_compat_hook.py", encoding="utf-8").read()
    portable = open("app/gui/runtime_compat_hook.py", encoding="utf-8").read()

    for text in (source, portable):
        assert '("Next action:", self.runtime_next_action_value)' in text
        assert 'QPushButton("Copy diagnostic summary")' in text
        assert "QApplication.clipboard().setText(_diagnostic_summary(export))" in text
        assert "self.runtime_copy_btn.setEnabled(True)" in text
