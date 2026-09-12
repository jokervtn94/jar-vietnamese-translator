
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import re, zipfile
from core.glyph_analyzer import GlyphAnalyzer

VIETNAMESE_CHARS = set(
    "ăâđêôơưĂÂĐÊÔƠƯ"
    "áàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
    "íìỉĩịóòỏõọốồổỗộớờởỡợ"
    "úùủũụứừửữựýỳỷỹỵ"
    "ÁÀẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆ"
    "ÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢ"
    "ÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ"
)

FONT_NAME_HINTS = (
    "font", "fonts", "glyph", "glyphs", "charset", "char", "chars",
    "fnt", "bitmapfont", "spritefont", "textfont"
)

IMAGE_EXTS = {".png", ".gif", ".jpg", ".jpeg", ".bmp"}
FONT_EXTS = {".fnt", ".ttf", ".otf", ".bdf", ".fon"}

@dataclass
class CompatibilityFinding:
    category: str
    severity: str
    source: str
    message: str

@dataclass
class CompatibilityReport:
    encoding_risk: str = "unknown"
    font_risk: str = "unknown"
    unicode_evidence: int = 0
    custom_font_evidence: int = 0
    findings: List[CompatibilityFinding] = field(default_factory=list)
    font_candidates: List[str] = field(default_factory=list)
    suspicious_images: List[str] = field(default_factory=list)

    @property
    def overall_risk(self):
        ranks={"low":0,"medium":1,"high":2,"unknown":1}
        r=max(ranks.get(self.encoding_risk,1),ranks.get(self.font_risk,1))
        return ["low","medium","high"][r]

class CompatibilityAnalyzer:
    def analyze(self, jar_path: str, result=None, project=None) -> CompatibilityReport:
        report=CompatibilityReport()
        entries=[]
        with zipfile.ZipFile(jar_path,"r") as z:
            entries=[i.filename for i in z.infolist() if not i.is_dir()]
            # Font candidates by extension/name
            for name in entries:
                low=name.lower()
                ext=Path(name).suffix.lower()
                base=Path(name).name.lower()
                if ext in FONT_EXTS or any(h in base for h in FONT_NAME_HINTS):
                    report.font_candidates.append(name)
                    report.custom_font_evidence += 2 if ext in FONT_EXTS else 1
                if ext in IMAGE_EXTS and any(h in base for h in FONT_NAME_HINTS):
                    report.suspicious_images.append(name)
                    report.custom_font_evidence += 2

            # Inspect small textual resources for charset/font mapping hints
            for name in entries:
                ext=Path(name).suffix.lower()
                if ext not in {".txt",".properties",".xml",".ini",".cfg",".json",".csv",".lang",".lng",".dat",".bin",".res"}:
                    continue
                try:
                    info=z.getinfo(name)
                    if info.file_size > 2*1024*1024:
                        continue
                    data=z.read(name)
                except Exception:
                    continue
                lowdata=data.lower()
                for token in (b"utf-8", b"utf8", b"unicode", b"charset", b"glyph"):
                    if token in lowdata:
                        report.unicode_evidence += 1
                        report.findings.append(
                            CompatibilityFinding("encoding","low",name,f"Found marker: {token.decode('ascii','ignore')}")
                        )
                        break

        # Analyze translations actually entered
        translated_text=[]
        if result is not None and project is not None:
            for _,s in result.all_strings():
                vi=project.get(s.key)
                if vi:
                    translated_text.append((s.source,vi,s.encoding or ""))

        uses_vietnamese=False
        non_ascii_count=0
        encoding_failures=[]
        for source,text,enc in translated_text:
            if any(ch in VIETNAMESE_CHARS for ch in text):
                uses_vietnamese=True
            if any(ord(ch)>127 for ch in text):
                non_ascii_count += 1
            if enc and enc.lower() not in ("utf-8","utf8"):
                try:
                    text.encode(enc)
                except Exception:
                    encoding_failures.append((source,enc))
                    report.findings.append(
                        CompatibilityFinding("encoding","high",source,f"Vietnamese translation cannot be encoded as {enc}.")
                    )

        # Encoding risk heuristic
        if encoding_failures:
            report.encoding_risk="high"
        elif report.unicode_evidence > 0:
            report.encoding_risk="low"
        elif uses_vietnamese or non_ascii_count:
            report.encoding_risk="medium"
            report.findings.append(
                CompatibilityFinding("encoding","medium","JAR",
                    "No explicit UTF-8/Unicode marker found. Vietnamese text may still work, but runtime support is unverified.")
            )
        else:
            report.encoding_risk="unknown"

        # Font risk heuristic
        if report.custom_font_evidence >= 3:
            report.font_risk="high" if uses_vietnamese else "medium"
            report.findings.append(
                CompatibilityFinding("font","high" if uses_vietnamese else "medium","JAR",
                    "Strong custom/bitmap font evidence found. Vietnamese glyphs may be missing even if string encoding is valid.")
            )
        elif report.custom_font_evidence > 0:
            report.font_risk="medium"
            report.findings.append(
                CompatibilityFinding("font","medium","JAR",
                    "Possible custom font resources detected. Check Vietnamese glyph coverage on device/emulator.")
            )
        else:
            report.font_risk="low"
            report.findings.append(
                CompatibilityFinding("font","low","JAR",
                    "No obvious custom font resources detected; game may rely on system fonts.")
            )

        if uses_vietnamese and report.font_risk != "low":
            report.findings.append(
                CompatibilityFinding("font","high","Translations",
                    "Vietnamese diacritics are present in the translation set; missing glyphs can appear as boxes/blanks.")
            )

        # V3.5: parse actual glyph maps when available
        try:
            glyph_report = GlyphAnalyzer().analyze(jar_path, result, project)
            if glyph_report.maps:
                if glyph_report.risk == "high":
                    report.font_risk = "high"
                    report.findings.append(
                        CompatibilityFinding("glyph","high","JAR",
                            f"{len(glyph_report.missing_chars)} required glyphs are missing from parsed font maps.")
                    )
                elif glyph_report.risk == "low":
                    report.findings.append(
                        CompatibilityFinding("glyph","low","JAR",
                            "Parsed font maps contain all currently required translation characters.")
                    )
            else:
                report.findings.append(
                    CompatibilityFinding("glyph","medium","JAR",
                        "No parseable glyph map found; proprietary sprite-font mapping remains unverified.")
                )
        except Exception:
            pass

        return report
