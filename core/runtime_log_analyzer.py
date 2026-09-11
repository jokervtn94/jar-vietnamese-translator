
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import re, json

ERROR_PATTERNS = [
    ("OutOfMemoryError", "HIGH", "memory"),
    ("VerifyError", "HIGH", "class"),
    ("ClassFormatError", "HIGH", "class"),
    ("NoClassDefFoundError", "HIGH", "class"),
    ("ClassNotFoundException", "HIGH", "class"),
    ("UnsupportedEncodingException", "HIGH", "encoding"),
    ("MalformedInputException", "HIGH", "encoding"),
    ("UnmappableCharacterException", "HIGH", "encoding"),
    ("IllegalArgumentException", "MEDIUM", "runtime"),
    ("ArrayIndexOutOfBoundsException", "HIGH", "binary"),
    ("IndexOutOfBoundsException", "HIGH", "binary"),
    ("NullPointerException", "HIGH", "runtime"),
    ("IOException", "MEDIUM", "resource"),
    ("EOFException", "HIGH", "binary"),
    ("ZipException", "HIGH", "archive"),
    ("SecurityException", "HIGH", "signature"),
    ("Exception", "MEDIUM", "runtime"),
    ("Error", "MEDIUM", "runtime"),
]

PATCH_RISK_HINTS = {
    "class": "Có thể liên quan class đã patch hoặc bytecode/constant-pool.",
    "encoding": "Có thể liên quan charset/chuỗi tiếng Việt không tương thích runtime.",
    "binary": "Có thể liên quan độ dài/offset/resource binary sau patch.",
    "resource": "Có thể liên quan resource text/binary bị thiếu hoặc thay đổi.",
    "archive": "Có thể liên quan cấu trúc JAR/ZIP đầu ra.",
    "signature": "Có thể liên quan chữ ký JAR bị vô hiệu sau rebuild.",
    "memory": "Có thể do runtime thiếu RAM; chưa đủ bằng chứng là lỗi bản dịch.",
    "runtime": "Lỗi runtime chung; cần đối chiếu stack trace và file đã patch.",
}

@dataclass
class LogIssue:
    severity: str
    category: str
    line_no: int
    text: str
    exception: str = ""
    class_name: str = ""
    resource: str = ""
    related_patch_sources: List[str] = field(default_factory=list)
    hint: str = ""

@dataclass
class RuntimeLogReport:
    log_path: str
    total_lines: int = 0
    issues: List[LogIssue] = field(default_factory=list)
    exceptions: Dict[str, int] = field(default_factory=dict)
    classes: Dict[str, int] = field(default_factory=dict)
    resources: Dict[str, int] = field(default_factory=dict)
    matched_patch_sources: Dict[str, int] = field(default_factory=dict)
    summary: str = "No obvious runtime error detected"

    @property
    def high_count(self):
        return sum(1 for i in self.issues if i.severity == "HIGH")

    @property
    def medium_count(self):
        return sum(1 for i in self.issues if i.severity == "MEDIUM")

    @property
    def status(self):
        if self.high_count:
            return "FAIL"
        if self.medium_count:
            return "WARNING"
        return "PASS"

class RuntimeLogAnalyzer:
    class_re = re.compile(r'(?:at\s+)?([A-Za-z_$][\w$]*(?:[./][A-Za-z_$][\w$]*)+)(?:\.[A-Za-z_$][\w$]*)?\s*\(')
    resource_re = re.compile(r'(?i)([A-Za-z0-9_./\\-]+\.(?:class|dat|bin|res|properties|txt|xml|png|fnt|jar))')

    def _normalize_source(self, s: str) -> str:
        return s.replace("\\","/").lstrip("/")

    def _load_patch_sources(self, build_report_path: Optional[str]):
        sources=set()
        if not build_report_path:
            return sources
        p=Path(build_report_path)
        if not p.exists():
            return sources
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
            for item in data.get("items",[]):
                if item.get("status") == "PATCHED" and item.get("source"):
                    sources.add(self._normalize_source(item["source"]))
        except Exception:
            pass
        return sources

    def analyze(self, log_path: str, build_report_path: Optional[str]=None) -> RuntimeLogReport:
        p=Path(log_path)
        raw=p.read_bytes()
        text=None
        for enc in ("utf-8","utf-8-sig","cp1252","latin-1"):
            try:
                text=raw.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            text=raw.decode("utf-8",errors="replace")

        lines=text.splitlines()
        report=RuntimeLogReport(str(p), total_lines=len(lines))
        patch_sources=self._load_patch_sources(build_report_path)

        for n,line in enumerate(lines,1):
            stripped=line.strip()
            if not stripped:
                continue

            matched=None
            for token,severity,category in ERROR_PATTERNS:
                if token.lower() in stripped.lower():
                    matched=(token,severity,category)
                    break

            # Common emulator failure markers even without Java exception class.
            low=stripped.lower()
            if matched is None:
                if any(x in low for x in ("fatal", "crash", "failed to load", "could not load", "uncaught")):
                    matched=("runtime-failure","HIGH","runtime")
                elif any(x in low for x in ("warning", "warn:", "[warn]")):
                    matched=("warning","MEDIUM","runtime")

            if matched is None:
                continue

            token,severity,category=matched
            class_name=""
            cm=self.class_re.search(stripped)
            if cm:
                class_name=cm.group(1).replace(".","/")

            resource=""
            rm=self.resource_re.search(stripped)
            if rm:
                resource=self._normalize_source(rm.group(1))

            related=[]
            candidates=[]
            if resource:
                candidates.append(resource)
            if class_name:
                candidates += [class_name+".class", class_name.split("/")[-1]+".class"]

            for ps in patch_sources:
                pslow=ps.lower()
                if any(c.lower() in pslow or pslow.endswith(c.lower()) for c in candidates):
                    related.append(ps)
                elif any(part and part.lower() in stripped.lower() for part in (ps, Path(ps).name)):
                    related.append(ps)

            # Stack-trace lines may refer to a patched class but only contain generic "Exception".
            for ps in patch_sources:
                if ps not in related and Path(ps).name.lower() in stripped.lower():
                    related.append(ps)

            issue=LogIssue(
                severity=severity,
                category=category,
                line_no=n,
                text=stripped[:1000],
                exception=token,
                class_name=class_name,
                resource=resource,
                related_patch_sources=sorted(set(related)),
                hint=PATCH_RISK_HINTS.get(category,"")
            )
            report.issues.append(issue)
            report.exceptions[token]=report.exceptions.get(token,0)+1
            if class_name:
                report.classes[class_name]=report.classes.get(class_name,0)+1
            if resource:
                report.resources[resource]=report.resources.get(resource,0)+1
            for src in issue.related_patch_sources:
                report.matched_patch_sources[src]=report.matched_patch_sources.get(src,0)+1

        if report.high_count:
            if report.matched_patch_sources:
                report.summary="Runtime FAIL; log references one or more patched sources."
            else:
                report.summary="Runtime FAIL; no direct reference to patched source was proven."
        elif report.medium_count:
            report.summary="Runtime WARNING; review warnings and stack traces."
        else:
            report.summary="No obvious runtime error detected."

        return report
