from pathlib import Path
import zipfile

from core.jar_scanner import JarScanner
from core.jar_builder import JarBuilder
from core.translation_project import TranslationProject


def test_builder_uses_temp_archive_and_atomic_publish(tmp_path):
    raw = "保存成功".encode("utf-8")
    jar = tmp_path / "game.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("text.bin", bytes([len(raw)]) + raw)

    result = JarScanner().scan(str(jar))
    project = TranslationProject()
    row = next(s for _, s in result.all_strings() if s.source == "text.bin" and s.value == "保存成功" and s.kind.endswith(":safe"))
    project.set(row.key, "Lưu thành công")

    out = tmp_path / "translated.jar"
    report = JarBuilder().build(result, project, str(out))
    assert out.exists()
    assert not (tmp_path / "translated.jar.building").exists()
    assert report.entries_written == 1
    with zipfile.ZipFile(out, "r") as z:
        assert z.testzip() is None
        assert "Lưu thành công".encode("utf-8") in z.read("text.bin")


def test_gui_build_is_worker_based_and_consolidates_preflight():
    source = Path(__file__).parents[1] / "gui" / "main_window.py"
    text = source.read_text(encoding="utf-8")
    assert "class BuildPreflightWorker(QThread)" in text
    assert "class BuildWorker(QThread)" in text
    assert "self._build_worker.start()" in text
    assert "One dialog only" in text
    assert "JarBuilder().build(self.result, self.project, path)" not in text
