from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Set


@dataclass(frozen=True)
class RuntimeProfile:
    key: str
    label: str
    description: str
    native_apis: FrozenSet[str] = field(default_factory=frozenset)
    conditional_apis: FrozenSet[str] = field(default_factory=frozenset)
    unsupported_apis: FrozenSet[str] = field(default_factory=frozenset)
    messaging_policy: str = "report_only"


PROFILES: Dict[str, RuntimeProfile] = {
    "generic_j2me": RuntimeProfile(
        key="generic_j2me",
        label="Generic J2ME",
        description="Conservative MIDP/CLDC target without assuming vendor-specific optional packages.",
        native_apis=frozenset({"media"}),
        conditional_apis=frozenset({"m3g", "bluetooth", "file_connection", "wma_sms"}),
        unsupported_apis=frozenset({"nokia", "samsung", "siemens", "sonyericsson", "motorola"}),
        messaging_policy="report_only",
    ),
    "freej2me_rg35xx": RuntimeProfile(
        key="freej2me_rg35xx",
        label="FreeJ2ME / RG35XX",
        description=(
            "RG35XX compatibility target. Detect optional/vendor APIs before rebuild and never attempt real SMS transport."
        ),
        native_apis=frozenset({"media"}),
        conditional_apis=frozenset({"m3g", "file_connection", "bluetooth"}),
        unsupported_apis=frozenset({"wma_sms", "nokia", "samsung", "siemens", "sonyericsson", "motorola"}),
        messaging_policy="deny_transport",
    ),
}


@dataclass
class ProfileAssessment:
    profile_key: str
    profile_label: str
    score: int
    risk: str
    supported: List[str] = field(default_factory=list)
    conditional: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def get_runtime_profile(key: str) -> RuntimeProfile:
    return PROFILES.get(key, PROFILES["generic_j2me"])


def assess_profile(detected_apis: Iterable[str], profile_key: str = "freej2me_rg35xx") -> ProfileAssessment:
    profile = get_runtime_profile(profile_key)
    apis: Set[str] = set(detected_apis)
    supported = sorted(apis.intersection(profile.native_apis))
    conditional = sorted(apis.intersection(profile.conditional_apis))
    unsupported = sorted(apis.intersection(profile.unsupported_apis))

    score = 100
    score -= 10 * len(conditional)
    score -= 25 * len(unsupported)
    score = max(0, score)

    risk = "high" if unsupported else ("medium" if conditional else "low")
    notes: List[str] = []
    if "wma_sms" in unsupported:
        notes.append(
            "WMA/SMS is not treated as a usable RG35XX transport. Keep it in report-only/deny mode; do not send SMS from the desktop tool."
        )
    if any(api in unsupported for api in ("nokia", "samsung", "siemens", "sonyericsson", "motorola")):
        notes.append("Vendor-specific classes may need an emulator-side compatibility implementation or a different JAR build.")
    if conditional:
        notes.append("Conditional APIs require runtime verification on the selected FreeJ2ME build.")

    return ProfileAssessment(
        profile_key=profile.key,
        profile_label=profile.label,
        score=score,
        risk=risk,
        supported=supported,
        conditional=conditional,
        unsupported=unsupported,
        notes=notes,
    )
