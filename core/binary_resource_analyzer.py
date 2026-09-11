
from dataclasses import dataclass, field
from typing import List, Optional
import re, struct

@dataclass
class BinaryString:
    offset: int
    length: int
    text: str
    encoding: str
    framing: str
    confidence: int
    patch_safe: bool
    length_field_offset: Optional[int] = None
    terminator_size: int = 0

@dataclass
class BinaryAnalysis:
    source: str
    format_name: str = "unknown"
    confidence: int = 0
    strings: List[BinaryString] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def safe_count(self):
        return sum(1 for s in self.strings if s.patch_safe)

    @property
    def total_count(self):
        return len(self.strings)

PRINTABLE = set(range(0x20, 0x7f)) | {0x09}

def _looks_text(bs: bytes, min_len=3):
    if len(bs) < min_len:
        return False
    printable = sum(1 for b in bs if b in PRINTABLE or b >= 0x80)
    return printable / max(1, len(bs)) >= 0.85

def _decode(bs: bytes):
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            s = bs.decode(enc)
            if any(ch.isalpha() for ch in s):
                return s, enc
        except Exception:
            pass
    return None, None

def scan_null_terminated(data: bytes):
    out=[]; start=0
    for i,b in enumerate(data):
        if b==0:
            chunk=data[start:i]
            if _looks_text(chunk):
                txt,enc=_decode(chunk)
                if txt:
                    out.append(BinaryString(start,len(chunk),txt,enc,"null-terminated",82,True,terminator_size=1))
            start=i+1
    return out

def scan_u8(data: bytes):
    out=[]; i=0
    while i < len(data)-2:
        n=data[i]
        if 3 <= n <= 240 and i+1+n <= len(data):
            chunk=data[i+1:i+1+n]
            if _looks_text(chunk):
                txt,enc=_decode(chunk)
                if txt:
                    out.append(BinaryString(i+1,n,txt,enc,"u8-length-prefixed",88,True,length_field_offset=i))
                    i += 1+n; continue
        i+=1
    return out

def scan_u16be(data: bytes):
    out=[]; i=0
    while i < len(data)-4:
        n=struct.unpack(">H",data[i:i+2])[0]
        if 3 <= n <= 4096 and i+2+n <= len(data):
            chunk=data[i+2:i+2+n]
            if _looks_text(chunk):
                txt,enc=_decode(chunk)
                if txt:
                    out.append(BinaryString(i+2,n,txt,enc,"u16be-length-prefixed",92,True,length_field_offset=i))
                    i += 2+n; continue
        i+=1
    return out

def scan_u16le(data: bytes):
    out=[]; i=0
    while i < len(data)-4:
        n=struct.unpack("<H",data[i:i+2])[0]
        if 3 <= n <= 4096 and i+2+n <= len(data):
            chunk=data[i+2:i+2+n]
            if _looks_text(chunk):
                txt,enc=_decode(chunk)
                if txt:
                    out.append(BinaryString(i+2,n,txt,enc,"u16le-length-prefixed",90,True,length_field_offset=i))
                    i += 2+n; continue
        i+=1
    return out

def scan_raw(data: bytes, min_len=4):
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % min_len, data):
        txt=m.group().decode("ascii","ignore")
        if any(ch.isalpha() for ch in txt):
            out.append(BinaryString(m.start(),len(m.group()),txt,"ascii","raw-run",45,False))
    return out

class BinaryResourceAnalyzer:
    def analyze(self, source: str, data: bytes) -> BinaryAnalysis:
        candidates = [
            ("u16be-length-prefixed", scan_u16be(data), 92),
            ("u16le-length-prefixed", scan_u16le(data), 90),
            ("u8-length-prefixed", scan_u8(data), 88),
            ("null-terminated", scan_null_terminated(data), 82),
        ]
        candidates.sort(key=lambda x:(len(x[1]),x[2]), reverse=True)
        fmt, strings, base = candidates[0]
        if strings:
            return BinaryAnalysis(
                source, fmt, min(99, base + min(7, len(strings)//5)), strings,
                [f"Detected {fmt}", f"{len(strings)} framed strings", "Safe patch only for framed entries."]
            )
        raw=scan_raw(data)
        notes=["No reliable framing detected."]
        if raw:
            notes.append(f"Found {len(raw)} raw printable runs; patching disabled.")
        return BinaryAnalysis(source,"raw/unknown",45 if raw else 10,raw,notes)
