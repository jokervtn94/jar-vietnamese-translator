import json
import os
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

    def build(self, result, project, output_path: str, progress=None) -> BuildReport:
        """Build to a temporary JAR and atomically publish only after validation.

        This keeps an existing good output untouched if patching, ZIP validation,
        class parsing, or regression validation fails midway. No UI callbacks are
        made here; callers can safely run this method on a worker thread.
        """
        source_path = Path(result.jar_path)
        output_path = Path(output_path)
        report = BuildReport(str(source_path), str(output_path))

        def emit(percent, stage, message):
            if progress:
                progress(int(percent), stage, message)

        emit(1, "prepare", "Đang chuẩn bị snapshot bản dịch…")

        if source_path.resolve() == output_path.resolve():
            raise ValueError("Output JAR must be different from source JAR")

        by_source: Dict[str, List[Tuple[object, str]]] = {}
        for _, st in result.all_strings():
            vi = project.get(st.key).strip()
            if vi and vi != st.value:
                by_source.setdefault(st.source, []).append((st, vi))

        emit(4, "prepare", f"Đã chuẩn bị {sum(len(v) for v in by_source.values())} bản dịch cần patch")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(output_path.name + ".building")
        try:
            if temp_path.exists():
                temp_path.unlink()

            with zipfile.ZipFile(source_path, "r") as zin:
                signed = [
                    i.filename for i in zin.infolist()
                    if i.filename.upper().startswith("META-INF/")
                    and i.filename.upper().endswith(SIGNATURE_SUFFIXES)
                ]
                if signed:
                    raise ValueError(
                        "This JAR contains signature files (META-INF/*.SF/*.RSA/*.DSA/*.EC). "
                        "Safe Build refuses to modify signed JARs because rebuilding invalidates the signature."
                    )

                infos = zin.infolist()
                emit(7, "patch", f"Bắt đầu ghi file tạm: {temp_path.name}")
                with zipfile.ZipFile(temp_path, "w") as zout:
                    total_entries=max(1,len(infos))
                    for entry_index, info in enumerate(infos, start=1):
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
                                for st, vi in patches:
                                    report.skipped += 1
                                    report.items.append(
                                        PatchItem(st.source, st.kind, st.value, vi, "SKIPPED", "Unsupported resource type")
                                    )

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
                        if entry_index == 1 or entry_index % 12 == 0 or entry_index == total_entries:
                            pct = 7 + int((entry_index / total_entries) * 61)
                            emit(pct, "patch", f"Đang ghi JAR {entry_index}/{total_entries}: {info.filename}")

            emit(72, "validate", "Đang kiểm tra ZIP / CRC / cấu trúc class…")
            self._validate(temp_path, report)
            structural_ok = bool(report.validation_ok)

            # Regression runs against the fully closed temporary archive.
            emit(82, "regression", "Đang đối chiếu các chuỗi sau khi rebuild…")
            try:
                def regression_progress(cur, total, message):
                    if progress:
                        pct = 82 + int((cur / max(1, total)) * 12)
                        progress(pct, "regression", message)
                rr = RegressionValidator().validate(result, project, str(temp_path), progress=regression_progress)
                report.regression_ok = rr.validation_ok
                report.regression_passed = rr.passed
                report.regression_failed = rr.failed
                report.regression_skipped = rr.skipped
                if not rr.validation_ok:
                    report.validation_ok = False
                    report.warnings.append(
                        f"Regression validation failed: {rr.failed} failed, {rr.passed} passed, {rr.skipped} skipped."
                    )
            except Exception as e:
                report.regression_ok = False
                report.validation_ok = False
                report.warnings.append(f"Regression validation could not run: {e}")

            # Never publish a structurally invalid archive. Regression failure can
            # indicate a rolled-back/unapplied translation while the JAR itself is
            # still structurally safe, so publish it with a warning/report.
            if not structural_ok:
                raise RuntimeError(
                    "Structural JAR validation failed. Output was not published; see build report for details."
                )

            emit(96, "publish", "Đang xuất bản JAR hoàn chỉnh…")
            os.replace(temp_path, output_path)
            emit(100, "publish", f"Build hoàn tất: {output_path.name}")
            return report
        except Exception:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            raise

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
        """Transactional structured-binary patching.

        V4.11 treats each binary resource as one transaction: every requested
        safe field must still match the original framing, every replacement must
        patch successfully, and every translated value must be rediscovered as a
        patch-safe framed field afterwards. If any step fails, the whole resource
        is rolled back so a partially translated binary table is never emitted.
        """
        analysis = BinaryResourceAnalyzer().analyze(source, data)
        detected = {(s.offset, s.text, s.framing): s for s in analysis.strings}
        prepared = []
        source_items = []

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
                source_items.append((s, vi, None))
                continue
            prepared.append((item, s, vi))
            source_items.append((s, vi, item))

        # Any preflight mismatch means we must not partially rewrite this source.
        if any(item is None for _, _, item in source_items):
            for s, vi, item in source_items:
                if item is not None:
                    report.failed += 1
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", "Binary source transaction aborted due to another invalid field"))
            return data

        prepared.sort(key=lambda x: x[0].offset, reverse=True)
        new_data = data
        patched_rows = []
        try:
            for item, s, vi in prepared:
                new_data = patch_binary_entry(new_data, item, vi)
                patched_rows.append((item, s, vi))
        except Exception as e:
            # Roll back the entire resource. No partial binary file is allowed.
            for _item, s, vi in prepared:
                report.failed += 1
                detail = str(e) if (_item, s, vi) in patched_rows or _item is item else "Binary source transaction rolled back"
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", detail))
            return data

        # V4.14: verify exact framing + UTF-8 bytes directly. The discovery
        # scanner is intentionally heuristic and may choose a different overlap
        # after Vietnamese strings change length, even when the resource is valid.
        try:
            failures = self._verify_binary_transaction(new_data, prepared)
            if failures:
                reason = "Post-patch direct framing validation failed: " + "; ".join(failures[:3])
                if len(failures) > 3:
                    reason += f"; +{len(failures)-3} more"
                for _item, s, vi in prepared:
                    report.failed += 1
                    report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", reason + "; file rolled back"))
                return data
        except Exception as e:
            for _item, s, vi in prepared:
                report.failed += 1
                report.items.append(PatchItem(source, s.kind, s.value, vi, "FAILED", f"Post-patch direct validation error: {e}; file rolled back"))
            return data

        for item, s, vi in prepared:
            report.patched += 1
            report.items.append(
                PatchItem(source, s.kind, s.value, vi, "PATCHED",
                          f"{item.framing} at 0x{item.offset:X}, UTF-8, transactional verify PASS")
            )
        return new_data

    @staticmethod
    def _verify_binary_transaction(final_data, prepared):
        """Verify every patched field by exact framing and payload bytes.

        Offsets in ``prepared`` refer to the original resource. Since patching is
        performed from high to low offsets, a field's final position is shifted
        only by replacements whose framed record originally starts before it.
        """
        import struct

        rows=[]
        for item, _s, vi in prepared:
            encoded=vi.encode("utf-8")
            frame_start=item.length_field_offset if item.length_field_offset is not None else item.offset
            if item.framing == "u8-length-prefixed":
                old_span=1+item.length
                new_span=1+len(encoded)
            elif item.framing in ("u16be-length-prefixed", "u16le-length-prefixed"):
                old_span=2+item.length
                new_span=2+len(encoded)
            elif item.framing == "null-terminated":
                old_span=item.length+item.terminator_size
                new_span=len(encoded)+item.terminator_size
            else:
                rows.append((item, encoded, vi, frame_start, 0, f"unsupported framing {item.framing}"))
                continue
            rows.append((item, encoded, vi, frame_start, new_span-old_span, None))

        failures=[]
        for item, encoded, _vi, original_frame_start, _delta, preset_error in rows:
            if preset_error:
                failures.append(preset_error)
                continue
            shift=sum(delta for other, _e, _v, other_start, delta, err in rows
                      if not err and other_start < original_frame_start)
            frame_start=original_frame_start+shift

            if item.framing == "u8-length-prefixed":
                if frame_start < 0 or frame_start + 1 + len(encoded) > len(final_data):
                    failures.append(f"u8 field out of bounds at 0x{frame_start:X}")
                    continue
                if final_data[frame_start] != len(encoded):
                    failures.append(f"u8 length mismatch at 0x{frame_start:X}")
                    continue
                payload_start=frame_start+1
            elif item.framing == "u16be-length-prefixed":
                if frame_start < 0 or frame_start + 2 + len(encoded) > len(final_data):
                    failures.append(f"u16be field out of bounds at 0x{frame_start:X}")
                    continue
                if struct.unpack(">H", final_data[frame_start:frame_start+2])[0] != len(encoded):
                    failures.append(f"u16be length mismatch at 0x{frame_start:X}")
                    continue
                payload_start=frame_start+2
            elif item.framing == "u16le-length-prefixed":
                if frame_start < 0 or frame_start + 2 + len(encoded) > len(final_data):
                    failures.append(f"u16le field out of bounds at 0x{frame_start:X}")
                    continue
                if struct.unpack("<H", final_data[frame_start:frame_start+2])[0] != len(encoded):
                    failures.append(f"u16le length mismatch at 0x{frame_start:X}")
                    continue
                payload_start=frame_start+2
            else:
                payload_start=frame_start
                term=payload_start+len(encoded)
                expected=b"\x00"*item.terminator_size
                if term+item.terminator_size > len(final_data) or final_data[term:term+item.terminator_size] != expected:
                    failures.append(f"null terminator mismatch at 0x{frame_start:X}")
                    continue

            payload=final_data[payload_start:payload_start+len(encoded)]
            if payload != encoded:
                failures.append(f"UTF-8 payload mismatch at 0x{payload_start:X}")
                continue
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError:
                failures.append(f"invalid UTF-8 payload at 0x{payload_start:X}")

        return failures

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
