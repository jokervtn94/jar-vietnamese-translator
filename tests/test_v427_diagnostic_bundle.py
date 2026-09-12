from __future__ import annotations

from pathlib import Path

from core.compatibility_report import CompatibilityExport
from core.diagnostic_bundle import export_diagnostic_bundle
from core.runtime_diagnosis_summary import RuntimeDiagnosisSummary


def _summary(log_name="freej2me.log"):
    return RuntimeDiagnosisSummary(
        log_name=log_name,
        probable_cause="Runtime class resolution failure",
        primary_exception="NoClassDefFoundError",
        root_exception="NoClassDefFoundError",
        failing_path=["game.MainMIDlet", "m3g"],
        matched_apis=["m3g"],
        startup_overlap=["game.MainMIDlet"],
        recommendation="Check target runtime support.",
        exception_count=1,
        high_severity_count=1,
    )


def test_bundle_without_compatibility_preserves_original_log(tmp_path):
    log = tmp_path / "freej2me.log"
    original = "line 1\nruntime failure\n"
    log.write_text(original, encoding="utf-8")

    result = export_diagnostic_bundle(tmp_path / "out", log, _summary())

    assert result.directory.is_dir()
    assert result.original_log_path.read_text(encoding="utf-8") == original
    assert result.runtime_diagnosis_path.is_file()
    assert result.manifest_path.is_file()
    assert result.compatibility_json_path is None
    assert result.compatibility_text_path is None
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert "Compatibility JSON: not available" in manifest
    assert "preserves the original runtime log unchanged" in manifest


def test_bundle_with_compatibility_exports_json_and_text(tmp_path):
    log = tmp_path / "game.log"
    log.write_text("runtime log\n", encoding="utf-8")
    compat = CompatibilityExport(
        jar_name="game.jar",
        compatibility_score=72,
        runtime_risk="medium",
        detected_apis=["m3g"],
        conditional_apis=["m3g"],
        startup_path=["game.MainMIDlet"],
    )

    result = export_diagnostic_bundle(tmp_path / "out", log, _summary("game.log"), compat)

    assert result.compatibility_json_path is not None
    assert result.compatibility_text_path is not None
    assert result.compatibility_json_path.is_file()
    assert result.compatibility_text_path.is_file()
    assert "game.jar" in result.compatibility_json_path.read_text(encoding="utf-8")
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert result.compatibility_json_path.name in manifest
    assert result.compatibility_text_path.name in manifest


def test_runtime_log_ui_exposes_bundle_export_without_importing_qt():
    source = Path("gui/runtime_log_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/runtime_log_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert 'QPushButton("Export Diagnostic Bundle")' in text
        assert "export_diagnostic_bundle(" in text
        assert "_runtime_compat_export" in text
        assert "_set_runtime_export_controls(True)" in text
