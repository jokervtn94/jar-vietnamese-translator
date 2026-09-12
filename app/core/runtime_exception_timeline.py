from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
import re


ERROR_NAMES = (
    "ClassNotFoundException",
    "NoClassDefFoundError",
    "UnsupportedOperationException",
    "VerifyError",
    "SecurityException",
    "OutOfMemoryError",
    "NullPointerException",
    "IllegalArgumentException",
)

STACK_RE = re.compile(r"^\s*at\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\.[^.(\s]+\s*\(")


@dataclass
class ExceptionEvent:
    index: int
    error_type: str
    message: str = ""
    caused_by: bool = False
    stack_frames: List[str] = field(default_factory=list)
    severity: str = "medium"
    startup_overlap: List[str] = field(default_factory=list)
    api_overlap: List[str] = field(default_factory=list)
    score: int = 0


@dataclass
class ExceptionTimeline:
    events: List[ExceptionEvent] = field(default_factory=list)
    primary_index: int = -1
    root_index: int = -1

    @property
    def primary(self) -> ExceptionEvent | None:
        if 0 <= self.primary_index < len(self.events):
            return self.events[self.primary_index]
        return None

    @property
    def root(self) -> ExceptionEvent | None:
        if 0 <= self.root_index < len(self.events):
            return self.events[self.root_index]
        return None


def _severity(error_type: str) -> str:
    if error_type in {"ClassNotFoundException", "NoClassDefFoundError", "VerifyError", "OutOfMemoryError"}:
        return "high"
    return "medium"


def _event_header(line: str):
    stripped = line.strip()
    caused_by = stripped.startswith("Caused by:")
    body = stripped[len("Caused by:"):].strip() if caused_by else stripped
    for name in ERROR_NAMES:
        if name not in body:
            continue
        tail = body.split(name, 1)[1].lstrip(": ")
        return name, tail, caused_by
    return None


def build_exception_timeline(log_text: str, startup_path=None, matched_apis=None) -> ExceptionTimeline:
    startup = [str(x).replace("/", ".") for x in (startup_path or [])]
    apis = [str(x) for x in (matched_apis or [])]
    events: List[ExceptionEvent] = []
    current: ExceptionEvent | None = None

    for raw in log_text.splitlines():
        header = _event_header(raw)
        if header:
            error_type, message, caused_by = header
            current = ExceptionEvent(
                index=len(events),
                error_type=error_type,
                message=message,
                caused_by=caused_by,
                severity=_severity(error_type),
            )
            events.append(current)
            continue

        if current is None:
            continue
        match = STACK_RE.match(raw)
        if match:
            cls = match.group(1).replace("/", ".")
            if cls not in current.stack_frames:
                current.stack_frames.append(cls)

    for event in events:
        frame_set = set(event.stack_frames)
        event.startup_overlap = [cls for cls in startup if cls in frame_set]
        normalized = (event.message + " " + " ".join(event.stack_frames)).lower()
        event.api_overlap = [api for api in apis if api.lower() in normalized]
        event.score = 0
        event.score += 100 if event.caused_by else 0
        event.score += 60 if event.severity == "high" else 20
        event.score += 25 * len(event.startup_overlap)
        event.score += 20 * len(event.api_overlap)
        event.score += event.index

    root_index = -1
    if events:
        caused = [event.index for event in events if event.caused_by]
        root_index = caused[-1] if caused else 0

    primary_index = -1
    if events:
        primary_index = max(range(len(events)), key=lambda i: events[i].score)

    return ExceptionTimeline(events=events, primary_index=primary_index, root_index=root_index)


def format_exception_timeline(timeline: ExceptionTimeline) -> str:
    lines = ["EXCEPTION TIMELINE"]
    if not timeline.events:
        return "EXCEPTION TIMELINE\n- none"

    for event in timeline.events:
        tags = []
        if event.index == timeline.root_index:
            tags.append("ROOT")
        if event.index == timeline.primary_index:
            tags.append("PRIMARY")
        if event.caused_by:
            tags.append("CAUSED-BY")
        tag_text = f" [{' / '.join(tags)}]" if tags else ""
        message = f": {event.message}" if event.message else ""
        lines.append(f"{event.index + 1}. {event.error_type}{message}{tag_text}")
        if event.stack_frames:
            lines.append("   path: " + " -> ".join(reversed(event.stack_frames)))
        if event.startup_overlap:
            lines.append("   startup overlap: " + " -> ".join(event.startup_overlap))

    primary = timeline.primary
    if primary is not None:
        lines.append("")
        lines.append(f"Priority failure: {primary.error_type}")
        if primary.stack_frames:
            lines.append("Priority path: " + " -> ".join(reversed(primary.stack_frames)))
    return "\n".join(lines)
