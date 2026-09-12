from __future__ import annotations

import zipfile
from types import SimpleNamespace

from core.build_readiness import BuildReadinessAnalyzer
from core.glyph_analyzer import GlyphAnalyzer


def _make_wma_jar(path):
    manifest = (
        "Manifest-Version: 1.0\r\n"
        "MIDlet-Name: Runtime Test\r\n"
        "MicroEdition-Profile: MIDP-2.0\r\n"
        "MicroEdition-Configuration: CLDC-1.1\r\n\r\n"
    )
    fake_class = (
        b"\xca\xfe\xba\xbe"
        b"javax/wireless/messaging/MessageConnection\x00"
        b"javax/wireless/messaging/TextMessage\x00"
        b"sms://10612345\x00"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", manifest)
        z.writestr("game/pay/Activate.class", fake_class)


def test_build_readiness_surfaces_rg35xx_wma_risk(tmp_path, monkeypatch):
    jar = tmp_path / "wma.jar"
    _make_wma_jar(jar)

    monkeypatch.setattr(
        GlyphAnalyzer,
        "analyze",
        lambda self, *args, **kwargs: SimpleNamespace(
            maps=[], missing_chars=set(), risk="low"
        ),
    )

    string = SimpleNamespace(
        key="k1",
        kind="class",
        value="Start",
        source="game/Main.class",
        encoding="utf-8",
    )
    result = SimpleNamespace(
        jar_path=str(jar),
        all_strings=lambda: [("game/Main.class", string)],
    )
    project = SimpleNamespace(get=lambda key: "Bắt đầu")

    report = BuildReadinessAnalyzer().analyze(result, project)

    assert report.runtime_risk == "high"
    assert report.runtime_score < 100
    assert report.status == "WARNING"
    messages = "\n".join(issue.message for issue in report.issues)
    assert "WMA/SMS" in messages
    assert "Real SMS transport must remain disabled" in messages
    assert "10612345" in messages
    assert any(issue.category == "runtime" for issue in report.issues)
