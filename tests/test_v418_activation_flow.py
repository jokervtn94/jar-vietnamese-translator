from __future__ import annotations

import zipfile

from core.activation_flow_analyzer import ActivationFlowAnalyzer


def _make_activation_jar(path):
    fake_class = (
        b"\xca\xfe\xba\xbe"
        b"game/pay/Activate\x00"
        b"javax/wireless/messaging/MessageConnection\x00"
        b"sms://10612345\x00"
        b"activation\x00purchase\x00payment\x00"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("game/pay/Activate.class", fake_class)
        z.writestr("res/pay.txt", "激活\n购买\n短信")


def test_activation_detector_links_wma_and_activation(tmp_path):
    jar = tmp_path / "legacy_activation.jar"
    _make_activation_jar(jar)

    report = ActivationFlowAnalyzer().analyze(str(jar))

    assert report.risk == "high"
    assert report.score >= 60
    assert report.wma_linked is True
    assert report.likely_activation_gate is True
    assert report.likely_payment_flow is True
    assert "game/pay/Activate.class" in report.suspicious_classes
    assert any(item.category == "activation_gate" for item in report.findings)
    assert any(item.category == "payment_flow" for item in report.findings)


def test_activation_detector_stays_low_for_plain_game(tmp_path):
    jar = tmp_path / "plain.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("game/Main.class", b"\xca\xfe\xba\xbeStartGameOptionsExit")
        z.writestr("res/text.txt", "Start\nOptions\nExit")

    report = ActivationFlowAnalyzer().analyze(str(jar))

    assert report.risk == "low"
    assert report.likely_activation_gate is False
    assert report.likely_payment_flow is False
    assert report.wma_linked is False
