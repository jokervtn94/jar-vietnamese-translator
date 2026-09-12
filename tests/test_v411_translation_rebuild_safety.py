import io
import struct
import zipfile
from pathlib import Path

from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.binary_resource_patcher import patch_binary_entry
from core.class_patcher import ClassPatcher
from core.class_reader import ClassReader
from core.jar_builder import JarBuilder
from core.jar_scanner import JarScanner
from core.language_detector import LanguageDetector
from core.translation_project import TranslationProject
from models.data import ExtractedString


def accepted(value, source, kind):
    d = LanguageDetector()
    x = ExtractedString(source=source, value=value, kind=kind, index=0, encoding="utf-8")
    score, _ = d.classify(value, source, kind)
    return score >= d._threshold(x)


def _minimal_class_with_utf8(text: str) -> bytes:
    raw = text.encode("utf-8")
    # Minimal parseable class for this project's ClassReader: magic/version,
    # cp_count=2, one CONSTANT_Utf8, then class tail bytes are not interpreted
    # by extract_strings after the constant pool.
    return (
        b"\xca\xfe\xba\xbe" + struct.pack(">HHH", 0, 46, 3) +
        b"\x01" + struct.pack(">H", len(raw)) + raw +
        b"\x08" + struct.pack(">H", 1) +
        b"\x00" * 8
    )


def test_reject_bare_map_extension_but_keep_map_label():
    assert not accepted(".map", "ae.class", "class-string")
    assert accepted("map", "af.class", "class-string")


def test_class_patcher_accepts_longer_vietnamese_mutf8():
    data = _minimal_class_with_utf8("存档成功")
    vi = "Lưu trò chơi thành công"
    patched, count = ClassPatcher.patch(data, {1: vi})
    assert count == 1
    strings = ClassReader(patched, "x.class").extract_strings()
    assert any(x.index == 1 and x.value == vi for x in strings)
    assert len(patched) > len(data)


def test_binary_u8_length_updates_for_longer_vietnamese():
    zh = "九转还魂丹".encode("utf-8")
    data = bytes([len(zh)]) + zh
    item = BinaryResourceAnalyzer().analyze("item.bin", data).strings[0]
    vi = "Cửu Chuyển Hoàn Hồn Đan"
    patched = patch_binary_entry(data, item, vi)
    encoded = vi.encode("utf-8")
    assert patched[0] == len(encoded)
    assert patched[1:1+len(encoded)] == encoded


def test_builder_transaction_rolls_back_binary_source_on_oversize_field(tmp_path):
    a = "九转还魂丹".encode("utf-8")
    b = "全体复活".encode("utf-8")
    payload = bytes([len(a)]) + a + bytes([len(b)]) + b
    jar = tmp_path / "game.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("item.bin", payload)

    result = JarScanner().scan(str(jar))
    rows = [s for _, s in result.all_strings() if s.source == "item.bin" and s.kind.endswith(":safe")]
    assert any(s.value == "九转还魂丹" for s in rows)
    assert any(s.value == "全体复活" for s in rows)

    project = TranslationProject()
    for s in rows:
        if s.value == "九转还魂丹":
            project.set(s.key, "Cửu Chuyển Hoàn Hồn Đan")
        elif s.value == "全体复活":
            project.set(s.key, "A" * 256)  # impossible for u8

    out = tmp_path / "out.jar"
    report = JarBuilder().build(result, project, str(out))
    assert report.failed >= 2
    with zipfile.ZipFile(out, "r") as z:
        assert z.read("item.bin") == payload


def test_builder_rebuilds_two_variable_length_binary_fields_transactionally(tmp_path):
    a = "九转还魂丹".encode("utf-8")
    b = "全体复活".encode("utf-8")
    payload = bytes([len(a)]) + a + bytes([len(b)]) + b
    jar = tmp_path / "game.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("item.bin", payload)

    result = JarScanner().scan(str(jar))
    project = TranslationProject()
    for _, s in result.all_strings():
        if s.value == "九转还魂丹":
            project.set(s.key, "Cửu Chuyển Hoàn Hồn Đan")
        elif s.value == "全体复活":
            project.set(s.key, "Hồi sinh toàn đội")

    out = tmp_path / "out.jar"
    report = JarBuilder().build(result, project, str(out))
    assert report.failed == 0
    assert report.patched == 2
    assert report.validation_ok
    assert report.regression_ok
    with zipfile.ZipFile(out, "r") as z:
        data = z.read("item.bin")
    post = BinaryResourceAnalyzer().analyze("item.bin", data)
    vals = {x.text for x in post.strings if x.patch_safe}
    assert "Cửu Chuyển Hoàn Hồn Đan" in vals
    assert "Hồi sinh toàn đội" in vals
