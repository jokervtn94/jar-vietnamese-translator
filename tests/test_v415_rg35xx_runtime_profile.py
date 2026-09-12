from core.runtime_profiles import assess_profile, get_runtime_profile


def test_rg35xx_profile_denies_real_sms_transport():
    profile = get_runtime_profile("freej2me_rg35xx")
    assert profile.label == "FreeJ2ME / RG35XX"
    assert profile.messaging_policy == "deny_transport"
    assert "wma_sms" in profile.unsupported_apis


def test_wma_is_high_risk_for_rg35xx():
    result = assess_profile({"wma_sms"}, "freej2me_rg35xx")
    assert result.risk == "high"
    assert result.score == 75
    assert result.unsupported == ["wma_sms"]
    assert any("do not send SMS" in note for note in result.notes)


def test_generic_midp_without_optional_api_is_low_risk():
    result = assess_profile(set(), "freej2me_rg35xx")
    assert result.risk == "low"
    assert result.score == 100
    assert result.unsupported == []


def test_optional_api_stays_conditional():
    result = assess_profile({"m3g", "file_connection"}, "freej2me_rg35xx")
    assert result.risk == "medium"
    assert result.score == 80
    assert result.conditional == ["file_connection", "m3g"]
