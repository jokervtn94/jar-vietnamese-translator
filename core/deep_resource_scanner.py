
from dataclasses import dataclass, field
from typing import List
import re
from models.data import ExtractedString

MEDIA_EXTENSIONS = {
    ".png",".jpg",".jpeg",".gif",".bmp",".ico",
    ".mp3",".wav",".mid",".midi",".amr",".ogg",".aac",
    ".mp4",".3gp",".avi",".m4a",
}
ARCHIVE_EXTENSIONS = {".zip",".jar",".gz",".bz2",".7z",".rar"}
NATIVE_EXTENSIONS = {".dll",".so",".exe",".dex"}

@dataclass
class DeepScanResult:
    strings: List[ExtractedString] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

def _human_score(s: str) -> float:
    if not s:
        return 0.0
    printable=sum(ch.isprintable() or ch in "\t\r\n" for ch in s)
    letters=sum(ch.isalpha() for ch in s)
    weird=sum(ord(ch)<32 and ch not in "\t\r\n" for ch in s)
    return (printable/max(1,len(s))) * 0.55 + (letters/max(1,len(s))) * 0.55 - weird*0.2

def _looks_human(s: str, min_len=2) -> bool:
    s=s.strip()
    if len(s)<min_len or len(s)>800:
        return False
    if not any(ch.isalpha() for ch in s):
        return False
    # reject long binary-ish identifiers/descriptors, but retain short UI tokens.
    if len(s)>12 and re.fullmatch(r'[A-Za-z0-9_/$.;<>\[\]():+-]+',s) and (
        "/" in s or ";" in s or s.count(".")>=2
    ):
        return False
    return _human_score(s)>=0.55

class DeepResourceScanner:
    """High-recall detector. Results are discovery-only unless an existing safe patcher owns the format."""

    def should_scan(self, source: str, size: int) -> bool:
        low=source.lower()
        ext=("."+low.rsplit(".",1)[1]) if "." in low.rsplit("/",1)[-1] else ""
        if size<=0 or size>12*1024*1024:
            return False
        if ext in MEDIA_EXTENSIONS or ext in ARCHIVE_EXTENSIONS or ext in NATIVE_EXTENSIONS:
            return False
        return True

    def scan(self, source: str, data: bytes) -> DeepScanResult:
        out=[]
        notes=[]
        seen=set()

        def add(value,kind,index,enc):
            clean=value.strip("\x00\r\n\t ")
            key=(index,clean,kind)
            if key in seen or not _looks_human(clean):
                return
            seen.add(key)
            out.append(ExtractedString(source,clean,kind,index,enc))

        # Whole-file text detection. This catches uncommon extensions such as .cfg/.loc/.db/.pak
        # when their payload is actually textual.
        enc_candidates=[]
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            enc_candidates=["utf-16"]
        elif data.startswith(b"\xef\xbb\xbf"):
            enc_candidates=["utf-8-sig"]
        else:
            enc_candidates=["utf-8","utf-16le","utf-16be","cp1252","latin-1"]

        for enc in enc_candidates:
            try:
                text=data.decode(enc)
            except Exception:
                continue
            if not text:
                continue
            printable=sum(ch.isprintable() or ch in "\r\n\t" for ch in text)/max(1,len(text))
            nul=text.count("\x00")/max(1,len(text))
            if printable>=0.88 and nul<0.03:
                for i,line in enumerate(text.splitlines()):
                    line=line.strip()
                    if not line or line.startswith(("#",";","//")):
                        continue
                    # common key=value / key:value language tables
                    val=line
                    if "=" in line:
                        left,right=line.split("=",1)
                        if right.strip():
                            val=right.strip()
                    elif ":" in line and len(line.split(":",1)[0])<40:
                        left,right=line.split(":",1)
                        if right.strip():
                            val=right.strip()
                    add(val,"deep-text",i,enc)
                if out:
                    notes.append(f"Whole-file text detected as {enc}")
                    break

        # Raw ASCII/UTF-8-ish runs. Unsafe for patching but excellent for discovery.
        for m in re.finditer(rb'[\x20-\x7e]{2,}',data):
            try:
                s=m.group().decode("ascii")
            except Exception:
                continue
            add(s,"deep-binary-ascii",m.start(),"ascii")

        # UTF-8 runs with non-ASCII. Conservative byte grouping.
        for m in re.finditer(rb'(?:[\x20-\x7e]|[\xc2-\xf4][\x80-\xbf]{1,3}){2,}',data):
            raw=m.group()
            try:
                s=raw.decode("utf-8")
            except Exception:
                continue
            if any(ord(ch)>127 for ch in s):
                add(s,"deep-binary-utf8",m.start(),"utf-8")

        # UTF-16LE printable runs (very common in ports/tools even with odd extensions).
        i=0
        while i+4<=len(data):
            start=i
            chars=[]
            while i+2<=len(data):
                unit=int.from_bytes(data[i:i+2],"little")
                ch=chr(unit)
                if (32<=unit<=126) or ch.isalpha() or ch in "\t":
                    chars.append(ch); i+=2
                else:
                    break
            if len(chars)>=2:
                add("".join(chars),"deep-binary-utf16le",start,"utf-16le")
            i=max(i+2,start+2)

        # UTF-16BE printable runs.
        i=0
        while i+4<=len(data):
            start=i
            chars=[]
            while i+2<=len(data):
                unit=int.from_bytes(data[i:i+2],"big")
                ch=chr(unit)
                if (32<=unit<=126) or ch.isalpha() or ch in "\t":
                    chars.append(ch); i+=2
                else:
                    break
            if len(chars)>=2:
                add("".join(chars),"deep-binary-utf16be",start,"utf-16be")
            i=max(i+2,start+2)

        if out:
            notes.append(f"Deep scan found {len(out)} possible text strings")
        return DeepScanResult(out,notes)
