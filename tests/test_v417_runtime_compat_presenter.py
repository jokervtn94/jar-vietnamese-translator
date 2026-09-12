from core.runtime_api_analyzer import RuntimeApiReport
from core.runtime_compat_presenter import summarize_runtime
from core.runtime_profiles import assess_profile


def test_presenter_summarizes_wma_policy_and_rg35xx_score():
    report = RuntimeApiReport(
        midp_profile="MIDP-2.0",
        cldc_configuration="CLDC-1.1",
        detected_apis={"wma_sms", "media"},
        sms_targets=["sms://10612345"],
    )
    report.rg35xx = assess_profile(report.detected_apis, "freej2me_rg35xx")
    report.runtime_risk = report.rg35xx.risk
    report.compatibility_score = report.rg35xx.score

    summary = summarize_runtime(report)

    assert summary.target == "FreeJ2ME / RG35XX"
    assert summary.risk == "high"
    assert summary.score == 75
    assert summary.uses_wma_sms is True
    assert "wma_sms" in summary.unsupported
    assert summary.sms_targets == ("sms://10612345",)
    assert summary.wma_policy == "deny_transport"
    text = "\n".join(summary.lines())
    assert "Chặn transport SMS thật" in text
    assert "10612345" in text


def test_presenter_keeps_clean_midp_jar_at_low_risk():
    report = RuntimeApiReport(
        midp_profile="MIDP-2.0",
        cldc_configuration="CLDC-1.1",
        detected_apis=set(),
    )
    report.rg35xx = assess_profile(set(), "freej2me_rg35xx")
    summary = summarize_runtime(report)

    assert summary.score == 100
    assert summary.risk == "low"
    assert summary.uses_wma_sms is False
    assert summary.unsupported == ()
    assert summary.conditional == ()
