from __future__ import annotations

from pathlib import Path
import json
import zipfile
import pytest

from core.diagnostic_bundle_inspector import (
    format_diagnostic_bundle_inspection,
    inspect_diagnostic_bundle_zip,
)


def _write_bundle(path: Path, include_compatibility: bool = True):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.txt",
            "JAR TRANSLATOR DIAGNOSTIC BUNDLE\nOriginal log: runtime.log\nRuntime diagnosis: runtime-diagnosis.txt\n",
        )
        zf.writestr(
            "runtime-diagnosis.txt",
            "FREEJ2ME / RG35XX RUNTIME DIAGNOSIS\nPrimary exception: VerifyError\n",
        )
        zf.writestr("runtime.log", "java.lang.VerifyError: game/MainMIDlet\n")
        if include_compatibility:
            payload = {
                "jar_name": "game.jar",
                "compatibility_score": 84,
                "runtime_risk": "medium",
                "detected_apis": ["m3g"],
            }
            zf.writestr("compatibility.compat.json", json.dumps(payload))
            zf.writestr("compatibility.compat.txt", "JAR: game.jar\nRuntime: 84/100\n")


def test_inspector_reads_complete_bundle_without_extracting(tmp_path):
    archive = tmp_path / "game_diagnostic.zip"
    _write_bundle(archive, include_compatibility=True)

    result = inspect_diagnostic_bundle_zip(archive)

    assert result.is_valid_bundle is True
    assert result.has_compatibility is True
    assert result.compatibility_json["jar_name"] == "game.jar"
    assert result.compatibility_json["compatibility_score"] == 84
    assert result.runtime_log_name == "runtime.log"
    assert "VerifyError" in result.runtime_log_text
    assert result.warnings == []

    text = format_diagnostic_bundle_inspection(result)
    assert "DIAGNOSTIC BUNDLE INSPECTOR" in text
    assert "Compatibility score: 84/100" in text
    assert "Runtime risk: MEDIUM" in text
    assert "Primary exception: VerifyError" in text


def test_inspector_accepts_runtime_only_bundle(tmp_path):
    archive = tmp_path / "runtime_only.zip"
    _write_bundle(archive, include_compatibility=False)

    result = inspect_diagnostic_bundle_zip(archive)

    assert result.is_valid_bundle is True
    assert result.has_compatibility is False
    assert result.runtime_log_name == "runtime.log"
    assert result.compatibility_json == {}


def test_inspector_rejects_unsafe_zip_entry(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.txt", "manifest")
        zf.writestr("runtime-diagnosis.txt", "diagnosis")
        zf.writestr("../outside.log", "unsafe")

    with pytest.raises(ValueError, match="Unsafe ZIP entry"):
        inspect_diagnostic_bundle_zip(archive)


def test_inspector_reports_missing_required_files(tmp_path):
    archive = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("runtime.log", "runtime\n")

    result = inspect_diagnostic_bundle_zip(archive)

    assert result.is_valid_bundle is False
    assert "manifest.txt not found" in result.warnings
    assert "runtime-diagnosis.txt not found" in result.warnings


def test_bundle_inspector_ui_contract_without_importing_qt():
    source = Path("gui/diagnostic_bundle_inspector_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/diagnostic_bundle_inspector_hook.py").read_text(encoding="utf-8")
    runtime_source = Path("gui/runtime_log_hook.py").read_text(encoding="utf-8")
    runtime_portable = Path("app/gui/runtime_log_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert 'QLabel("Diagnostic Bundle Inspector")' in text
        assert 'QPushButton("Open Diagnostic ZIP")' in text
        assert "inspect_diagnostic_bundle_zip(selected)" in text
        assert "format_diagnostic_bundle_inspection(result)" in text

    for text in (runtime_source, runtime_portable):
        assert "install_diagnostic_bundle_inspector(MainWindow)" in text
