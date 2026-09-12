from types import SimpleNamespace

from core.startup_blocking_assessment import assess_startup_blocking


def _runtime(*, unsupported=(), conditional=(), uses_wma=False):
    target = SimpleNamespace(unsupported=list(unsupported), conditional=list(conditional))
    return SimpleNamespace(rg35xx=target, uses_wma_sms=uses_wma)


def _activation(
    *,
    risk="low",
    startup=False,
    gate=False,
    payment=False,
    wma_linked=False,
):
    return SimpleNamespace(
        risk=risk,
        startup_activation_reachable=startup,
        likely_activation_gate=gate,
        likely_payment_flow=payment,
        wma_linked=wma_linked,
    )


def test_startup_reachable_wma_gate_is_likely_blocker():
    assessment = assess_startup_blocking(
        _runtime(unsupported=("wma_sms",), uses_wma=True),
        _activation(risk="high", startup=True, gate=True, wma_linked=True),
    )
    assert assessment.classification == "likely_startup_blocker"
    assert assessment.severity == "high"
    assert "Likely startup blocker" in assessment.title


def test_activation_without_startup_path_is_optional_feature_risk():
    assessment = assess_startup_blocking(
        _runtime(),
        _activation(risk="high", startup=False, gate=True, payment=True),
    )
    assert assessment.classification == "optional_feature_risk"
    assert assessment.severity == "medium"


def test_unsupported_api_without_gate_is_runtime_only():
    assessment = assess_startup_blocking(
        _runtime(unsupported=("nokia",)),
        _activation(),
    )
    assert assessment.classification == "runtime_only_incompatibility"
    assert assessment.severity == "high"


def test_conditional_api_only_requires_runtime_test():
    assessment = assess_startup_blocking(
        _runtime(conditional=("m3g",)),
        _activation(),
    )
    assert assessment.classification == "needs_runtime_test"
    assert assessment.severity == "medium"


def test_clean_profile_has_no_clear_startup_blocker():
    assessment = assess_startup_blocking(_runtime(), _activation())
    assert assessment.classification == "compatible_or_unknown"
    assert assessment.severity == "low"
