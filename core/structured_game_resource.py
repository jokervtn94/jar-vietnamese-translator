from dataclasses import dataclass, field
from typing import List, Tuple
import re

from models.data import ExtractedString

CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')


@dataclass
class StructuredScanResult:
    strings: List[ExtractedString] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def decode_modified_utf8(raw: bytes) -> str:
    """Decode the Java/J2ME Modified UTF-8 form used by DataInputStream.readUTF."""
    raw = raw.replace(b"\xC0\x80", b"\x00")
    text = raw.decode("utf-8", errors="surrogatepass")
    out = []
    i = 0
    while i < len(text):
        o = ord(text[i])
        if 0xD800 <= o <= 0xDBFF and i + 1 < len(text):
            o2 = ord(text[i + 1])
            if 0xDC00 <= o2 <= 0xDFFF:
                out.append(chr(0x10000 + ((o - 0xD800) << 10) + (o2 - 0xDC00)))
                i += 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _looks_player_text(text: str) -> bool:
    if not text or len(text) > 800 or "\x00" in text:
        return False
    if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in text):
        return False
    if CJK_RE.search(text):
        return True
    letters = sum(ch.isalpha() for ch in text)
    return letters >= 2 and (" " in text or any(ch in ".,!?;:'\"-" for ch in text))


def scan_java_utf_u16be(source: str, data: bytes, kind: str = "binary:u16be-length-prefixed:safe") -> List[ExtractedString]:
    """High-confidence DataInputStream.readUTF-style carving."""
    found = []
    for prefix in range(0, max(0, len(data) - 2)):
        n = int.from_bytes(data[prefix:prefix + 2], "big")
        if not (1 <= n <= 65535) or prefix + 2 + n > len(data):
            continue
        raw = data[prefix + 2:prefix + 2 + n]
        try:
            text = decode_modified_utf8(raw)
        except (UnicodeDecodeError, ValueError):
            continue
        if not _looks_player_text(text):
            continue
        found.append((prefix, prefix + 2 + n, ExtractedString(
            source=source,
            value=text,
            kind=kind,
            index=prefix + 2,
            encoding="MUTF-8",
        )))

    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept = []
    end = -1
    for start, stop, item in found:
        if start < end:
            continue
        kept.append(item)
        end = stop
    return kept


def _read_bits(buf: bytes, state: list[int], count: int) -> int:
    value = 0
    for bit in range(count):
        byte_i, bit_i = state
        if byte_i >= len(buf):
            raise ValueError("SRC4 compressed bitstream ended early")
        value |= ((buf[byte_i] >> bit_i) & 1) << bit
        bit_i += 1
        if bit_i == 8:
            byte_i += 1
            bit_i = 0
        state[0], state[1] = byte_i, bit_i
    return value


def decompress_src4_blob(blob: bytes) -> bytes:
    """Mirror ClassA.a(byte[]) from the game."""
    if len(blob) < 2:
        raise ValueError("SRC4 compressed blob too short")
    out_len = int.from_bytes(blob[:2], "little")
    out = bytearray(out_len + 32)
    state = [2, 0]
    pos = 0
    while pos < out_len:
        flag = _read_bits(blob, state, 1)
        if flag == 0:
            out[pos] = _read_bits(blob, state, 8)
            pos += 1
            continue
        run_len = _read_bits(blob, state, 4) + 2
        back = _read_bits(blob, state, 12)
        src = back if pos <= 4095 else pos - 4095 + back
        if src < 0 or src + run_len > len(out):
            raise ValueError("SRC4 invalid LZ reference")
        chunk = bytes(out[src:src + run_len])
        out[pos:pos + run_len] = chunk
        pos += run_len
    return bytes(out[:out_len])


def split_src4_records(data: bytes) -> List[bytes]:
    """Extract the five RMS records stored in a .src4 container."""
    if len(data) < 10:
        raise ValueError("SRC4 header too short")
    records = []
    previous_end = 10
    for i in range(5):
        relative = int.from_bytes(data[i * 2:i * 2 + 2], "little")
        length_offset = (i + 1) * 2 + relative
        if length_offset < 10 or length_offset + 2 > len(data):
            raise ValueError(f"SRC4 record {i + 1} offset out of bounds")
        length = int.from_bytes(data[length_offset:length_offset + 2], "little")
        start = length_offset + 2
        end = start + length
        if end > len(data):
            raise ValueError(f"SRC4 record {i + 1} length out of bounds")
        if i and length_offset < previous_end:
            raise ValueError("SRC4 record table is not monotonic")
        records.append(data[start:end])
        previous_end = end
    return records


def decompress_src4_record(record: bytes) -> bytes:
    """Decode compressed RMS record 4/5 payload."""
    if len(record) < 4:
        raise ValueError("SRC4 compressed record too short")
    bitstream_len = int.from_bytes(record[:2], "little")
    blob_len = bitstream_len + 2
    if 2 + blob_len > len(record):
        raise ValueError("SRC4 compressed record length mismatch")
    blob = record[2:2 + blob_len]
    return decompress_src4_blob(blob)


class Src4ResourceAnalyzer:
    """Structured scanner for five-record .src4 game resources."""

    TEXT_RECORDS = (4, 5)

    def scan(self, source: str, data: bytes) -> StructuredScanResult:
        notes = []
        strings = []
        try:
            records = split_src4_records(data)
        except ValueError as exc:
            return StructuredScanResult([], [f"SRC4 rejected: {exc}"])

        for record_no in self.TEXT_RECORDS:
            try:
                decoded = decompress_src4_record(records[record_no - 1])
            except ValueError as exc:
                notes.append(f"SRC4 record {record_no} decompress failed: {exc}")
                continue
            found = scan_java_utf_u16be(
                source,
                decoded,
                kind=f"src4:r{record_no}:java-utf:safe",
            )
            strings.extend(found)
            notes.append(
                f"SRC4 record {record_no}: decompressed {len(decoded)} bytes, "
                f"found {len(found)} Java-UTF language field(s)"
            )
        return StructuredScanResult(strings, notes)


def _parse_gif_end(data: bytes, start: int) -> int | None:
    """Return exclusive GIF end offset, or None when the stream is invalid."""
    if data[start:start + 6] not in (b"GIF87a", b"GIF89a"):
        return None
    p = start + 6
    if p + 7 > len(data):
        return None
    packed = data[p + 4]
    p += 7
    if packed & 0x80:
        p += 3 * (1 << ((packed & 0x07) + 1))
        if p > len(data):
            return None

    def skip_subblocks(pos: int) -> int | None:
        while True:
            if pos >= len(data):
                return None
            n = data[pos]
            pos += 1
            if n == 0:
                return pos
            pos += n
            if pos > len(data):
                return None

    while p < len(data):
        marker = data[p]
        p += 1
        if marker == 0x3B:
            return p
        if marker == 0x21:
            if p >= len(data):
                return None
            p += 1
            p = skip_subblocks(p)
            if p is None:
                return None
            continue
        if marker == 0x2C:
            if p + 9 > len(data):
                return None
            local_packed = data[p + 8]
            p += 9
            if local_packed & 0x80:
                p += 3 * (1 << ((local_packed & 0x07) + 1))
                if p > len(data):
                    return None
            if p >= len(data):
                return None
            p += 1
            p = skip_subblocks(p)
            if p is None:
                return None
            continue
        return None
    return None


def embedded_gif_regions(data: bytes) -> List[Tuple[int, int]]:
    regions = []
    pos = 0
    while True:
        a = data.find(b"GIF87a", pos)
        b = data.find(b"GIF89a", pos)
        starts = [x for x in (a, b) if x >= 0]
        if not starts:
            break
        start = min(starts)
        end = _parse_gif_end(data, start)
        if end is None:
            pos = start + 6
            continue
        regions.append((start, end))
        pos = end
    return regions


def exclude_embedded_media(strings: List[ExtractedString], data: bytes) -> tuple[List[ExtractedString], int]:
    regions = embedded_gif_regions(data)
    if not regions:
        return strings, 0
    out = []
    removed = 0
    for item in strings:
        off = item.index
        if any(start <= off < end for start, end in regions):
            removed += 1
            continue
        out.append(item)
    return out, removed


def encode_modified_utf8(text: str) -> bytes:
    """Encode Java Modified UTF-8 used by DataOutputStream.writeUTF."""
    utf16 = text.encode("utf-16-be", errors="surrogatepass")
    out = bytearray()
    for i in range(0, len(utf16), 2):
        unit = (utf16[i] << 8) | utf16[i + 1]
        if unit == 0:
            out.extend((0xC0, 0x80))
        elif unit <= 0x7F:
            out.append(unit)
        elif unit <= 0x7FF:
            out.extend((
                0xC0 | (unit >> 6),
                0x80 | (unit & 0x3F),
            ))
        else:
            out.extend((
                0xE0 | (unit >> 12),
                0x80 | ((unit >> 6) & 0x3F),
                0x80 | (unit & 0x3F),
            ))
    return bytes(out)


def _write_lsb_bits(bits: list[int], value: int, count: int) -> None:
    for bit in range(count):
        bits.append((value >> bit) & 1)


def compress_src4_literals(decoded: bytes) -> bytes:
    """Produce a valid SRC4 LZ stream using literal tokens only."""
    if len(decoded) > 0xFFFF:
        raise ValueError("SRC4 decompressed record exceeds u16 length")
    bits = []
    for value in decoded:
        bits.append(0)
        _write_lsb_bits(bits, value, 8)
    stream = bytearray((len(bits) + 7) // 8)
    for bit_index, bit in enumerate(bits):
        if bit:
            stream[bit_index // 8] |= 1 << (bit_index % 8)
    if len(stream) > 0xFFFF:
        raise ValueError("SRC4 literal bitstream exceeds u16 length")
    return len(decoded).to_bytes(2, "little") + bytes(stream)


def pack_src4_record(decoded: bytes) -> bytes:
    """Wrap decompressed record 4/5 bytes in the game's compression envelope."""
    blob = compress_src4_literals(decoded)
    bitstream_len = len(blob) - 2
    if bitstream_len > 0xFFFF:
        raise ValueError("SRC4 compressed bitstream exceeds u16 length")
    return bitstream_len.to_bytes(2, "little") + blob


def rebuild_src4(records: List[bytes]) -> bytes:
    """Rebuild a five-record SRC4 file with canonical contiguous records."""
    if len(records) != 5:
        raise ValueError("SRC4 must contain exactly five records")
    header = bytearray(10)
    body = bytearray()
    length_offset = 10
    for i, record in enumerate(records):
        if len(record) > 0xFFFF:
            raise ValueError(f"SRC4 record {i + 1} exceeds u16 length")
        relative = length_offset - ((i + 1) * 2)
        if not (0 <= relative <= 0xFFFF):
            raise ValueError(f"SRC4 record {i + 1} relative offset exceeds u16")
        header[i * 2:i * 2 + 2] = relative.to_bytes(2, "little")
        body.extend(len(record).to_bytes(2, "little"))
        body.extend(record)
        length_offset += 2 + len(record)
    return bytes(header + body)


def _parse_src4_kind(kind: str) -> int:
    m = re.fullmatch(r"src4:r([45]):java-utf:safe", kind or "")
    if not m:
        raise ValueError(f"Unsupported SRC4 kind: {kind}")
    return int(m.group(1))


def _java_utf_field_at(decoded: bytes, text_offset: int) -> tuple[int, int, str]:
    prefix = text_offset - 2
    if prefix < 0 or prefix + 2 > len(decoded):
        raise ValueError("SRC4 Java-UTF prefix offset out of bounds")
    byte_len = int.from_bytes(decoded[prefix:prefix + 2], "big")
    end = text_offset + byte_len
    if end > len(decoded):
        raise ValueError("SRC4 Java-UTF payload out of bounds")
    raw = decoded[text_offset:end]
    try:
        text = decode_modified_utf8(raw)
    except UnicodeDecodeError as exc:
        raise ValueError(f"SRC4 Java-UTF decode failed: {exc}") from exc
    return prefix, end, text


def _contains_java_utf(decoded: bytes, text: str) -> bool:
    encoded = encode_modified_utf8(text)
    if len(encoded) > 0xFFFF:
        return False
    return len(encoded).to_bytes(2, "big") + encoded in decoded


def patch_src4_translations(data: bytes, patches) -> bytes:
    """Transactionally patch SRC4 Java-UTF strings and recompress records 4/5."""
    records = split_src4_records(data)
    grouped = {4: [], 5: []}
    patch_rows = list(patches)
    if not patch_rows:
        return data

    for item, replacement in patch_rows:
        record_no = _parse_src4_kind(item.kind)
        if not isinstance(replacement, str) or not replacement:
            raise ValueError("SRC4 replacement must be a non-empty string")
        grouped[record_no].append((item, replacement))

    updated_records = list(records)
    for record_no, rows in grouped.items():
        if not rows:
            continue
        working = decompress_src4_record(records[record_no - 1])

        for item, replacement in sorted(rows, key=lambda row: row[0].index, reverse=True):
            prefix, end, current = _java_utf_field_at(working, item.index)
            if current != item.value:
                raise ValueError(
                    f"SRC4 original mismatch in record {record_no} at {item.index}: "
                    f"{current!r} != {item.value!r}"
                )
            encoded = encode_modified_utf8(replacement)
            if len(encoded) > 0xFFFF:
                raise ValueError("SRC4 replacement exceeds Java-UTF u16 byte length")
            working = (
                working[:prefix]
                + len(encoded).to_bytes(2, "big")
                + encoded
                + working[end:]
            )

        for _item, replacement in rows:
            if not _contains_java_utf(working, replacement):
                raise ValueError(
                    f"SRC4 replacement verification failed in record {record_no}: {replacement!r}"
                )
        updated_records[record_no - 1] = pack_src4_record(working)

    rebuilt = rebuild_src4(updated_records)
    check_records = split_src4_records(rebuilt)
    for i in range(3):
        if check_records[i] != records[i]:
            raise ValueError(f"SRC4 untouched record {i + 1} changed unexpectedly")
    for record_no, rows in grouped.items():
        if not rows:
            continue
        decoded = decompress_src4_record(check_records[record_no - 1])
        for _item, replacement in rows:
            if not _contains_java_utf(decoded, replacement):
                raise ValueError(
                    f"SRC4 post-rebuild verification failed in record {record_no}: {replacement!r}"
                )
    return rebuilt


def src4_translation_present(data: bytes, record_no: int, translation: str) -> bool:
    if record_no not in (4, 5):
        return False
    try:
        records = split_src4_records(data)
        decoded = decompress_src4_record(records[record_no - 1])
    except ValueError:
        return False
    return _contains_java_utf(decoded, translation)
