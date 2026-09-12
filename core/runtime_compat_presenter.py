from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


API_LABELS = {
    "wma_sms": "WMA / SMS (JSR-120/205)",
    "m3g": "M3G (JSR-184)",
    "bluetooth": "Bluetooth (JSR-82)",
    "media": "MMAPI (JSR-135)",
    "file_connection": "FileConnection (JSR-75)",
    "nokia": "Nokia proprietary API",
    "samsung": "Samsung proprietary API",
    "siemens": "Siemens proprietary API",
    "sonyericsson": "Sony Ericsson proprietary API",
    "motorola": "Motorola proprietary API",
}


@dataclass(frozen=True)
class RuntimeCompatibilitySummary:
    target: str
    score: int
    risk: str
    midp: str
    cldc: str
    detected_apis: Tuple[str, ...]
    unsupported: Tuple[str, ...]
    conditional: Tuple[str, ...]
    sms_targets: Tuple[str, ...]
    wma_policy: str

    @property
    def uses_wma_sms(self) -> bool:
        return "wma_sms" in self.detected_apis

    def lines(self) -> list[str]:
        detected = ", ".join(API_LABELS.get(x, x) for x in self.detected_apis) or "Không phát hiện optional/vendor API"
        unsupported = ", ".join(API_LABELS.get(x, x) for x in self.unsupported) or "Không có"
        conditional = ", ".join(API_LABELS.get(x, x) for x in self.conditional) or "Không có"
        sms = ", ".join(self.sms_targets) or "Không có"
        wma = "Chặn transport SMS thật; không giả activation thành công" if self.uses_wma_sms else "Không áp dụng"
        return [
            f"Target: {self.target}",
            f"Compatibility score: {self.score}/100",
            f"Runtime risk: {self.risk.upper()}",
            f"MIDP: {self.midp}",
            f"CLDC: {self.cldc}",
            f"Detected APIs: {detected}",
            f"Unsupported: {unsupported}",
            f"Conditional: {conditional}",
            f"SMS endpoint(s): {sms}",
            f"WMA policy: {wma}",
        ]


def summarize_runtime(report) -> RuntimeCompatibilitySummary:
    rg35xx = report.rg35xx
    return RuntimeCompatibilitySummary(
        target=getattr(rg35xx, "profile_label", "FreeJ2ME / RG35XX") or "FreeJ2ME / RG35XX",
        score=int(getattr(rg35xx, "score", report.compatibility_score)),
        risk=str(getattr(rg35xx, "risk", report.runtime_risk)),
        midp=str(report.midp_profile),
        cldc=str(report.cldc_configuration),
        detected_apis=tuple(sorted(report.detected_apis)),
        unsupported=tuple(sorted(getattr(rg35xx, "unsupported", ()) or ())),
        conditional=tuple(sorted(getattr(rg35xx, "conditional", ()) or ())),
        sms_targets=tuple(report.sms_targets),
        wma_policy="deny_transport" if report.uses_wma_sms else "not_applicable",
    )
