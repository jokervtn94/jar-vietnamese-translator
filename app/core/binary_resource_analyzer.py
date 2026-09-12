from dataclasses import dataclass, field
from typing import List, Optional
import re, struct
from core.encoding_utils import (
    decode_best, scan_legacy_cjk_runs, script_count,
    decode_mixed_utf8_binary, has_structural_binary_bytes,
)

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

    @property
    def span_start(self):
        return self.length_field_offset if self.length_field_offset is not None else self.offset

    @property
    def span_end(self):
        return self.offset + self.length + self.terminator_size

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
    # UTF-8 is the only binary encoding that V4.9 will patch automatically.
    # Vietnamese output is UTF-8 and therefore a legacy GBK/Big5 field cannot
    # be safely rewritten without changing the game's decoder contract.
    try:
        strict_utf8 = bs.decode("utf-8")
    except UnicodeDecodeError:
        strict_utf8 = None
    if strict_utf8 is not None and any(ch.isalpha() for ch in strict_utf8):
        return strict_utf8, "utf-8"

    # Discovery-only recovery for records that mix raw bytes and UTF-8 islands.
    mixed, recovered = decode_mixed_utf8_binary(bs)
    if recovered and script_count(mixed) >= 2:
        return mixed, "mixed-utf8-binary"

    # Legacy encodings stay visible for extraction, but are never marked safe.
    text, enc = decode_best(bs, ("gb18030", "gbk", "big5"))
    if text and any(ch.isalpha() for ch in text):
        return text, enc

    try:
        ascii_text = bs.decode("ascii")
    except UnicodeDecodeError:
        return None, None
    if any(ch.isalpha() for ch in ascii_text):
        return ascii_text, "ascii"
    return None, None


def _decode_framed_fast(bs: bytes):
    """Fast decoder used by high-frequency u8/u16 framing probes.

    Mixed binary recovery is deliberately skipped here because mixed records are
    discovery-only and never patch-safe. The full _decode path still preserves
    that capability for null/raw discovery and regression compatibility.
    """
    try:
        text = bs.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None and any(ch.isalpha() for ch in text):
        return text, "utf-8"
    text, enc = decode_best(bs, ("gb18030", "gbk", "big5"))
    if text and any(ch.isalpha() for ch in text):
        return text, enc
    try:
        text = bs.decode("ascii")
    except UnicodeDecodeError:
        return None, None
    if any(ch.isalpha() for ch in text):
        return text, "ascii"
    return None, None


def _whole_record_patch_safe(chunk: bytes, enc: str) -> bool:
    # Safe binary rewriting is intentionally narrow.  A field must be a plain
    # UTF-8/ASCII payload with no embedded structural controls.
    if enc not in ("utf-8", "ascii"):
        return False
    return not has_structural_binary_bytes(chunk)


def scan_null_terminated(data: bytes):
    out=[]; start=0
    for i,b in enumerate(data):
        if b==0:
            chunk=data[start:i]
            if _looks_text(chunk):
                txt,enc=_decode(chunk)
                if txt:
                    safe = _whole_record_patch_safe(chunk, enc)
                    out.append(BinaryString(start,len(chunk),txt,enc,"null-terminated",82 if safe else 68,safe,terminator_size=1))
            start=i+1
    return out


def scan_u8(data: bytes):
    # Scan every byte position.  Do not jump past a detected outer record: a
    # J2ME resource can nest [len][text] fields inside a larger framed record.
    out=[]
    for i in range(0, max(0, len(data)-1)):
        n=data[i]
        if not (3 <= n <= 240 and i+1+n <= len(data)):
            continue
        chunk=data[i+1:i+1+n]
        if not _looks_text(chunk):
            continue
        txt,enc=_decode_framed_fast(chunk)
        if not txt:
            continue
        safe = _whole_record_patch_safe(chunk, enc)
        # Require at least two letters for a safe tiny field; this removes many
        # accidental one-token matches in compressed/config binary data.
        if safe and sum(ch.isalpha() for ch in txt) < 2:
            safe=False
        out.append(BinaryString(i+1,n,txt,enc,"u8-length-prefixed",94 if safe else 70,safe,length_field_offset=i))
    return out


def _scan_u16(data: bytes, endian: str, framing: str, base_conf: int):
    out=[]
    fmt=">H" if endian=="be" else "<H"
    for i in range(0, max(0, len(data)-2)):
        n=struct.unpack(fmt,data[i:i+2])[0]
        if not (3 <= n <= 4096 and i+2+n <= len(data)):
            continue
        chunk=data[i+2:i+2+n]
        if not _looks_text(chunk):
            continue
        txt,enc=_decode_framed_fast(chunk)
        if not txt:
            continue
        safe = _whole_record_patch_safe(chunk, enc)
        if safe and sum(ch.isalpha() for ch in txt) < 2:
            safe=False
        out.append(BinaryString(i+2,n,txt,enc,framing,base_conf if safe else 72,safe,length_field_offset=i))
    return out


def scan_u16be(data: bytes):
    return _scan_u16(data,"be","u16be-length-prefixed",96)


def scan_u16le(data: bytes):
    return _scan_u16(data,"le","u16le-length-prefixed",94)


def scan_raw(data: bytes, min_len=4):
    out=[]
    seen=set()
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % min_len, data):
        txt=m.group().decode("ascii","ignore")
        if any(ch.isalpha() for ch in txt):
            key=(m.start(),txt)
            if key not in seen:
                seen.add(key)
                out.append(BinaryString(m.start(),len(m.group()),txt,"ascii","raw-run",45,False))
    for enc in ("gb18030", "big5"):
        for off, raw, txt in scan_legacy_cjk_runs(data, enc, min_chars=2):
            key=(off,txt)
            if key in seen:
                continue
            seen.add(key)
            out.append(BinaryString(off,len(raw),txt,enc,"raw-cjk-run",58,False))
    return out


def _overlap(a: BinaryString, b: BinaryString) -> bool:
    return max(a.span_start,b.span_start) < min(a.span_end,b.span_end)


def _prefer(a: BinaryString, b: BinaryString) -> BinaryString:
    """Choose the better representation when two detectors overlap.

    Structured safe fields win over unsafe enclosing records.  Otherwise favor
    higher confidence and then the smaller payload, because a smaller framed
    text field is less likely to contain unrelated metadata.
    """
    ka=(1 if a.patch_safe else 0, a.confidence, -a.length)
    kb=(1 if b.patch_safe else 0, b.confidence, -b.length)
    return a if ka>=kb else b


def merge_framed_candidates(groups):
    """Merge overlapping framed detections in O(n log n) rather than O(n²).

    Candidates are processed from strongest to weakest using the same priority
    semantics as ``_prefer``.  Because a stronger candidate is always inserted
    first, a later candidate can be discarded as soon as it overlaps any kept
    interval.  A small bisect-backed interval list keeps overlap checks local.
    """
    from bisect import bisect_left

    dedup={}
    for _name, items, _base in groups:
        for s in items:
            k=(s.offset,s.length,s.text,s.framing)
            old=dedup.get(k)
            if old is None or s.confidence>old.confidence:
                dedup[k]=s

    ordered=sorted(
        dedup.values(),
        key=lambda s:(1 if s.patch_safe else 0, s.confidence, -s.length, -s.offset),
        reverse=True,
    )
    kept=[]
    starts=[]
    for cand in ordered:
        cs, ce = cand.span_start, cand.span_end
        pos=bisect_left(starts, cs)
        conflict=False
        # Check intervals immediately to the left while their end can reach cs.
        j=pos-1
        while j>=0:
            other=kept[j]
            if other.span_end <= cs:
                break
            if _overlap(cand, other):
                conflict=True
                break
            j-=1
        # Check intervals to the right while their start is before ce.
        if not conflict:
            j=pos
            while j<len(kept) and kept[j].span_start < ce:
                if _overlap(cand, kept[j]):
                    conflict=True
                    break
                j+=1
        if conflict:
            continue
        kept.insert(pos,cand)
        starts.insert(pos,cs)
    return kept


class BinaryResourceAnalyzer:
    def analyze(self, source: str, data: bytes) -> BinaryAnalysis:
        groups = [
            ("u16be-length-prefixed", scan_u16be(data), 96),
            ("u16le-length-prefixed", scan_u16le(data), 94),
            ("u8-length-prefixed", scan_u8(data), 94),
            ("null-terminated", scan_null_terminated(data), 82),
        ]
        strings=merge_framed_candidates(groups)
        if strings:
            framings=sorted({s.framing for s in strings})
            safe=sum(1 for s in strings if s.patch_safe)
            fmt=framings[0] if len(framings)==1 else "mixed-framing"
            conf=max((s.confidence for s in strings),default=70)
            return BinaryAnalysis(
                source,fmt,min(99,conf),strings,
                [
                    f"Detected {len(framings)} framing type(s): {', '.join(framings)}",
                    f"{len(strings)} non-overlapping framed field(s)",
                    f"{safe} field(s) patch-safe; unsafe/enclosing records locked.",
                ]
            )
        raw=scan_raw(data)
        notes=["No reliable framing detected."]
        if raw:
            notes.append(f"Found {len(raw)} raw printable runs; patching disabled.")
        return BinaryAnalysis(source,"raw/unknown",45 if raw else 10,raw,notes)
