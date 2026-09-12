from pathlib import Path
import tempfile, zipfile

from core.jar_scanner import JarScanner
from core.resource_scanner import ResourceScanner
from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.language_detector import LanguageDetector
from core.class_reader import ClassReader
from models.data import ExtractedString


def all_values(result):
    return [s.value for c in result.candidates for s in c.strings]


def main():
    # 1) Text resource encoded as GB18030 must not fall through to Latin-1 mojibake.
    rs = ResourceScanner()
    text = "开始游戏\n继续游戏\n退出游戏"
    vals = [x.value for x in rs._scan_text("res/lang.dat", text.encode("gb18030"))]
    assert "开始游戏" in vals and "继续游戏" in vals and "退出游戏" in vals, vals

    # 2) CJK discovered by deep scan must survive the language classifier.
    d = LanguageDetector()
    item = ExtractedString("item.bin", "九转还魂丹 全体复活", "deep-binary-gb18030", 10, "gb18030")
    assert d.filter_strings([item]), d.classify(item.value, item.source, item.kind)

    # 3) Framed GB18030 binary string should be decoded as Chinese and remain patch-safe.
    payload = "攻击+50，三回合".encode("gb18030")
    data = bytes([len(payload)]) + payload + b"\x00\x01"
    ba = BinaryResourceAnalyzer().analyze("item.bin", data)
    assert any("攻击" in x.text for x in ba.strings), [(x.text,x.encoding,x.framing) for x in ba.strings]

    # 4) Raw GB18030 content in unknown extension must be discovered by deep scan path.
    with tempfile.TemporaryDirectory() as td:
        jar = Path(td) / "cn_game.jar"
        with zipfile.ZipFile(jar, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "MIDlet-Name: CN Game\n")
            z.writestr("data/dialog.tblx", b"\x01\x02" + "开始游戏 请选择角色".encode("gb18030") + b"\x00\xff")
            z.writestr("data/item.bin", bytes([len(payload)]) + payload + b"\x00")
        r = JarScanner().scan(str(jar))
        values = all_values(r)
        assert any("开始游戏" in v for v in values), values
        assert any("攻击" in v for v in values), values
        assert r.diagnostics["strings_after_filter"] > 0

    # 5) MUTF-8/CESU-8 surrogate-pair decoding.
    # U+1F600 encoded as CESU-8 surrogate pair ED A0 BD ED B8 80.
    assert ClassReader.decode_modified_utf8(bytes.fromhex("EDA0BDEDB880")) == "😀"

    print("V4.7 Extractor V3 tests: PASS")


if __name__ == "__main__":
    main()
