import tempfile
import zipfile

from core.runtime_api_analyzer import RuntimeApiAnalyzer


def _make_jar(class_blob: bytes, manifest: str):
    tmp = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", manifest)
        z.writestr("game/Test.class", class_blob)
    return tmp.name


def test_detects_midp_cldc_and_wma_sms_dependency():
    path = _make_jar(
        b"xxjavax/wireless/messaging/MessageConnectionxxTextMessagexxsms://10612345xx",
        "MicroEdition-Profile: MIDP-2.0\nMicroEdition-Configuration: CLDC-1.1\n",
    )
    report = RuntimeApiAnalyzer().analyze(path)
    assert report.midp_profile == "MIDP-2.0"
    assert report.cldc_configuration == "CLDC-1.1"
    assert report.uses_wma_sms is True
    assert report.runtime_risk == "high"
    assert report.compatibility_score < 100
    assert any(x.startswith("sms://10612345") for x in report.sms_targets)


def test_detects_vendor_specific_api():
    path = _make_jar(
        b"xxcom/nokia/mid/ui/FullCanvasxx",
        "MicroEdition-Profile: MIDP-2.0\nMicroEdition-Configuration: CLDC-1.1\n",
    )
    report = RuntimeApiAnalyzer().analyze(path)
    assert "nokia" in report.detected_apis
    assert report.uses_vendor_api is True
    assert report.runtime_risk == "high"


def test_generic_midlet_stays_low_risk():
    path = _make_jar(
        b"xxjavax/microedition/lcdui/Canvasxx",
        "MicroEdition-Profile: MIDP-2.0\nMicroEdition-Configuration: CLDC-1.1\n",
    )
    report = RuntimeApiAnalyzer().analyze(path)
    assert report.runtime_risk == "low"
    assert report.compatibility_score == 100
