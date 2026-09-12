from __future__ import annotations

from types import SimpleNamespace

from core.compatibility_report import CompatibilityReportExporter


def _runtime(*, unsupported=(), conditional=()):
    return SimpleNamespace(
        rg35xx=SimpleNamespace(
            unsupported=list(unsupported),
            conditional=list(conditional),
            score=100,
            risk="low",
        ),
        detected_apis=set(),
        api_sources={},
        sms_targets=[],
        midp_profile="MIDP-2.0",
        cldc_configuration="CLDC-1.1",
        compatibility_score=100,
        runtime_risk="low",
    )


def _flow(*, path=None, suspicious=()):
    paths=[]
    if path:
        paths.append(SimpleNamespace(startup_reachable=True, path=list(path)))
    return SimpleNamespace(
        dependency=SimpleNamespace(activation_paths=paths),
        suspicious_classes=list(suspicious),
        suspicious_resources=[],
        startup_activation_reachable=bool(path),
        risk="low",
        score=0,
        likely_activation_gate=False,
        likely_payment_flow=False,
        wma_linked=False,
    )


def test_actions_prioritize_startup_path_then_unsupported_api_then_conditional_api():
    runtime=_runtime(unsupported=("wma_sms",), conditional=("m3g",))
    flow=_flow(path=("game.MainMIDlet", "game.Manager", "game.guard.Check"))

    report=CompatibilityReportExporter().build("game.jar", runtime, flow)

    assert [a.priority for a in report.recommended_actions] == [1, 2, 3]
    assert [a.category for a in report.recommended_actions] == [
        "startup_path", "unsupported_api", "conditional_api"
    ]
    assert "game.MainMIDlet" in report.recommended_actions[0].detail
    assert "game.guard.Check" in report.recommended_actions[0].detail
    assert report.recommended_actions[1].detail == "wma_sms"
    assert report.recommended_actions[2].detail == "m3g"

    text=CompatibilityReportExporter.to_text(report)
    assert "RECOMMENDED ACTIONS" in text
    assert "P1" in text
    assert "P2" in text
    assert "P3" in text


def test_actions_use_suspicious_class_when_no_startup_path():
    report=CompatibilityReportExporter().build(
        "game.jar",
        _runtime(),
        _flow(suspicious=("game/pay/Check.class",)),
    )

    assert report.recommended_actions[0].priority == 2
    assert report.recommended_actions[0].category == "suspicious_class"


def test_actions_fall_back_to_runtime_test_for_clean_report():
    report=CompatibilityReportExporter().build("game.jar", _runtime(), _flow())

    assert len(report.recommended_actions) == 1
    assert report.recommended_actions[0].priority == 4
    assert report.recommended_actions[0].category == "runtime_test"
