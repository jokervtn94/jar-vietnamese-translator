from pathlib import Path
import tempfile
import zipfile

from core.jar_scanner import JarScanner


def make_archive(path: Path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMIDlet-Name: Test\n")
        z.writestr("lang/en.txt", "Start Game\nOptions\nExit\n")


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    jar_path = td / "sample.jar"
    zip_path = td / "sample.zip"
    make_archive(jar_path)
    zip_path.write_bytes(jar_path.read_bytes())

    jar_result = JarScanner().scan(str(jar_path))
    zip_result = JarScanner().scan(str(zip_path))

    assert jar_result.entries == zip_result.entries
    assert jar_result.diagnostics["entries_total"] == zip_result.diagnostics["entries_total"]
    assert jar_result.diagnostics["entries_total"] >= 2

    bad = td / "broken.jar"
    bad.write_bytes(b"not-a-zip")
    try:
        JarScanner().scan(str(bad))
    except zipfile.BadZipFile as e:
        assert "JAR/ZIP" in str(e)
    else:
        raise AssertionError("broken .jar must be rejected")

print("V4.6.1 JAR extension/archive loading regression: PASS")
