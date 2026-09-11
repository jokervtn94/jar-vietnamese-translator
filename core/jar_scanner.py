import zipfile
from pathlib import Path
from models.data import JarScanResult, Candidate, ExtractedString
from core.class_reader import ClassReader, ClassFormatError
from core.resource_scanner import ResourceScanner, TEXT_EXTENSIONS, BINARY_EXTENSIONS
from core.language_detector import LanguageDetector
from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.deep_resource_scanner import DeepResourceScanner


class JarScanner:
    def __init__(self, deep_scan=True):
        self.resources = ResourceScanner()
        self.detector = LanguageDetector()
        self.binary_analyzer = BinaryResourceAnalyzer()
        self.deep = DeepResourceScanner()
        self.deep_scan = deep_scan

    @staticmethod
    def _merge(primary, extra):
        seen = {(x.index, x.value, x.kind) for x in primary}
        out = list(primary)
        seen_value_offset = {(x.index, x.value) for x in primary}
        for x in extra:
            if (x.index, x.value, x.kind) in seen or (x.index, x.value) in seen_value_offset:
                continue
            out.append(x)
            seen.add((x.index, x.value, x.kind))
            seen_value_offset.add((x.index, x.value))
        return out

    @staticmethod
    def _open_archive(path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {p}")
        if not p.is_file():
            raise ValueError(f"Đường dẫn không phải file: {p}")

        # JAR về bản chất là ZIP. Kiểm tra theo nội dung, không phụ thuộc đuôi .jar/.zip.
        try:
            raw = p.open("rb")
        except OSError as e:
            raise OSError(f"Không thể đọc file '{p.name}': {e}") from e

        try:
            if not zipfile.is_zipfile(raw):
                raw.close()
                raise zipfile.BadZipFile(
                    f"'{p.name}' không phải JAR/ZIP hợp lệ hoặc file đã bị hỏng. "
                    "Hãy kiểm tra lại file gốc thay vì chỉ đổi phần mở rộng."
                )
            raw.seek(0)
            return raw, zipfile.ZipFile(raw, "r")
        except Exception:
            if not raw.closed:
                raw.close()
            raise

    def scan(self, jar_path: str) -> JarScanResult:
        result = JarScanResult(jar_path=str(jar_path))
        diag = {
            "entries_total": 0,
            "entries_read": 0,
            "entries_deep_scanned": 0,
            "entries_skipped_media_or_size": 0,
            "class_parse_failed": 0,
            "strings_before_filter": 0,
            "strings_after_filter": 0,
            "strings_rejected_non_language": 0,
            "deep_strings": 0,
        }

        raw_file, jar = self._open_archive(jar_path)
        try:
            infos = [i for i in jar.infolist() if not i.is_dir()]
            result.entries = [i.filename for i in infos]
            diag["entries_total"] = len(infos)
            try:
                result.manifest = jar.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
            except KeyError:
                pass

            for info in infos:
                name = info.filename
                ext = Path(name).suffix.lower()

                if info.file_size > 16 * 1024 * 1024:
                    diag["entries_skipped_media_or_size"] += 1
                    continue

                known = ext == ".class" or ext in TEXT_EXTENSIONS or ext in BINARY_EXTENSIONS
                deep_allowed = self.deep_scan and self.deep.should_scan(name, info.file_size)
                if not known and not deep_allowed:
                    diag["entries_skipped_media_or_size"] += 1
                    continue

                try:
                    data = jar.read(info)
                    diag["entries_read"] += 1
                except Exception:
                    continue

                raw = []
                source_type = "resource"
                reasons_extra = []

                if ext == ".class":
                    source_type = "class"
                    try:
                        raw = ClassReader(data, name).extract_strings()
                    except ClassFormatError:
                        diag["class_parse_failed"] += 1
                        raw = []
                    if self.deep_scan:
                        dr = self.deep.scan(name, data)
                        raw = self._merge(raw, dr.strings)
                        diag["entries_deep_scanned"] += 1
                        diag["deep_strings"] += len(dr.strings)
                        reasons_extra.extend(dr.notes)

                elif ext in BINARY_EXTENSIONS:
                    source_type = "binary"
                    analysis = self.binary_analyzer.analyze(name, data)
                    for bs in analysis.strings:
                        raw.append(ExtractedString(
                            source=name,
                            value=bs.text,
                            kind=f"binary:{bs.framing}:{'safe' if bs.patch_safe else 'unsafe'}",
                            index=bs.offset,
                            encoding=bs.encoding,
                        ))
                    if self.deep_scan:
                        dr = self.deep.scan(name, data)
                        raw = self._merge(raw, dr.strings)
                        diag["entries_deep_scanned"] += 1
                        diag["deep_strings"] += len(dr.strings)
                        reasons_extra.extend(dr.notes)

                elif ext in TEXT_EXTENSIONS:
                    raw = self.resources.scan(name, data)
                    if self.deep_scan and not raw:
                        dr = self.deep.scan(name, data)
                        raw = self._merge(raw, dr.strings)
                        diag["entries_deep_scanned"] += 1
                        diag["deep_strings"] += len(dr.strings)
                        reasons_extra.extend(dr.notes)

                else:
                    source_type = "deep-resource"
                    dr = self.deep.scan(name, data)
                    raw = dr.strings
                    diag["entries_deep_scanned"] += 1
                    diag["deep_strings"] += len(dr.strings)
                    reasons_extra.extend(dr.notes)

                diag["strings_before_filter"] += len(raw)
                strings = self.detector.filter_strings(raw)
                diag["strings_after_filter"] += len(strings)
                diag["strings_rejected_non_language"] += self.detector.last_filter_stats.get("rejected", 0)
                if not strings:
                    continue

                score, reasons = self.detector.score(name, strings)
                if source_type == "deep-resource":
                    score = max(score, 15)
                    reasons.append("Deep Scan: non-standard resource extension")
                reasons.extend(reasons_extra[:3])
                result.candidates.append(Candidate(name, source_type, strings, score, reasons))
        finally:
            jar.close()
            raw_file.close()

        result.candidates.sort(key=lambda c: (c.score, len(c.strings)), reverse=True)
        diag["candidates"] = len(result.candidates)
        diag["total_strings"] = sum(len(c.strings) for c in result.candidates)
        result.diagnostics = diag
        return result
