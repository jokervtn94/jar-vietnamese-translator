from __future__ import annotations

import json
from types import SimpleNamespace

from core.compatibility_report import CompatibilityReportExporter


def _runtime():
    target = SimpleNamespace(
        score=72,
        risk="high",
        unsupported=["wma_sms"],
        conditional=["m3g"],
    )
    return SimpleNamespace(
        rg35xx=target,
        midp_profile="MIDP-2.0",
        cldc_configuration="CLDC-1.1",
        compatibility_score=72,
        runtime_risk="high",
        detected_apis={"wma_sms", "m3g"},
        api_sources={
            "wma_sms": ["game/net/Legacy.class"],
            "m3g": ["game/render/Scene.class"],
        },
        sms_targets=["sms://10612345"],
        uses_wma_sms=True,
    )


def _flow():
    path_short = SimpleNamespace(
        startup_reachable=True,
        path=["game.MainMIDlet", "game.Manager"],
    )
    path_deep = SimpleNamespace(
        startup_reachable=True,
        path=["game.MainMIDlet", "game.Manager", "game.guard.Check"],
    )
    dependency = SimpleNamespace(activation_paths=[path_short, path_deep])
    return SimpleNamespace(
        dependency=dependency,
        risk="high",
        score=88,
        suspicious_classes=["game/guard/Check.class"],
        suspicious_resources=[],
        startup_activation_reachable=True,
        likely_activation_gate=True,
        likely_payment_flow=False,
        wma_linked=True,
    )


def test_report_contains_runtime_startup_and_deepest_path(tmp_path):
    exporter = CompatibilityReportExporter()
    report = exporter.build(str(tmp_path / "demo.jar"), _runtime(), _flow())

    assert report.jar_name == "demo.jar"
    assert report.compatibility_score == 72
    assert report.runtime_risk == "high"
    assert report.detected_apis == ["m3g", "wma_sms"]
    assert report.startup_reachable is True
    assert report.startup_path == [
        "game.MainMIDlet", "game.Manager", "game.guard.Check"
    ]
    assert report.startup_classification == "likely_startup_blocker"
    assert report.startup_severity == "high"


def test_report_json_and_text_are_exportable(tmp_path):
    exporter = CompatibilityReportExporter()
    report = exporter.build(str(tmp_path / "demo.jar"), _runtime(), _flow())

    payload = json.loads(exporter.to_json(report))
    assert payload["schema"] == "jar-translator.compatibility-report.v1"
    assert payload["midp_profile"] == "MIDP-2.0"
    assert payload["startup_path"][-1] == "game.guard.Check"

    text = exporter.to_text(report)
    assert "JAR COMPATIBILITY REPORT" in text
    assert "Runtime score: 72/100" in text
    assert "game.MainMIDlet -> game.Manager -> game.guard.Check" in text

    json_path, txt_path = exporter.write_pair(tmp_path / "demo_report", report)
    assert json_path.name == "demo_report.compat.json"
    assert txt_path.name == "demo_report.compat.txt"
    assert json_path.is_file()
    assert txt_path.is_file()
