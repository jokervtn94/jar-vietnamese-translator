
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
        self.resources=ResourceScanner()
        self.detector=LanguageDetector()
        self.binary_analyzer=BinaryResourceAnalyzer()
        self.deep=DeepResourceScanner()
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

    def scan(self,jar_path: str) -> JarScanResult:
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
        }

        with zipfile.ZipFile(jar_path,"r") as jar:
            infos=[i for i in jar.infolist() if not i.is_dir()]
            result.entries=[i.filename for i in infos]
            diag["entries_total"]=len(infos)
            try:
                result.manifest=jar.read("META-INF/MANIFEST.MF").decode("utf-8",errors="replace")
            except KeyError:
                pass

            for info in infos:
                name=info.filename
                ext=Path(name).suffix.lower()

                # Hard cap for memory safety.
                if info.file_size > 16*1024*1024:
                    diag["entries_skipped_media_or_size"]+=1
                    continue

                known = ext==".class" or ext in TEXT_EXTENSIONS or ext in BINARY_EXTENSIONS
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

                if ext==".class":
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
                    analysis=self.binary_analyzer.analyze(name,data)
                    for bs in analysis.strings:
                        raw.append(ExtractedString(
                            source=name,
                            value=bs.text,
                            kind=f"binary:{bs.framing}:{'safe' if bs.patch_safe else 'unsafe'}",
                            index=bs.offset,
                            encoding=bs.encoding,
                        ))
                    # Always supplement binary analysis with Unicode/high-recall discovery.
                    if self.deep_scan:
                        dr=self.deep.scan(name,data)
                        raw=self._merge(raw,dr.strings)
                        diag["entries_deep_scanned"]+=1
                        diag["deep_strings"]+=len(dr.strings)
                        reasons_extra.extend(dr.notes)

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
                diag["strings_after_filter"]+=len(strings)
                diag["strings_rejected_non_language"]+=self.detector.last_filter_stats.get("rejected",0)
                if not strings:
                    continue

                score,reasons=self.detector.score(name,strings)
                # Deep resources get a modest floor so they remain visible instead of disappearing.
                if source_type=="deep-resource":
                    score=max(score,15)
                    reasons.append("Deep Scan: non-standard resource extension")
                reasons.extend(reasons_extra[:3])
                result.candidates.append(Candidate(name,source_type,strings,score,reasons))

        result.candidates.sort(key=lambda c:(c.score,len(c.strings)),reverse=True)
        diag["candidates"]=len(result.candidates)
        diag["total_strings"]=sum(len(c.strings) for c in result.candidates)
        result.diagnostics=diag
        return result
