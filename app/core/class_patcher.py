import struct
from typing import Dict, Tuple


class ClassPatchError(Exception):
    pass


def encode_modified_utf8(text: str) -> bytes:
    """Encode Java Modified UTF-8 (DataInput/DataOutput style).

    Java class CONSTANT_Utf8 entries use MUTF-8. BMP characters use normal UTF-8
    except NUL. Supplementary code points are encoded as surrogate pairs.
    """
    out = bytearray()
    # Work in UTF-16 code units so supplementary characters become surrogate pairs.
    units = text.encode("utf-16-be", errors="surrogatepass")
    for i in range(0, len(units), 2):
        ch = (units[i] << 8) | units[i + 1]
        if ch == 0:
            out += b"\xC0\x80"
        elif ch <= 0x7F:
            out.append(ch)
        elif ch <= 0x7FF:
            out.append(0xC0 | ((ch >> 6) & 0x1F))
            out.append(0x80 | (ch & 0x3F))
        else:
            out.append(0xE0 | ((ch >> 12) & 0x0F))
            out.append(0x80 | ((ch >> 6) & 0x3F))
            out.append(0x80 | (ch & 0x3F))
    return bytes(out)


class ClassPatcher:
    """Rewrites selected CONSTANT_Utf8 entries while preserving the rest of class bytes."""

    @staticmethod
    def patch(data: bytes, replacements: Dict[int, str]) -> Tuple[bytes, int]:
        if not replacements:
            return data, 0
        if len(data) < 10 or struct.unpack_from(">I", data, 0)[0] != 0xCAFEBABE:
            raise ClassPatchError("Invalid Java class magic")

        cp_count = struct.unpack_from(">H", data, 8)[0]
        pos = 10
        out = bytearray(data[:10])
        patched = 0
        i = 1

        while i < cp_count:
            if pos >= len(data):
                raise ClassPatchError("Unexpected end of constant pool")
            tag = data[pos]
            out.append(tag)
            pos += 1

            if tag == 1:  # CONSTANT_Utf8
                if pos + 2 > len(data):
                    raise ClassPatchError("Truncated UTF8 length")
                length = struct.unpack_from(">H", data, pos)[0]
                pos += 2
                raw = data[pos:pos + length]
                if len(raw) != length:
                    raise ClassPatchError("Truncated UTF8 payload")
                pos += length
                if i in replacements:
                    new_raw = encode_modified_utf8(replacements[i])
                    if len(new_raw) > 65535:
                        raise ClassPatchError(f"Translated string too large for CONSTANT_Utf8 at index {i}")
                    out += struct.pack(">H", len(new_raw))
                    out += new_raw
                    patched += 1
                else:
                    out += struct.pack(">H", length)
                    out += raw
            elif tag in (3, 4):
                out += data[pos:pos + 4]; pos += 4
            elif tag in (5, 6):
                out += data[pos:pos + 8]; pos += 8
                i += 1
            elif tag in (7, 8, 16, 19, 20):
                out += data[pos:pos + 2]; pos += 2
            elif tag in (9, 10, 11, 12, 17, 18):
                out += data[pos:pos + 4]; pos += 4
            elif tag == 15:
                out += data[pos:pos + 3]; pos += 3
            else:
                raise ClassPatchError(f"Unsupported constant-pool tag {tag} at index {i}")
            i += 1

        out += data[pos:]
        return bytes(out), patched
