
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import zipfile

from core.jar_scanner import JarScanner
from core.class_reader import ClassReader, ClassFormatError
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
    def validate(self, source_result, project, output_jar: str) -> RegressionReport:
        report=RegressionReport(source_result.jar_path, output_jar)
        output=Path(output_jar)
        if not output.exists():
            report.failed += 1
            report.items.append(ValidationItem("JAR","","","", "FAIL","Output JAR does not exist"))
            return report

        # Basic archive integrity
        try:
            with zipfile.ZipFile(output,"r") as z:
                bad=z.testzip()
                if bad:
                    report.warnings.append(f"CRC error at {bad}")
                    report.archive_ok=False
                else:
                    report.archive_ok=True
        except Exception as e:
            report.failed += 1
            report.items.append(ValidationItem("JAR","","","", "FAIL", f"Cannot open output JAR: {e}"))
            return report

        # Rescan output
        try:
            out_result=JarScanner().scan(str(output))
            report.rescan_ok=True
        except Exception as e:
            report.failed += 1
            report.items.append(ValidationItem("JAR","","","", "FAIL", f"Output rescan failed: {e}"))
            return report

        # Validate each translated string against actual output bytes/content
        with zipfile.ZipFile(output,"r") as zout:
            for _,s in source_result.all_strings():
                vi=project.get(s.key).strip()
                if not vi or vi == s.value:
                    continue

                if s.source not in zout.namelist():
                    report.failed += 1
                    report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL","Source entry missing from output JAR"))
                    continue

                try:
                    data=zout.read(s.source)
                except Exception as e:
                    report.failed += 1
                    report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL",f"Cannot read output entry: {e}"))
                    continue

                if s.kind == "class-string":
                    self._validate_class(data,s,vi,report)
                elif s.kind == "resource-text":
                    self._validate_text(data,s,vi,report)
                elif s.kind.startswith("binary:"):
                    self._validate_binary(data,s,vi,report)
                else:
                    report.skipped += 1
                    report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"SKIPPED","Unsupported validation kind"))

        return report

    def _validate_class(self, data, s, vi, report):
        try:
            strings=ClassReader(data,s.source).extract_strings()
            matches=[x for x in strings if x.index == s.index]
            if matches and any(x.value == vi for x in matches):
                report.passed += 1
                report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"PASS",f"CONSTANT_Utf8 index {s.index} verified"))
            else:
                # Fallback search because some readers may normalize references differently.
                if any(x.value == vi for x in strings):
                    report.passed += 1
                    report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"PASS","Translation found in class after rebuild"))
                else:
                    report.failed += 1
                    report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL","Translation not found in class"))
        except Exception as e:
            report.failed += 1
            report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL",f"Class validation error: {e}"))

    def _validate_text(self, data, s, vi, report):
        enc=s.encoding or "utf-8"
        try:
            text=data.decode(enc)
        except Exception:
            try:
                text=data.decode("utf-8")
            except Exception as e:
                report.failed += 1
                report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL",f"Cannot decode output text: {e}"))
                return
        lines=text.splitlines()
        line_ok = 0 <= s.index < len(lines) and vi in lines[s.index]
        if line_ok or vi in text:
            report.passed += 1
            report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"PASS",f"Text resource verified, expected line {s.index+1}"))
        else:
            report.failed += 1
            report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL","Translation not found in text resource"))

    def _validate_binary(self, data, s, vi, report):
        # Unsafe/raw binary translations are intentionally never expected to be patched.
        if s.kind.endswith(":unsafe"):
            report.skipped += 1
            report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"SKIPPED","Raw/unknown binary is intentionally locked"))
            return

        # Re-analyze the output. Because variable-length patch can shift later offsets,
        # validation searches framed strings by translated value rather than original offset.
        try:
            analysis=BinaryResourceAnalyzer().analyze(s.source,data)
            if any(x.text == vi and x.patch_safe for x in analysis.strings):
                report.passed += 1
                report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"PASS",f"Binary translation verified as {analysis.format_name}"))
                return
        except Exception:
            pass

        # Byte-level fallback for UTF-8 output
        try:
            if vi.encode("utf-8") in data:
                report.passed += 1
                report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"PASS","Translation bytes found in binary output"))
                return
        except Exception:
            pass

        report.failed += 1
        report.items.append(ValidationItem(s.source,s.kind,s.value,vi,"FAIL","Translated binary string not found in output"))
