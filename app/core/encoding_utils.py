import re
from typing import Iterable, List, Optional, Tuple

CJK_RANGES = (
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
    (0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF),
    (0xAC00, 0xD7AF),
)

DEFAULT_ENCODINGS = (
    "utf-8-sig", "utf-8", "gb18030", "gbk", "big5",
    "utf-16", "utf-16le", "utf-16be", "cp1252", "latin-1",
)

MOJIBAKE_MARKERS = ("Ã", "Â", "æ", "ç", "å", "é", "ð", "ï", "¤", "¦", "¥", "", "")


def is_cjk_char(ch: str) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in CJK_RANGES)


def script_count(text: str) -> int:
    return sum(1 for ch in text if is_cjk_char(ch))


def repair_utf8_mojibake(text: str) -> str:
    """Recover the common case where UTF-8 bytes were decoded as Latin-1/cp1252."""
    if not text or not any(m in text for m in MOJIBAKE_MARKERS):
        return text
    best = text
    best_score = _quality_score(text)
    for enc in ("latin-1", "cp1252"):
        try:
            candidate = text.encode(enc).decode("utf-8")
        except Exception:
            continue
        score = _quality_score(candidate)
        if score > best_score + 0.08:
            best, best_score = candidate, score
    return best


def _quality_score(text: str) -> float:
    if not text:
        return -10.0
    n = len(text)
    printable = sum(ch.isprintable() or ch in "\t\r\n" for ch in text) / n
    controls = sum(ord(ch) < 32 and ch not in "\t\r\n" for ch in text) / n
    replacement = text.count("\ufffd") / n
    letters = sum(ch.isalpha() for ch in text) / n
    cjk = script_count(text) / n
    mojibake = sum(text.count(m) for m in MOJIBAKE_MARKERS) / n
    nul = text.count("\x00") / n
    # CJK text often has no spaces; reward script validity rather than Latin word shape.
    return printable * 1.2 + letters * 0.6 + cjk * 0.9 - controls * 1.7 - replacement * 3.0 - mojibake * 0.9 - nul * 1.2


def decode_candidates(data: bytes, encodings: Iterable[str] = DEFAULT_ENCODINGS) -> List[Tuple[str, str, float]]:
    out = []
    seen = set()
    for enc in encodings:
        try:
            text = data.decode(enc)
        except Exception:
            continue
        repaired = repair_utf8_mojibake(text)
        key = repaired
        if key in seen:
            continue
        seen.add(key)
        out.append((repaired, enc, _quality_score(repaired)))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


def decode_best(data: bytes, encodings: Iterable[str] = DEFAULT_ENCODINGS) -> Tuple[str, str]:
    candidates = decode_candidates(data, encodings)
    if not candidates:
        return data.decode("latin-1", errors="replace"), "latin-1"
    text, enc, _ = candidates[0]
    return text, enc




def decode_mixed_utf8_binary(data: bytes) -> Tuple[str, bool]:
    """Losslessly render binary data while decoding valid UTF-8 islands.

    This is intentionally different from ``data.decode('utf-8', errors=...)``:
    invalid/structural bytes are preserved 1:1 as U+0000..U+00FF while valid
    multi-byte UTF-8 sequences are decoded to Unicode.  It fixes game records
    such as ``<control><UTF-8 Chinese><control><UTF-8 Chinese><raw byte>``
    without throwing away the structural bytes.

    Returns ``(text, recovered)`` where recovered is True when at least one
    non-ASCII UTF-8 sequence was decoded.
    """
    out = []
    recovered = False
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        width = 0
        if 0xC2 <= b <= 0xDF:
            width = 2
        elif 0xE0 <= b <= 0xEF:
            width = 3
        elif 0xF0 <= b <= 0xF4:
            width = 4
        if width and i + width <= n:
            raw = data[i:i + width]
            if all(0x80 <= x <= 0xBF for x in raw[1:]):
                try:
                    ch = raw.decode('utf-8')
                except UnicodeDecodeError:
                    ch = ''
                if ch:
                    out.append(ch)
                    recovered = True
                    i += width
                    continue
        # Preserve all non-UTF8 bytes exactly as Latin-1 code points.
        out.append(chr(b))
        i += 1
    return ''.join(out), recovered


def has_structural_binary_bytes(data: bytes) -> bool:
    """True when a framed payload contains bytes that are unlikely text.

    Tabs/newlines/CR are allowed; other C0 controls and stray high bytes that
    are not part of a valid whole UTF-8 string make whole-record replacement
    unsafe.
    """
    if any(b < 0x20 and b not in (0x09, 0x0A, 0x0D) for b in data):
        return True
    try:
        data.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True

def _gb18030_unit(data: bytes, i: int) -> int:
    b = data[i]
    if 0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D):
        return 1
    if 0x81 <= b <= 0xFE and i + 1 < len(data):
        b2 = data[i + 1]
        if 0x40 <= b2 <= 0xFE and b2 != 0x7F:
            return 2
        if 0x30 <= b2 <= 0x39 and i + 3 < len(data):
            b3, b4 = data[i + 2], data[i + 3]
            if 0x81 <= b3 <= 0xFE and 0x30 <= b4 <= 0x39:
                return 4
    return 0


def _big5_unit(data: bytes, i: int) -> int:
    b = data[i]
    if 0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D):
        return 1
    if 0x81 <= b <= 0xFE and i + 1 < len(data):
        b2 = data[i + 1]
        if 0x40 <= b2 <= 0x7E or 0xA1 <= b2 <= 0xFE:
            return 2
    return 0


def scan_legacy_cjk_runs(data: bytes, encoding: str, min_chars: int = 2, max_bytes: int = 4096):
    """Yield (offset, raw, text) for GB18030/Big5-like text runs in arbitrary binary data.

    Discovery only: callers should not mark these runs patch-safe without framing evidence.
    """
    unit = _gb18030_unit if encoding in ("gb18030", "gbk") else _big5_unit
    i = 0
    n = len(data)
    while i < n:
        start = i
        j = i
        non_ascii_units = 0
        while j < n and j - start < max_bytes:
            width = unit(data, j)
            if width == 0:
                break
            if width > 1:
                non_ascii_units += 1
            j += width
        if j > start and non_ascii_units > 0:
            raw = data[start:j]
            try:
                text = raw.decode(encoding)
            except Exception:
                text = ""
            text = repair_utf8_mojibake(text)
            if text and script_count(text) >= min_chars:
                yield start, raw, text
        i = max(start + 1, j + 1 if j == start else j)
