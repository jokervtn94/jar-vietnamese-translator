
import zipfile
from pathlib import Path
from models.data import JarScanResult, Candidate, ExtractedString
from core.class_reader import ClassReader, ClassFormatError
from core.resource_scanner import ResourceScanner, TEXT_EXTENSIONS, BINARY_EXTENSIONS
from core.language_detector import LanguageDetector
from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.deep_resource_scanner import DeepResourceScanner
from core.structured_game_resource import (
    CJK_RE,
    Src4ResourceAnalyzer,
    scan_java_utf_u16be,
    exclude_embedded_media,
)

class JarScanner:
    def __init__(self, deep_scan=True):
        self.resources=ResourceScanner()
        self.detector=LanguageDetector()
        self.binary_analyzer=BinaryResourceAnalyzer()
        self.deep=DeepResourceScanner()
        self.src4=Src4ResourceAnalyzer()
        self.deep_scan=deep_scan

    @staticmethod
    def _merge(primary, extra):
        seen={(x.index,x.value,x.kind) for x in primary}
        out=list(primary)
        # Also suppress duplicate values at same source offset even if detectors classify differently.
        seen_value_offset={(x.index,x.value) for x in primary}
        for x in extra:
            if (x.index,x.value,x.kind) in seen or (x.index,x.value) in seen_value_offset:
                continue
            out.append(x)
            seen.add((x.index,x.value,x.kind))
            seen_value_offset.add((x.index,x.value))
        return out

    @staticmethod
    def _restore_trusted_cjk(raw, filtered):
        """Restore structurally trusted CJK rejected by generic heuristics."""
        out=list(filtered)
        seen={(x.index,x.value,x.kind) for x in out}
        seen_value={(x.index,x.value) for x in out}
        for item in raw:
            if not CJK_RE.search(item.value):
                continue
            trusted=(
                item.kind == "class-string"
                or item.kind.startswith("src4:")
                or item.kind == "binary:u16be-length-prefixed:safe"
            )
            if not trusted:
                continue
            key=(item.index,item.value,item.kind)
            vo=(item.index,item.value)
            if key in seen or vo in seen_value:
                continue
            out.append(item)
            seen.add(key)
            seen_value.add(vo)
        return out

    def scan(self,jar_path: str, progress=None) -> JarScanResult:
        result=JarScanResult(jar_path=jar_path)
        diag={
            "entries_total":0,
            "entries_read":0,
            "entries_deep_scanned":0,
            "entries_skipped_media_or_size":0,
            "class_parse_failed":0,
            "strings_before_filter":0,
            "strings_after_filter":0,
            "strings_rejected_non_language":0,
            "deep_strings":0,
            "src4_entries":0,
            "src4_strings":0,
            "strict_java_utf_strings":0,
            "embedded_media_strings_removed":0,
        }

        with zipfile.ZipFile(jar_path,"r") as jar:
            infos=[i for i in jar.infolist() if not i.is_dir()]
            result.entries=[i.filename for i in infos]
            diag["entries_total"]=len(infos)
            try:
                result.manifest=jar.read("META-INF/MANIFEST.MF").decode("utf-8",errors="replace")
            except KeyError:
                pass

            total_infos=len(infos)
            for info_index, info in enumerate(infos, start=1):
                name=info.filename
                if progress and (info_index == 1 or info_index % 8 == 0 or info_index == total_infos):
                    progress("scan", info_index, total_infos, f"Đang quét {info_index}/{total_infos}: {name}")
                ext=Path(name).suffix.lower()

                # Hard cap for memory safety.
                if info.file_size > 16*1024*1024:
                    diag["entries_skipped_media_or_size"]+=1
                    continue

                known = ext==".class" or ext==".src4" or ext in TEXT_EXTENSIONS or ext in BINARY_EXTENSIONS
                deep_allowed = self.deep_scan and self.deep.should_scan(name,info.file_size)
                if not known and not deep_allowed:
                    diag["entries_skipped_media_or_size"]+=1
                    continue

                try:
                    data=jar.read(info)
                    diag["entries_read"]+=1
                except Exception:
                    continue

                raw=[]
                source_type="resource"
                reasons_extra=[]

                if ext==".src4":
                    source_type="src4"
                    sr=self.src4.scan(name,data)
                    raw=sr.strings
                    diag["src4_entries"]+=1
                    diag["src4_strings"]+=len(sr.strings)
                    reasons_extra.extend(sr.notes)

                elif ext==".class":
                    source_type="class"
                    try:
                        raw=ClassReader(data,name).extract_strings()
                    except ClassFormatError:
                        diag["class_parse_failed"]+=1
                        raw=[]
                    # Deep raw pass over class data can reveal obfuscator-packed text.
                    # These findings remain unsafe/discovery-only.
                    if self.deep_scan:
                        dr=self.deep.scan(name,data)
                        raw=self._merge(raw,dr.strings)
                        diag["entries_deep_scanned"]+=1
                        diag["deep_strings"]+=len(dr.strings)
                        reasons_extra.extend(dr.notes)

                elif ext in BINARY_EXTENSIONS:
                    source_type="binary"
                    # DataInputStream.readUTF uses a canonical 2-byte big-endian
                    # byte length. Run this structural probe before generic binary
                    # framing so nested u8 matches cannot own the same payload.
                    strict_utf=scan_java_utf_u16be(name,data)
                    raw=list(strict_utf)
                    diag["strict_java_utf_strings"]+=len(strict_utf)

                    analysis=self.binary_analyzer.analyze(name,data)
                    framed=[]
                    for bs in analysis.strings:
                        framed.append(ExtractedString(
                            source=name,
                            value=bs.text,
                            kind=f"binary:{bs.framing}:{'safe' if bs.patch_safe else 'unsafe'}",
                            index=bs.offset,
                            encoding=bs.encoding,
                        ))
                    raw=self._merge(raw,framed)
                    # Always supplement binary analysis with Unicode/high-recall discovery.
                    if self.deep_scan:
                        dr=self.deep.scan(name,data)
                        raw=self._merge(raw,dr.strings)
                        diag["entries_deep_scanned"]+=1
                        diag["deep_strings"]+=len(dr.strings)
                        reasons_extra.extend(dr.notes)

                    # image.pak-style containers can embed complete GIF streams.
                    # Byte sequences inside compressed image payloads are not text.
                    raw, removed=exclude_embedded_media(raw,data)
                    if removed:
                        diag["embedded_media_strings_removed"]+=removed
                        reasons_extra.append(f"Ignored {removed} candidate(s) inside embedded GIF payloads")

                elif ext in TEXT_EXTENSIONS:
                    raw=self.resources.scan(name,data)
                    # If standard parser finds nothing, deep fallback can recover unusual encoding.
                    if self.deep_scan and not raw:
                        dr=self.deep.scan(name,data)
                        raw=self._merge(raw,dr.strings)
                        diag["entries_deep_scanned"]+=1
                        diag["deep_strings"]+=len(dr.strings)
                        reasons_extra.extend(dr.notes)

                else:
                    # Previously V4.2 skipped this entry completely.
                    source_type="deep-resource"
                    dr=self.deep.scan(name,data)
                    raw=dr.strings
                    diag["entries_deep_scanned"]+=1
                    diag["deep_strings"]+=len(dr.strings)
                    reasons_extra.extend(dr.notes)

                diag["strings_before_filter"]+=len(raw)
                strings=self.detector.filter_strings(raw)
                strings=self._restore_trusted_cjk(raw,strings)
                diag["strings_after_filter"]+=len(strings)
                diag["strings_rejected_non_language"]+=max(0,len(raw)-len(strings))
                if not strings:
                    continue

                score,reasons=self.detector.score(name,strings)
                # Deep resources get a modest floor so they remain visible instead of disappearing.
                if source_type=="deep-resource":
                    score=max(score,15)
                    reasons.append("Deep Scan: non-standard resource extension")
                if source_type=="src4":
                    score=max(score,70)
                    reasons.append("Structured SRC4: decompressed Java-UTF game text")
                reasons.extend(reasons_extra[:3])
                result.candidates.append(Candidate(name,source_type,strings,score,reasons))

        result.candidates.sort(key=lambda c:(c.score,len(c.strings)),reverse=True)
        diag["candidates"]=len(result.candidates)
        diag["total_strings"]=sum(len(c.strings) for c in result.candidates)
        result.diagnostics=diag
        return result
