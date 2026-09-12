import re
from typing import List
from models.data import ExtractedString
from core.encoding_utils import decode_best

TEXT_EXTENSIONS = {".txt", ".properties", ".xml", ".csv", ".ini", ".lang", ".lng", ".json", ".yaml", ".yml", ".cfg", ".conf", ".config", ".loc", ".locale", ".strings", ".po"}
BINARY_EXTENSIONS = {".dat", ".bin", ".res", ".pak", ".db", ".rms"}

class ResourceScanner:
    @staticmethod
    def _ext(path: str) -> str:
        dot = path.rfind(".")
        return path[dot:].lower() if dot >= 0 else ""

    def scan(self, source: str, data: bytes) -> List[ExtractedString]:
        ext = self._ext(source)
        if ext in TEXT_EXTENSIONS:
            return self._scan_text(source, data)
        if ext in BINARY_EXTENSIONS:
            return self._scan_binary(source, data)
        return []

    def _decode(self, data: bytes):
        # Prefer the best-scoring decode instead of the first codec that happens
        # not to throw. Latin-1 always succeeds and previously masked GBK/GB18030.
        return decode_best(data)

    def _scan_text(self, source: str, data: bytes):
        text, enc = self._decode(data)
        results = []
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line or line.startswith(("#", ";", "//")):
                continue
            value = line.split("=", 1)[1].strip() if "=" in line else line
            if value:
                results.append(ExtractedString(source, value, "resource-text", i, enc))
        return results

    def _scan_binary(self, source: str, data: bytes):
        results = []
        # Conservative printable ASCII search, useful for unknown J2ME resource formats.
        for m in re.finditer(rb"[\x20-\x7E]{4,}", data):
            value = m.group(0).decode("ascii", errors="ignore").strip()
            if value:
                results.append(ExtractedString(source, value, "binary-ascii", m.start(), "ascii"))
        return results
