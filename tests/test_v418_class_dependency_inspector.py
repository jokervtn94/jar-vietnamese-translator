from __future__ import annotations

import zipfile

from core.activation_flow_analyzer import ActivationFlowAnalyzer
from core.class_dependency_inspector import ClassDependencyInspector
from core.dependency_path_presenter import summarize_dependency_path


def _write_jar(path, startup_links_activation: bool):
    manifest = (
        "Manifest-Version: 1.0\r\n"
        "MIDlet-Name: Dependency Test\r\n"
        "MIDlet-1: Test,,game.MainMIDlet\r\n"
        "MicroEdition-Profile: MIDP-2.0\r\n"
        "MicroEdition-Configuration: CLDC-1.1\r\n\r\n"
    )
    main = b"\xca\xfe\xba\xbe game/Manager\x00"
    manager = b"\xca\xfe\xba\xbe"
    if startup_links_activation:
        manager += b" game/pay/Activate\x00"
    else:
        manager += b" game/Menu\x00"
    activate = (
        b"\xca\xfe\xba\xbe activate activation payment purchase "
        b"javax/wireless/messaging/MessageConnection sms://10612345"
    )
    menu = b"\xca\xfe\xba\xbe game/pay/Activate\x00"

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", manifest)
        z.writestr("game/MainMIDlet.class", main)
        z.writestr("game/Manager.class", manager)
        z.writestr("game/Menu.class", menu)
        z.writestr("game/pay/Activate.class", activate)


def test_dependency_inspector_finds_startup_path(tmp_path):
    jar = tmp_path / "startup.jar"
    _write_jar(jar, True)

    report = ClassDependencyInspector().analyze(
        str(jar), ["game/pay/Activate.class"]
    )

    assert report.roots == ["game.MainMIDlet"]
    assert report.startup_activation_reachable is True
    reachable = [p for p in report.activation_paths if p.startup_reachable]
    assert reachable
    assert reachable[0].path == [
        "game.MainMIDlet", "game.Manager", "game.pay.Activate"
    ]


def test_activation_flow_promotes_startup_reachable_gate(tmp_path):
    jar = tmp_path / "flow.jar"
    _write_jar(jar, True)

    report = ActivationFlowAnalyzer().analyze(str(jar))

    assert report.startup_activation_reachable is True
    assert report.likely_activation_gate is True
    assert report.wma_linked is True
    assert report.risk == "high"
    messages = "\n".join(x.message for x in report.findings)
    assert "statically reachable" in messages
    assert "game.MainMIDlet" in messages
    assert "game.pay.Activate" in messages

    summary = summarize_dependency_path(report)
    assert summary.startswith("Startup reachable:")
    assert "game.MainMIDlet -> game.Manager -> game.pay.Activate" in summary
