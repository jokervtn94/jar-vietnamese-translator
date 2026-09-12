import struct
from typing import List
from models.data import ExtractedString

class ClassFormatError(Exception):
    pass

class ClassReader:
    """Minimal Java .class constant-pool reader focused on UTF8/String constants."""

    def __init__(self, data: bytes, source: str = ""):
        self.data = data
        self.source = source
        self.pos = 0

    def _need(self, n: int):
        if self.pos + n > len(self.data):
            raise ClassFormatError("Unexpected end of class file")

    def u1(self):
        self._need(1)
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u2(self):
        self._need(2)
        v = struct.unpack_from(">H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u4(self):
        self._need(4)
        v = struct.unpack_from(">I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def take(self, n: int):
        self._need(n)
        v = self.data[self.pos:self.pos+n]
        self.pos += n
        return v

    @staticmethod
    def decode_modified_utf8(raw: bytes) -> str:
        # Java Modified UTF-8 encodes NUL as C0 80 and supplementary characters
        # as CESU-8 surrogate pairs. Decode both forms without turning valid game
        # text into replacement characters.
        raw = raw.replace(b"\xC0\x80", b"\x00")
        try:
            text = raw.decode("utf-8", errors="surrogatepass")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
        out=[]
        i=0
        while i < len(text):
            o=ord(text[i])
            if 0xD800 <= o <= 0xDBFF and i+1 < len(text):
                o2=ord(text[i+1])
                if 0xDC00 <= o2 <= 0xDFFF:
                    out.append(chr(0x10000 + ((o-0xD800)<<10) + (o2-0xDC00)))
                    i += 2
                    continue
            out.append(text[i]); i += 1
        return "".join(out)

    def extract_strings(self) -> List[ExtractedString]:
        if self.u4() != 0xCAFEBABE:
            raise ClassFormatError("Invalid Java class magic")
        self.u2()  # minor
        self.u2()  # major
        cp_count = self.u2()
        cp = [None] * cp_count
        i = 1
        while i < cp_count:
            tag = self.u1()
            if tag == 1:  # Utf8
                length = self.u2()
                raw = self.take(length)
                cp[i] = (tag, self.decode_modified_utf8(raw))
            elif tag in (3, 4):
                self.take(4)
                cp[i] = (tag, None)
            elif tag in (5, 6):
                self.take(8)
                cp[i] = (tag, None)
                i += 1  # double-slot
            elif tag in (7, 8, 16, 19, 20):
                idx = self.u2()
                cp[i] = (tag, idx)
            elif tag in (9, 10, 11, 12, 17, 18):
                a, b = self.u2(), self.u2()
                cp[i] = (tag, (a, b))
            elif tag == 15:
                self.u1(); self.u2()
                cp[i] = (tag, None)
            else:
                raise ClassFormatError(f"Unsupported constant-pool tag {tag} at index {i}")
            i += 1

        out = []
        seen = set()
        # Prefer actual CONSTANT_String references so class names/method names are
        # not mistaken for language strings.
        for idx, item in enumerate(cp):
            if not item or item[0] != 8:
                continue
            utf_index = item[1]
            if 0 < utf_index < len(cp) and cp[utf_index] and cp[utf_index][0] == 1:
                value = cp[utf_index][1]
                key = (utf_index, value)
                if key not in seen:
                    seen.add(key)
                    out.append(ExtractedString(self.source, value, "class-string", utf_index, "MUTF-8"))
        return out
