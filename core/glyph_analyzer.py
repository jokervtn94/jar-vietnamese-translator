
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Dict
import re, zipfile

VIETNAMESE_EXTRA = (
    "ăâđêôơưĂÂĐÊÔƠƯ"
    "áàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
    "íìỉĩịóòỏõọốồổỗộớờởỡợ"
    "úùủũụứừửữựýỳỷỹỵ"
    "ÁÀẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆ"
    "ÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢ"
    "ÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ"
)

@dataclass
class FontMap:
    source: str
    glyphs: Set[str] = field(default_factory=set)
    codepoints: Set[int] = field(default_factory=set)
    format_name: str = "unknown"
    confidence: int = 0
    notes: List[str] = field(default_factory=list)

@dataclass
class GlyphReport:
    required_chars: Set[str] = field(default_factory=set)
    mapped_chars: Set[str] = field(default_factory=set)
    missing_chars: Set[str] = field(default_factory=set)
    maps: List[FontMap] = field(default_factory=list)
    confidence: int = 0
    risk: str = "unknown"
    notes: List[str] = field(default_factory=list)

class GlyphAnalyzer:
    def _parse_bmfont_text(self, source: str, text: str):
        cps=set()
        # BMFont text format: char id=65 ...
        for m in re.finditer(r'\bchar\s+id\s*=\s*(\d+)', text, re.I):
            try:
                cps.add(int(m.group(1)))
            except Exception:
                pass
        # Some descriptors use id= without leading 'char'
        if not cps:
            for m in re.finditer(r'\bid\s*=\s*(\d+)', text, re.I):
                try:
                    cp=int(m.group(1))
                    if 0 <= cp <= 0x10FFFF:
                        cps.add(cp)
                except Exception:
                    pass
        if cps:
            glyphs={chr(cp) for cp in cps if 0 <= cp <= 0x10FFFF}
            return FontMap(source,glyphs,cps,"BMFont-text",95,[f"{len(cps)} codepoints parsed"])
        return None

    def _parse_codepoint_list(self, source: str, text: str):
        cps=set()
        # U+XXXX patterns
        for m in re.finditer(r'U\+([0-9A-Fa-f]{2,6})', text):
            cp=int(m.group(1),16)
            if 0 <= cp <= 0x10FFFF:
                cps.add(cp)
        # decimal comma/space-separated mapping lines, but require keywords
        if re.search(r'charset|glyph|char|codepoint|unicode', text, re.I):
            for m in re.finditer(r'(?<!\d)(\d{2,6})(?!\d)', text):
                cp=int(m.group(1))
                if 32 <= cp <= 0x10FFFF:
                    cps.add(cp)
        if cps:
            return FontMap(source,{chr(cp) for cp in cps},cps,"codepoint-list",75,[f"{len(cps)} codepoints inferred"])
        return None

    def _parse_literal_charset(self, source: str, text: str):
        # Common custom-font descriptor patterns:
        # chars=ABCDEFGHIJKLMNOPQRSTUVWXYZ...
        # charset: "..."
        m=re.search(r'(?:chars?|charset)\s*[:=]\s*["\']?([^\r\n"\']{4,})', text, re.I)
        if not m:
            return None
        s=m.group(1).strip()
        glyphs={ch for ch in s if not ch.isspace()}
        if len(glyphs) < 4:
            return None
        return FontMap(source,glyphs,{ord(ch) for ch in glyphs},"literal-charset",82,[f"{len(glyphs)} literal glyphs parsed"])

    def parse_font_descriptor(self, source: str, data: bytes):
        for enc in ("utf-8","cp1252","latin-1"):
            try:
                text=data.decode(enc)
                break
            except Exception:
                text=None
        if text is None:
            return None
        for parser in (self._parse_bmfont_text,self._parse_literal_charset,self._parse_codepoint_list):
            fm=parser(source,text)
            if fm:
                return fm
        return None

    def _required_from_project(self, result, project):
        chars=set()
        if result is None or project is None:
            return chars
        for _,s in result.all_strings():
            vi=project.get(s.key)
            if vi:
                chars.update(ch for ch in vi if not ch.isspace())
        return chars

    def analyze(self, jar_path: str, result=None, project=None):
        report=GlyphReport()
        report.required_chars=self._required_from_project(result,project)
        if not report.required_chars:
            report.required_chars=set(VIETNAMESE_EXTRA)

        with zipfile.ZipFile(jar_path,"r") as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > 2*1024*1024:
                    continue
                name=info.filename
                low=name.lower()
                ext=Path(name).suffix.lower()
                if ext not in {".fnt",".txt",".ini",".cfg",".xml",".properties",".dat",".res"}:
                    continue
                if not any(k in low for k in ("font","glyph","char","charset")) and ext != ".fnt":
                    continue
                try:
                    fm=self.parse_font_descriptor(name,z.read(info))
                except Exception:
                    fm=None
                if fm:
                    report.maps.append(fm)
                    report.mapped_chars.update(fm.glyphs)

        if report.maps:
            report.missing_chars={c for c in report.required_chars if c not in report.mapped_chars}
            best=max(m.confidence for m in report.maps)
            report.confidence=best
            if report.missing_chars:
                report.risk="high" if any(ord(c)>127 for c in report.missing_chars) else "medium"
                report.notes.append(f"{len(report.missing_chars)} required glyphs are not present in parsed font maps.")
            else:
                report.risk="low"
                report.notes.append("All required characters are present in parsed font maps.")
        else:
            report.risk="unknown"
            report.confidence=20
            report.missing_chars=set()
            report.notes.append("No parseable font descriptor found. Sprite atlas may use proprietary mapping.")

        return report
