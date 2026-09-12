from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import zipfile

from core.jar_scanner import JarScanner
from core.class_reader import ClassReader
from core.binary_resource_analyzer import BinaryResourceAnalyzer


@dataclass
class ValidationItem:
    source: str
    kind: str
    original: str
    translated: str
    status: str   # PASS / FAIL / SKIPPED
    detail: str = ""


@dataclass
class RegressionReport:
    source_jar: str
    output_jar: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    archive_ok: bool = False
    rescan_ok: bool = False
    items: List[ValidationItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def validation_ok(self):
        return self.archive_ok and self.rescan_ok and self.failed == 0


class RegressionValidator:
    """Validate a rebuilt JAR without repeatedly rescanning the same resource.

    Older builds re-ran BinaryResourceAnalyzer once *per translated string* and
    performed a full deep JarScanner pass.  A binary table containing hundreds of
    translations could therefore be analyzed hundreds of times and make Build look
    frozen.  This validator groups checks by source and analyzes every output entry
    at most once.
    """

    def validate(self, source_result, project, output_jar: str, progress=None) -> RegressionReport:
        report = RegressionReport(source_result.jar_path, output_jar)
        output = Path(output_jar)
        if not output.exists():
            report.failed += 1
            report.items.append(ValidationItem("JAR", "", "", "", "FAIL", "Output JAR does not exist"))
            return report

        def emit(current, total, message):
            if progress:
                progress(current, total, message)

        try:
            with zipfile.ZipFile(output, "r") as z:
                bad = z.testzip()
                report.archive_ok = bad is None
                if bad:
                    report.warnings.append(f"CRC error at {bad}")
        except Exception as e:
            report.failed += 1
            report.items.append(ValidationItem("JAR", "", "", "", "FAIL", f"Cannot open output JAR: {e}"))
            return report

        # A lightweight scanner pass is enough here. Deep discovery was already done
        # before translation and structural validity is independently checked by Builder.
        try:
            JarScanner(deep_scan=False).scan(str(output))
            report.rescan_ok = True
        except Exception as e:
            report.failed += 1
            report.items.append(ValidationItem("JAR", "", "", "", "FAIL", f"Output fast rescan failed: {e}"))
            return report

        by_source = {}
        for _, s in source_result.all_strings():
            vi = project.get(s.key).strip()
            if vi and vi != s.value:
                by_source.setdefault(s.source, []).append((s, vi))

        with zipfile.ZipFile(output, "r") as zout:
            names = set(zout.namelist())
            total_sources = max(1, len(by_source))
            for source_index, (source, rows) in enumerate(by_source.items(), start=1):
                emit(source_index, total_sources, f"Đối chiếu {source_index}/{total_sources}: {source}")
                if source not in names:
                    for s, vi in rows:
                        report.failed += 1
                        report.items.append(ValidationItem(source, s.kind, s.value, vi, "FAIL", "Source entry missing from output JAR"))
                    continue
                try:
                    data = zout.read(source)
                except Exception as e:
                    for s, vi in rows:
                        report.failed += 1
                        report.items.append(ValidationItem(source, s.kind, s.value, vi, "FAIL", f"Cannot read output entry: {e}"))
                    continue

                class_rows = [(s, vi) for s, vi in rows if s.kind == "class-string"]
                text_rows = [(s, vi) for s, vi in rows if s.kind == "resource-text"]
                binary_rows = [(s, vi) for s, vi in rows if s.kind.startswith("binary:")]
                other_rows = [(s, vi) for s, vi in rows if s.kind != "class-string" and s.kind != "resource-text" and not s.kind.startswith("binary:")]

                if class_rows:
                    self._validate_class_group(data, source, class_rows, report)
                if text_rows:
                    self._validate_text_group(data, text_rows, report)
                if binary_rows:
                    self._validate_binary_group(data, source, binary_rows, report)
                for s, vi in other_rows:
                    report.skipped += 1
                    report.items.append(ValidationItem(source, s.kind, s.value, vi, "SKIPPED", "Unsupported validation kind"))

        return report

    def _validate_class_group(self, data, source, rows, report):
        try:
            strings = ClassReader(data, source).extract_strings()
            by_index = {x.index: x.value for x in strings}
            values = {x.value for x in strings}
            for s, vi in rows:
                if by_index.get(s.index) == vi:
                    report.passed += 1
                    report.items.append(ValidationItem(source, s.kind, s.value, vi, "PASS", f"CONSTANT_Utf8 index {s.index} verified"))
                elif vi in values:
                    report.passed += 1
                    report.items.append(ValidationItem(source, s.kind, s.value, vi, "PASS", "Translation found in class after rebuild"))
                else:
                    report.failed += 1
                    report.items.append(ValidationItem(source, s.kind, s.value, vi, "FAIL", "Translation not found in class"))
        except Exception as e:
            for s, vi in rows:
                report.failed += 1
                report.items.append(ValidationItem(source, s.kind, s.value, vi, "FAIL", f"Class validation error: {e}"))

    def _validate_text_group(self, data, rows, report):
        # Resources normally share one encoding; fall back per-row only when required.
        decode_cache = {}
        for s, vi in rows:
            enc = s.encoding or "utf-8"
            if enc not in decode_cache:
                try:
                    decode_cache[enc] = data.decode(enc)
                except Exception:
                    try:
                        decode_cache[enc] = data.decode("utf-8")
                    except Exception as e:
                        decode_cache[enc] = e
            text = decode_cache[enc]
            if isinstance(text, Exception):
                report.failed += 1
                report.items.append(ValidationItem(s.source, s.kind, s.value, vi, "FAIL", f"Cannot decode output text: {text}"))
                continue
            lines = text.splitlines()
            line_ok = 0 <= s.index < len(lines) and vi in lines[s.index]
            if line_ok or vi in text:
                report.passed += 1
                report.items.append(ValidationItem(s.source, s.kind, s.value, vi, "PASS", f"Text resource verified, expected line {s.index+1}"))
            else:
                report.failed += 1
                report.items.append(ValidationItem(s.source, s.kind, s.value, vi, "FAIL", "Translation not found in text resource"))

    def _validate_binary_group(self, data, source, rows, report):
        safe_rows = []
        for s, vi in rows:
            if s.kind.endswith(":unsafe"):
                report.skipped += 1
                report.items.append(ValidationItem(source, s.kind, s.value, vi, "SKIPPED", "Raw/unknown binary is intentionally locked"))
            else:
                safe_rows.append((s, vi))
        if not safe_rows:
            return

        safe_values = set()
        try:
            analysis = BinaryResourceAnalyzer().analyze(source, data)
            safe_values = {x.text for x in analysis.strings if x.patch_safe}
        except Exception:
            pass

        for s, vi in safe_rows:
            if vi in safe_values:
                report.passed += 1
                report.items.append(ValidationItem(source, s.kind, s.value, vi, "PASS", "Binary translation verified by framed analyzer"))
                continue
            try:
                found = vi.encode("utf-8") in data
            except Exception:
                found = False
            if found:
                report.passed += 1
                report.items.append(ValidationItem(source, s.kind, s.value, vi, "PASS", "Translation bytes found in binary output"))
            else:
                report.failed += 1
                report.items.append(ValidationItem(source, s.kind, s.value, vi, "FAIL", "Translated binary string not found in output"))
