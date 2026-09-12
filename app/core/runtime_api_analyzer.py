from dataclasses import dataclass, field
from typing import Dict, List, Set
import zipfile


API_SIGNATURES = {
    "wma_sms": (
        b"javax/wireless/messaging/", b"javax.wireless.messaging.",
        b"MessageConnection", b"TextMessage", b"BinaryMessage", b"sms://",
    ),
    "m3g": (b"javax/microedition/m3g/", b"javax.microedition.m3g."),
    "bluetooth": (b"javax/bluetooth/", b"javax.bluetooth."),
    "media": (b"javax/microedition/media/", b"javax.microedition.media."),
    "file_connection": (b"javax/microedition/io/file/", b"javax.microedition.io.file."),
    "nokia": (b"com/nokia/", b"com.nokia."),
    "samsung": (b"com/samsung/", b"com.samsung."),
    "siemens": (b"com/siemens/", b"com.siemens."),
    "sonyericsson": (b"com/sonyericsson/", b"com.sonyericsson."),
    "motorola": (b"com/motorola/", b"com.motorola."),
}


@dataclass
class RuntimeApiFinding:
    api: str
    severity: str
    source: str
    message: str


@dataclass
class RuntimeApiReport:
    midp_profile: str = "unknown"
    cldc_configuration: str = "unknown"
    runtime_risk: str = "low"
    compatibility_score: int = 100
    detected_apis: Set[str] = field(default_factory=set)
    api_sources: Dict[str, List[str]] = field(default_factory=dict)
    sms_targets: List[str] = field(default_factory=list)
    findings: List[RuntimeApiFinding] = field(default_factory=list)

    @property
    def uses_wma_sms(self) -> bool:
        return "wma_sms" in self.detected_apis

    @property
    def uses_vendor_api(self) -> bool:
        return any(x in self.detected_apis for x in ("nokia", "samsung", "siemens", "sonyericsson", "motorola"))


class RuntimeApiAnalyzer:
    """Static J2ME API dependency scan without decompiling application code."""

    def _parse_manifest(self, data: bytes) -> Dict[str, str]:
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        logical = []
        for line in text.split("\n"):
            if line.startswith(" ") and logical:
                logical[-1] += line[1:]
            else:
                logical.append(line)
        out = {}
        for line in logical:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            out[key.strip().lower()] = value.strip()
        return out

    def analyze(self, jar_path: str) -> RuntimeApiReport:
        report = RuntimeApiReport()
        sms_targets = set()
        with zipfile.ZipFile(jar_path, "r") as z:
            manifest = {}
            for candidate in ("META-INF/MANIFEST.MF", "meta-inf/manifest.mf"):
                try:
                    manifest = self._parse_manifest(z.read(candidate))
                    break
                except KeyError:
                    continue
            report.midp_profile = manifest.get("microedition-profile", "unknown")
            report.cldc_configuration = manifest.get("microedition-configuration", "unknown")

            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".class"):
                    continue
                if info.file_size > 8 * 1024 * 1024:
                    continue
                try:
                    data = z.read(info)
                except Exception:
                    continue
                low = data.lower()
                for api, signatures in API_SIGNATURES.items():
                    if any(sig.lower() in low for sig in signatures):
                        report.detected_apis.add(api)
                        report.api_sources.setdefault(api, []).append(info.filename)
                start = 0
                while True:
                    pos = low.find(b"sms://", start)
                    if pos < 0:
                        break
                    end = pos
                    while end < len(data) and 32 <= data[end] < 127 and end - pos < 160:
                        end += 1
                    target = data[pos:end].decode("ascii", errors="ignore")
                    if target:
                        sms_targets.add(target)
                    start = pos + 6

        report.sms_targets = sorted(sms_targets)
        score = 100
        severities = []

        if report.uses_wma_sms:
            score -= 25
            severities.append("high")
            source = ", ".join(report.api_sources.get("wma_sms", [])[:3]) or "JAR"
            report.findings.append(RuntimeApiFinding(
                "wma_sms", "high", source,
                "JSR-120/205 WMA-SMS dependency detected. FreeJ2ME may fail with ClassNotFound/NoClassDefFoundError when WMA is unavailable; legacy activation may also block startup."
            ))
            if report.sms_targets:
                report.findings.append(RuntimeApiFinding(
                    "wma_sms", "medium", "constant-pool",
                    "SMS endpoint(s) found: " + ", ".join(report.sms_targets[:5])
                ))

        vendor_names = {
            "nokia": "Nokia proprietary API", "samsung": "Samsung proprietary API",
            "siemens": "Siemens proprietary API", "sonyericsson": "Sony Ericsson proprietary API",
            "motorola": "Motorola proprietary API",
        }
        for api, label in vendor_names.items():
            if api in report.detected_apis:
                score -= 18
                severities.append("high")
                report.findings.append(RuntimeApiFinding(
                    api, "high", ", ".join(report.api_sources.get(api, [])[:3]),
                    f"{label} detected; generic J2ME runtimes may not provide these classes."
                ))

        for api, label in (("m3g", "JSR-184 M3G"), ("bluetooth", "JSR-82 Bluetooth"),
                           ("file_connection", "JSR-75 FileConnection")):
            if api in report.detected_apis:
                score -= 8
                severities.append("medium")
                report.findings.append(RuntimeApiFinding(
                    api, "medium", ", ".join(report.api_sources.get(api, [])[:3]),
                    f"{label} dependency detected; support depends on the target emulator/runtime."
                ))

        if "media" in report.detected_apis:
            score -= 3
            report.findings.append(RuntimeApiFinding(
                "media", "low", ", ".join(report.api_sources.get("media", [])[:3]),
                "JSR-135/MMAPI dependency detected."
            ))

        report.compatibility_score = max(0, score)
        report.runtime_risk = "high" if "high" in severities else ("medium" if "medium" in severities else "low")
        if not report.findings:
            report.findings.append(RuntimeApiFinding(
                "runtime", "low", "JAR",
                "No WMA/SMS or known vendor-specific API signature was detected in class files."
            ))
        return report
