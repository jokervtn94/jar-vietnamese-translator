import tempfile
import zipfile
from pathlib import Path

from core.rebuild_support import install_same_name_build_support
from core.jar_builder import JarBuilder
from core.translation_project import TranslationProject
from models.data import JarScanResult, Candidate, ExtractedString


def make_result(jar_path: Path):
    s = ExtractedString(
        source="lang.txt",
        value="Hello",
        kind="resource-text",
        index=0,
        encoding="utf-8",
    )
    c = Candidate("lang.txt", "resource", [s], 100, ["test"])
    return JarScanResult(str(jar_path), ["lang.txt"], "", [c], {})


def read_text(jar_path: Path):
    with zipfile.ZipFile(jar_path, "r") as z:
        return z.read("lang.txt").decode("utf-8")


def main():
    install_same_name_build_support()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "game.jar"
        with zipfile.ZipFile(source, "w") as z:
            z.writestr("lang.txt", "Hello\n")

        result = make_result(source)
        project = TranslationProject(jar_path=str(source))
        s = result.candidates[0].strings[0]
        project.set(s.key, "Xin chao")

        renamed = root / "game_vi.jar"
        report1 = JarBuilder().build(result, project, str(renamed))
        assert report1.validation_ok
        assert renamed.exists()
        assert "Xin chao" in read_text(renamed)
        assert read_text(source) == "Hello\n"

        report2 = JarBuilder().build(result, project, str(source))
        assert report2.validation_ok
        assert "Xin chao" in read_text(source)
        backup = root / "game.original.jar"
        assert backup.exists()
        assert read_text(backup) == "Hello\n"

        project.set(s.key, "Chao ban")
        report3 = JarBuilder().build(result, project, str(source))
        assert report3.validation_ok
        assert "Chao ban" in read_text(source)
        assert read_text(backup) == "Hello\n"

        renamed2 = root / "game_vi_2.jar"
        report4 = JarBuilder().build(result, project, str(renamed2))
        assert report4.validation_ok
        assert "Chao ban" in read_text(renamed2)

    print("V4.6.2 same-name / renamed rebuild tests: PASS")


if __name__ == "__main__":
    main()
