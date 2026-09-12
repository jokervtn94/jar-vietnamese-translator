from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List
import json
import zipfile


MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 64


@dataclass
class DiagnosticBundleInspection:
    archive_name: str
    entries: List[str] = field(default_factory=list)
    manifest_text: str = ""
    runtime_diagnosis_text: str = ""
    compatibility_json: Dict = field(default_factory=dict)
    compatibility_text: str = ""
    runtime_log_name: str = ""
    runtime_log_text: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def has_compatibility(self) -> bool:
        return bool(self.compatibility_json or self.compatibility_text)

    @property
    def is_valid_bundle(self) -> bool:
        return bool(self.manifest_text and self.runtime_diagnosis_text)


def _safe_entry(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    return ".." not in path.parts


def _read_text(zf: zipfile.ZipFile, name: str, warnings: List[str]) -> str:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return ""
    if info.file_size > MAX_TEXT_BYTES:
        warnings.append(f"Skipped oversized entry: {name}")
        return ""
    return zf.read(info).decode("utf-8", errors="replace")


def inspect_diagnostic_bundle_zip(path: str | Path) -> DiagnosticBundleInspection:
    archive = Path(path)
    if not archive.is_file():
        raise FileNotFoundError(archive)

    warnings: List[str] = []
    with zipfile.ZipFile(archive, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError("Diagnostic bundle contains too many entries")

        entries: List[str] = []
        for info in infos:
            if info.is_dir():
                continue
            if not _safe_entry(info.filename):
                raise ValueError(f"Unsafe ZIP entry: {info.filename}")
            entries.append(info.filename)

        manifest_name = next((name for name in entries if PurePosixPath(name).name == "manifest.txt"), "")
        runtime_name = next((name for name in entries if PurePosixPath(name).name == "runtime-diagnosis.txt"), "")
        compat_json_name = next((name for name in entries if PurePosixPath(name).name == "compatibility.compat.json"), "")
        compat_text_name = next((name for name in entries if PurePosixPath(name).name == "compatibility.compat.txt"), "")

        manifest_text = _read_text(zf, manifest_name, warnings) if manifest_name else ""
        runtime_diagnosis_text = _read_text(zf, runtime_name, warnings) if runtime_name else ""
        compatibility_text = _read_text(zf, compat_text_name, warnings) if compat_text_name else ""

        compatibility_json: Dict = {}
        if compat_json_name:
            raw_json = _read_text(zf, compat_json_name, warnings)
            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, dict):
                        compatibility_json = parsed
                    else:
                        warnings.append("Compatibility JSON is not an object")
                except json.JSONDecodeError:
                    warnings.append("Compatibility JSON is invalid")

        known_names = {name for name in (manifest_name, runtime_name, compat_json_name, compat_text_name) if name}
        log_candidates = [
            name for name in entries
            if name not in known_names and PurePosixPath(name).suffix.lower() in {".log", ".txt"}
        ]
        runtime_log_name = log_candidates[0] if log_candidates else ""
        runtime_log_text = _read_text(zf, runtime_log_name, warnings) if runtime_log_name else ""

        if not manifest_name:
            warnings.append("manifest.txt not found")
        if not runtime_name:
            warnings.append("runtime-diagnosis.txt not found")
        if not runtime_log_name:
            warnings.append("Runtime log not found")

        return DiagnosticBundleInspection(
            archive_name=archive.name,
            entries=entries,
            manifest_text=manifest_text,
            runtime_diagnosis_text=runtime_diagnosis_text,
            compatibility_json=compatibility_json,
            compatibility_text=compatibility_text,
            runtime_log_name=runtime_log_name,
            runtime_log_text=runtime_log_text,
            warnings=warnings,
        )


def format_diagnostic_bundle_inspection(result: DiagnosticBundleInspection) -> str:
    lines = [
        "DIAGNOSTIC BUNDLE INSPECTOR",
        f"Archive: {result.archive_name}",
        f"Entries: {len(result.entries)}",
        f"Valid bundle: {'yes' if result.is_valid_bundle else 'no'}",
        f"Compatibility report: {'available' if result.has_compatibility else 'not available'}",
        f"Runtime log: {result.runtime_log_name or 'not found'}",
    ]
    if result.compatibility_json:
        jar_name = result.compatibility_json.get("jar_name", "")
        score = result.compatibility_json.get("compatibility_score", "")
        risk = result.compatibility_json.get("runtime_risk", "")
        if jar_name:
            lines.append(f"JAR: {jar_name}")
        if score != "":
            lines.append(f"Compatibility score: {score}/100")
        if risk:
            lines.append(f"Runtime risk: {str(risk).upper()}")
    if result.warnings:
        lines.append("Warnings: " + "; ".join(result.warnings))
    lines.append("")
    lines.append(result.runtime_diagnosis_text.strip() or "Runtime diagnosis not available")
    return "\n".join(lines)
