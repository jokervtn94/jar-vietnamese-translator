
from pathlib import Path
import tempfile, zipfile
from core.jar_scanner import JarScanner

def values(result):
    return [(c.source,s.value,s.kind) for c in result.candidates for s in c.strings]

def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        jar=td/"odd_game.jar"
        with zipfile.ZipFile(jar,"w") as z:
            z.writestr("META-INF/MANIFEST.MF","MIDlet-Name: Odd Game\n")
            # Unknown extension: V4.2 skipped this completely.
            z.writestr("res/english.locx", b"START=New Game\nEXIT=Exit\nOK=OK\n")
            # UTF-16LE text with non-standard binary-ish extension.
            z.writestr("data/words.tbl", "Play\nContinue\nOptions\nGame Over".encode("utf-16le"))
            # Raw binary with embedded readable text.
            z.writestr("assets/game.pak2", b"\x01\x99MENU\x00\x13Start Game\x00\x04Help\x00")
            # Media should remain ignored.
            z.writestr("gfx/font.png", b"\x89PNG\r\n\x1a\n"+b"A"*200)

        r=JarScanner().scan(str(jar))
        vals=values(r)
        texts=[v for _,v,_ in vals]
        assert "New Game" in texts, texts
        assert "Exit" in texts, texts
        assert "OK" in texts, texts
        assert any("Continue" in x for x in texts), texts
        assert any("Start Game" in x for x in texts), texts
        assert r.diagnostics["entries_deep_scanned"] >= 3, r.diagnostics
        assert r.diagnostics["total_strings"] > 0
        assert not any(src=="gfx/font.png" for src,_,_ in vals)
        print("V4.3 Deep Scan tests: PASS")
        print("Diagnostics:",r.diagnostics)

if __name__=="__main__":
    main()
