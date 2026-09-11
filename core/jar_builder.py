import json
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple

from core.class_patcher import ClassPatcher, ClassPatchError
from core.resource_scanner import TEXT_EXTENSIONS
from core.class_reader import ClassReader, ClassFormatError
from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.binary_resource_patcher import patch_binary_entry
from core.regression_validator import RegressionValidator


SIGNATURE_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")


@dataclass
class PatchItem:
    source: str
    kind: str
    original: str
    translated: str
    status: str
    detail: str = ""


@dataclass
class BuildReport:
    source_jar: str
    output_jar: str
    patched: int = 0
    skipped: int = 0
    failed: int = 0
    entries_written: int = 0
    validation_ok: bool = False
    regression_ok: bool = False
    regression_passed: int = 0
    regression_failed: int = 0
    regression_skipped: int = 0
    items: List[PatchItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def save_json(self, path: str):
        payload = asdict(self)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


class JarBuilder:
    """Safe-mode JAR rebuilder for V3.

    Supported:
      - class-string: rewrites the referenced CONSTANT_Utf8 entry
      - resource-text: rewrites the same logical line/value in text resources
      - safe framed binary strings: null-terminated / u8 / u16be / u16le length-prefixed
    Deliberately skipped:
      - raw/unknown binary strings without reliable framing
    """

    def build(self, result, project, output_path: str) -> BuildReport:
        source_path = Path(result.jar_path)
        output_path = Path(output_path)
        report = BuildReport(str(source_path), str(output_path))

        if source_path.resolve() == output_path.resolve():
            raise ValueError("Output JAR must be different from source JAR")

        by_source: Dict[str, List[Tuple[object, str]]] = {}
        for _, s in result.all_strings():
            vi = project.get(s.key).strip()
            if vi and vi != s.value:
                by_source.setdefault(s.source, []).append((s, vi))

        with zipfile.ZipFile(source_path, "r") as zin:
            signed = [i.filename for i in zin.infolist()
                      if i.filename.upper().startswith("META-INF/") and i.filename.upper().endswith(SIGNATURE_SUFFIXES)]
            if signed:
                raise ValueError(
                    "This JAR contains signature files (META-INF/*.SF/*.RSA/*.DSA/*.EC). "
                    "Safe Build refuses to modify signed JARs because rebuilding invalidates the signature."
                )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output_path, "w") as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    patches = by_source.get(info.filename, [])
                    new_data = data
                    if patches:
                        ext = Path(info.filename).suffix.lower()
                        if ext == ".class":
                            new_data = self._patch_class(info.filename, data, patches, report)
                        elif ext in TEXT_EXTENSIONS:
                            new_data = self._patch_text(info.filename, data, patches, report)
                        elif ext in (".dat", ".bin", ".res"):
                            new_data = self._patch_binary(info.filename, data, patches, report)
                        else:
                            for s, vi in patches:
                                report.skipped += 1
                                report.items.append(PatchItem(s.source, s.kind, s.value, vi, "SKIPPED", "Unsupported resource type"))
                    # Copy metadata while allowing Python to recompute CRC/sizes.
                    out_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    out_info.compress_type = info.compress_type
                    out_info.comment = info.comment
                    out_info.extra = info.extra
                    out_info.internal_attr = info.internal_attr
                    out_info.external_attr = info.external_attr
                    out_info.create_system = info.create_system
                    out_info.flag_bits = info.flag_bits & ~0x08
                    zout.writestr(out_info, new_data)
                    report.entries_written += 1

        self._validate(output_path, report)

        # V3.7 regression validation: reopen and verify translations actually exist.
        try:
            rr = RegressionValidator().validate(result, project, str(output_path))
            report.regression_ok = rr.validation_ok
            report.regression_passed = rr.passed
            report.regression_failed = rr.failed
            report.regression_skipped = rr.skipped
            if not rr.validation_ok:
                report.validation_ok = False
                report.warnings.append(
                    f"Regression validation failed: {rr.failed} failed, {rr.passed} passed, {rr.skipped} skipped."
                )
            else:
                report.warnings.append(
                    f"Regression validation PASS: {rr.passed} passed, {rr.skipped} skipped."
                )
        except Exception as e:
            report.regression_ok = False
            report.validation_ok = False
            report.warnings.append(f"Regression validation could not run: {e}")

        return report

    def _patch_class(self, source, data, patches, report):
        replacements: Dict[int, str] = {}
        for s, vi in patches:
            if s.kind != "class-string" or s.index < 1:
                report.skipped += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "SKIPPED", "Not a patchable class-string"))
                continue
            # If the same UTF8 index is shared by duplicate references, require same replacement.
            if s.index in replacements and replacements[s.index] != vi:
                report.failed += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", f"Conflicting translation for constant-pool index {s.index}"))
                continue
            replacements[s.index] = vi

        if not replacements:
            return data
        try:
            patched_data, count = ClassPatcher.patch(data, replacements)
            # Parse it immediately to catch structural corruption.
            ClassReader(patched_data, source).extract_strings()
            report.patched += count
            for s, vi in patches:
                if s.kind == "class-string" and s.index in replacements and replacements[s.index] == vi:
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "PATCHED", f"CONSTANT_Utf8 index {s.index}"))
            return patched_data
        except (ClassPatchError, ClassFormatError) as e:
            report.failed += len(replacements)
            for s, vi in patches:
                if s.kind == "class-string" and s.index in replacements:
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", str(e)))
            return data

    @staticmethod
    def _decode_with_encoding(data: bytes, enc: str):
        return data.decode(enc)

    def _patch_text(self, source, data, patches, report):
        # Scanner records original line number and detected encoding.
        enc = patches[0][0].encoding or "utf-8"
        try:
            text = self._decode_with_encoding(data, enc)
        except Exception as e:
            for s, vi in patches:
                report.failed += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", f"Decode failed: {e}"))
            return data

        # Keep line endings exactly where possible.
        lines = text.splitlines(keepends=True)
        changed = False
        for s, vi in patches:
            if s.kind != "resource-text" or not (0 <= s.index < len(lines)):
                report.skipped += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "SKIPPED", "Resource line index is not patchable"))
                continue
            line = lines[s.index]
            ending = ""
            core = line
            if core.endswith("\r\n"):
                core, ending = core[:-2], "\r\n"
            elif core.endswith("\n") or core.endswith("\r"):
                core, ending = core[:-1], core[-1:]

            # Preserve key= prefix and surrounding whitespace around the value.
            if "=" in core:
                prefix, value_part = core.split("=", 1)
                left_ws = value_part[:len(value_part) - len(value_part.lstrip())]
                right_ws = value_part[len(value_part.rstrip()):]
                old_value = value_part.strip()
                if old_value != s.value:
                    report.failed += 1
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", "Source line no longer matches scanned original"))
                    continue
                new_core = prefix + "=" + left_ws + vi + right_ws
            else:
                left_ws = core[:len(core) - len(core.lstrip())]
                right_ws = core[len(core.rstrip()):]
                old_value = core.strip()
                if old_value != s.value:
                    report.failed += 1
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", "Source line no longer matches scanned original"))
                    continue
                new_core = left_ws + vi + right_ws
            lines[s.index] = new_core + ending
            changed = True
            report.patched += 1
            report.items.append(PatchItem(source, s.kind, s.value, vi, "PATCHED", f"line {s.index + 1}, encoding {enc}"))

        if not changed:
            return data
        new_text = "".join(lines)
        try:
            return new_text.encode(enc)
        except UnicodeEncodeError as e:
            # Roll back the entire file; do not silently change charset.
            # Correct previously optimistic PATCHED accounting for this source.
            source_patched = [it for it in report.items if it.source == source and it.status == "PATCHED"]
            for it in source_patched:
                it.status = "FAILED"
                it.detail = f"Translation cannot be encoded as {enc}: {e}"
                report.patched -= 1
                report.failed += 1
            return data


    def _patch_binary(self, source, data, patches, report):
        """
        Controlled binary patch:
        - Re-analyze ORIGINAL bytes at build time.
        - Require scanned offset + text + framing to still match.
        - Patch entries from highest offset to lowest so earlier offsets remain valid
          when translated byte lengths differ.
        - Unsafe/raw entries are always skipped.
        """
        analysis = BinaryResourceAnalyzer().analyze(source, data)
        detected = {(s.offset, s.text, s.framing): s for s in analysis.strings}
        prepared = []

        for s, vi in patches:
            if not s.kind.startswith("binary:"):
                report.skipped += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "SKIPPED", "Not a binary translation entry"))
                continue

            parts = s.kind.split(":")
            framing = parts[1] if len(parts) > 1 else ""
            safe_flag = parts[2] if len(parts) > 2 else "unsafe"
            if safe_flag != "safe":
                report.skipped += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "SKIPPED", "Raw/unknown binary string is locked"))
                continue

            item = detected.get((s.index, s.value, framing))
            if item is None or not item.patch_safe:
                report.failed += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", "Binary framing/offset/original no longer matches source"))
                continue
            prepared.append((item, s, vi))

        # Reverse offsets prevents later entries moving before we patch them.
        prepared.sort(key=lambda x: x[0].offset, reverse=True)
        new_data = data
        for item, s, vi in prepared:
            try:
                new_data = patch_binary_entry(new_data, item, vi)
                report.patched += 1
                report.items.append(
                    PatchItem(source, s.kind, s.value, vi, "PATCHED",
                              f"{item.framing} at 0x{item.offset:X}, encoding utf-8")
                )
            except Exception as e:
                report.failed += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", str(e)))

        # Re-analyze final bytes. This is a framing sanity check, not proof of game semantics.
        if prepared:
            post = BinaryResourceAnalyzer().analyze(source, new_data)
            if post.format_name == "raw/unknown":
                # Conservative rollback of this entire binary file.
                affected = [it for it in report.items if it.source == source and it.status == "PATCHED"]
                for it in affected:
                    it.status = "FAILED"
                    it.detail = "Post-patch binary framing validation failed; file rolled back"
                    report.patched -= 1
                    report.failed += 1
                return data

        return new_data

    def _validate(self, output_path: Path, report: BuildReport):
        try:
            with zipfile.ZipFile(output_path, "r") as z:
                bad = z.testzip()
                if bad:
                    report.warnings.append(f"CRC validation failed at {bad}")
                    report.validation_ok = False
                    return
                # Structural sanity-check patched class files.
                failed_classes = []
                patched_sources = {it.source for it in report.items if it.status == "PATCHED" and it.source.endswith(".class")}
                for source in patched_sources:
                    try:
                        ClassReader(z.read(source), source).extract_strings()
                    except Exception as e:
                        failed_classes.append(f"{source}: {e}")
                if failed_classes:
                    report.warnings.extend(failed_classes)
                    report.validation_ok = False
                else:
                    report.validation_ok = True
        except Exception as e:
            report.warnings.append(f"Validation error: {e}")
            report.validation_ok = False
