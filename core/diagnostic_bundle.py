from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any
import zipfile

from core.compatibility_report import CompatibilityReportExporter
from core.runtime_diagnosis_summary import format_runtime_diagnosis_summary


@dataclass
class DiagnosticBundleResult:
    directory: Path
    manifest_path: Path
    runtime_diagnosis_path: Path
    original_log_path: Path
    compatibility_json_path: Path | None = None
    compatibility_text_path: Path | None = None


@dataclass
class DiagnosticBundleZipResult:
    bundle: DiagnosticBundleResult
    zip_path: Path


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    return cleaned.strip("._") or "diagnostic"


def export_diagnostic_bundle(
    output_parent: str | Path,
    log_path: str | Path,
    runtime_summary: Any,
    compatibility_export: Any | None = None,
    bundle_name: str | None = None,
) -> DiagnosticBundleResult:
    parent = Path(output_parent)
    parent.mkdir(parents=True, exist_ok=True)

    source_log = Path(log_path)
    if not source_log.is_file():
        raise FileNotFoundError(source_log)

    base_name = bundle_name or f"{source_log.stem}_diagnostic"
    bundle_dir = parent / _safe_name(base_name)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    original_log_path = bundle_dir / source_log.name
    shutil.copy2(source_log, original_log_path)

    runtime_diagnosis_path = bundle_dir / "runtime-diagnosis.txt"
    runtime_diagnosis_path.write_text(
        format_runtime_diagnosis_summary(runtime_summary) + "\n",
        encoding="utf-8",
    )

    compatibility_json_path = None
    compatibility_text_path = None
    if compatibility_export is not None:
        base = bundle_dir / "compatibility"
        compatibility_json_path, compatibility_text_path = CompatibilityReportExporter().write_pair(
            base, compatibility_export
        )

    manifest_path = bundle_dir / "manifest.txt"
    manifest_lines = [
        "JAR TRANSLATOR DIAGNOSTIC BUNDLE",
        f"Original log: {original_log_path.name}",
        f"Runtime diagnosis: {runtime_diagnosis_path.name}",
        f"Compatibility JSON: {compatibility_json_path.name if compatibility_json_path else 'not available'}",
        f"Compatibility TXT: {compatibility_text_path.name if compatibility_text_path else 'not available'}",
        "",
        "This bundle is diagnostic-only and preserves the original runtime log unchanged.",
    ]
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    return DiagnosticBundleResult(
        directory=bundle_dir,
        manifest_path=manifest_path,
        runtime_diagnosis_path=runtime_diagnosis_path,
        original_log_path=original_log_path,
        compatibility_json_path=compatibility_json_path,
        compatibility_text_path=compatibility_text_path,
    )


def zip_diagnostic_bundle(
    bundle: DiagnosticBundleResult | str | Path,
    zip_path: str | Path | None = None,
) -> Path:
    bundle_dir = bundle.directory if isinstance(bundle, DiagnosticBundleResult) else Path(bundle)
    if not bundle_dir.is_dir():
        raise FileNotFoundError(bundle_dir)

    target = Path(zip_path) if zip_path is not None else bundle_dir.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(bundle_dir))
    return target


def export_diagnostic_bundle_zip(
    output_parent: str | Path,
    log_path: str | Path,
    runtime_summary: Any,
    compatibility_export: Any | None = None,
    bundle_name: str | None = None,
) -> DiagnosticBundleZipResult:
    bundle = export_diagnostic_bundle(
        output_parent,
        log_path,
        runtime_summary,
        compatibility_export,
        bundle_name,
    )
    zip_path = zip_diagnostic_bundle(bundle)
    return DiagnosticBundleZipResult(bundle=bundle, zip_path=zip_path)
