from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class StartupBlockingAssessment:
    classification: str = "compatible_or_unknown"
    severity: str = "low"
    title: str = "Không thấy blocker startup rõ ràng"
    reasons: List[str] = field(default_factory=list)
    recommendation: str = "Kiểm thử trực tiếp trên FreeJ2ME / RG35XX để xác nhận hành vi runtime."


def assess_startup_blocking(runtime_report, activation_report) -> StartupBlockingAssessment:
    """Summarize startup risk without patching, bypassing, or emulating activation.

    The result is diagnostic only. It combines target-runtime support with static
    activation/payment reachability so the UI can distinguish a likely startup
    blocker from an optional feature risk or a runtime-only incompatibility.
    """
    target = getattr(runtime_report, "rg35xx", None)
    unsupported = set(getattr(target, "unsupported", []) or []) if target is not None else set()
    conditional = set(getattr(target, "conditional", []) or []) if target is not None else set()
    uses_wma = bool(getattr(runtime_report, "uses_wma_sms", False))

    startup_reachable = bool(getattr(activation_report, "startup_activation_reachable", False))
    activation_gate = bool(getattr(activation_report, "likely_activation_gate", False))
    payment_flow = bool(getattr(activation_report, "likely_payment_flow", False))
    wma_linked = bool(getattr(activation_report, "wma_linked", False))
    activation_risk = str(getattr(activation_report, "risk", "low") or "low").lower()

    reasons: List[str] = []
    if unsupported:
        reasons.append("RG35XX unsupported API: " + ", ".join(sorted(unsupported)))
    if conditional:
        reasons.append("API cần kiểm thử runtime: " + ", ".join(sorted(conditional)))
    if uses_wma:
        reasons.append("Phát hiện legacy WMA/SMS")
    if activation_gate:
        reasons.append("Có dấu hiệu activation/registration gate")
    if payment_flow:
        reasons.append("Có dấu hiệu payment/subscription flow")
    if wma_linked:
        reasons.append("Activation/payment liên kết WMA/SMS")
    if startup_reachable:
        reasons.append("Class nghi vấn statically reachable từ MIDlet entry")

    # Strongest case: application-level gate sits on a static startup path and
    # depends on WMA or another API the RG35XX profile marks unsupported.
    if startup_reachable and (wma_linked or uses_wma or bool(unsupported)):
        return StartupBlockingAssessment(
            classification="likely_startup_blocker",
            severity="high",
            title="Likely startup blocker",
            reasons=reasons,
            recommendation=(
                "Ưu tiên kiểm tra class trên startup path và runtime API bị thiếu. "
                "Không coi việc chặn SMS là activation thành công."
            ),
        )

    # Suspicious flow exists but no static path from MIDlet entry was found.
    if activation_risk in {"medium", "high"} or activation_gate or payment_flow:
        return StartupBlockingAssessment(
            classification="optional_feature_risk",
            severity="medium",
            title="Optional feature risk",
            reasons=reasons,
            recommendation=(
                "Flow activation/payment có thể chỉ nằm ở menu hoặc chức năng phụ. "
                "Cần test runtime để xác nhận trước khi coi đây là lỗi startup."
            ),
        )

    # Runtime dependency is the dominant issue and no application gate was found.
    if unsupported or uses_wma:
        return StartupBlockingAssessment(
            classification="runtime_only_incompatibility",
            severity="high" if unsupported else "medium",
            title="Runtime-only incompatibility",
            reasons=reasons,
            recommendation=(
                "Tập trung vào khả năng hỗ trợ API của FreeJ2ME / RG35XX; "
                "chưa có bằng chứng mạnh về application-level activation gate."
            ),
        )

    if conditional:
        return StartupBlockingAssessment(
            classification="needs_runtime_test",
            severity="medium",
            title="Needs runtime test",
            reasons=reasons,
            recommendation="Các API conditional cần được kiểm thử trực tiếp trên target runtime.",
        )

    return StartupBlockingAssessment(reasons=reasons)
