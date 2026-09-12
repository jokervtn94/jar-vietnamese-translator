from __future__ import annotations

from pathlib import Path
import zipfile

from core.compatibility_report import CompatibilityExport
from core.diagnostic_bundle import export_diagnostic_bundle_zip
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


def test_zip_bundle_contains_runtime_files_and_leaves_only_zip(tmp_path):
    log = tmp_path / "freej2me.log"
    log.write_text("line 1\nruntime failure\n", encoding="utf-8")
    original_bytes = log.read_bytes()
    out = tmp_path / "out"

    result = export_diagnostic_bundle_zip(out, log, _summary())

    assert result.zip_path.is_file()
    assert result.zip_path.name == "freej2me_diagnostic.zip"
    assert not (out / "freej2me_diagnostic").exists()
    assert set(result.members) == {
        "freej2me.log",
        "manifest.txt",
        "runtime-diagnosis.txt",
    }

    with zipfile.ZipFile(result.zip_path, "r") as archive:
        assert archive.read("freej2me.log") == original_bytes
        manifest = archive.read("manifest.txt").decode("utf-8")
        assert "Compatibility JSON: not available" in manifest


def test_zip_bundle_includes_compatibility_report_when_available(tmp_path):
    log = tmp_path / "game.log"
    log.write_text("runtime log\n", encoding="utf-8")
    compat = CompatibilityExport(
        jar_name="game.jar",
        compatibility_score=80,
        runtime_risk="medium",
        detected_apis=["m3g"],
        conditional_apis=["m3g"],
        startup_path=["game.MainMIDlet"],
    )

    result = export_diagnostic_bundle_zip(
        tmp_path / "out",
        log,
        _summary("game.log"),
        compat,
    )

    assert "compatibility.compat.json" in result.members
    assert "compatibility.compat.txt" in result.members
    with zipfile.ZipFile(result.zip_path, "r") as archive:
        assert "game.jar" in archive.read("compatibility.compat.json").decode("utf-8")


def test_runtime_log_ui_exposes_zip_export_without_importing_qt():
    source = Path("gui/runtime_log_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/runtime_log_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert 'QPushButton("Export Bundle ZIP")' in text
        assert "export_diagnostic_bundle_zip(" in text
        assert "runtime_bundle_zip_btn.setEnabled(enabled)" in text
        assert "_export_diagnostic_bundle_zip" in text
