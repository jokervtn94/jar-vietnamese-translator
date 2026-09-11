
from pathlib import Path
import tempfile,zipfile
from core.jar_scanner import JarScanner
from core.language_detector import LanguageDetector
from models.data import ExtractedString

def main():
    d=LanguageDetector()
    good=[
        "New Game","Continue","Options","Game Over","Press any key",
        "Are you sure?","Level 10","Save completed!","OK","HP","Retry"
    ]
    bad=[
        "java/lang/String","javax.microedition.lcdui.Graphics",
        "getPlayerName","drawString","COMMAND_ACTION",
        "res/images/menu.png","http://example.com/test",
        "(Ljava/lang/String;)V","a8f3c19d90aa44ff",
        "application/octet-stream","key_pressed","com.game.engine.Renderer"
    ]

    accepted=[]
    for i,s in enumerate(good):
        item=ExtractedString("res/strings.dat",s,"deep-binary-ascii",i,"ascii")
        if d.filter_strings([item]):
            accepted.append(s)
    assert set(good)==set(accepted), ("good rejected",set(good)-set(accepted))

    rejected=[]
    for i,s in enumerate(bad):
        item=ExtractedString("com/game/Engine.class",s,"deep-binary-ascii",i,"ascii")
        if not d.filter_strings([item]):
            rejected.append(s)
    assert set(bad)==set(rejected), ("bad accepted",set(bad)-set(rejected))

    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        jar=td/"noisy.jar"
        with zipfile.ZipFile(jar,"w") as z:
            z.writestr("res/text.tbl",
                b"New Game\x00Continue\x00Options\x00Game Over\x00"
                b"drawString\x00getPlayerName\x00COMMAND_ACTION\x00"
                b"java/lang/String\x00res/images/menu.png\x00")
            z.writestr("com/game/Debug.cfg",
                b"http://example.com\napplication/octet-stream\nkey_pressed\n")
        r=JarScanner().scan(str(jar))
        vals=[s.value for c in r.candidates for s in c.strings]
        assert "New Game" in vals
        assert "Continue" in vals
        assert "Options" in vals
        assert "Game Over" in vals
        assert "drawString" not in vals
        assert "getPlayerName" not in vals
        assert "COMMAND_ACTION" not in vals
        assert "java/lang/String" not in vals
        assert "res/images/menu.png" not in vals
        assert r.diagnostics["strings_rejected_non_language"] > 0

    print("V4.4 Precision Scan tests: PASS")

if __name__=="__main__":
    main()
