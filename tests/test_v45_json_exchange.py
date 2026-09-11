
from pathlib import Path
import tempfile,zipfile,json
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.translation_exchange import TranslationExchange

def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        jar=td/"game.jar"
        with zipfile.ZipFile(jar,"w") as z:
            z.writestr("res/lang.properties",
                "start=New Game\nscore=Score: %d\nexit=Exit\n".encode("utf-8"))

        result=JarScanner().scan(str(jar))
        project=TranslationProject(jar_path=str(jar))
        ex=TranslationExchange()

        out=td/"translate.json"
        count=ex.export_file(result,project,str(out))
        assert count>=3
        payload=json.loads(out.read_text(encoding="utf-8"))
        assert payload["format"] in ("jar-translator-exchange-v1","jar-translator-exchange-v2")
        assert all("original" in x and "translation" in x for x in payload["items"])

        for row in payload["items"]:
            if row["original"]=="New Game":
                row["translation"]="Trò chơi mới"
            elif row["original"]=="Exit":
                row["translation"]="Thoát"
            elif row["original"]=="Score: %d":
                row["translation"]="Điểm: %d"
            else:
                row["translation"]=row["original"]

        translated=td/"translated.json"
        translated.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        r=ex.import_file(str(translated),result,project)
        assert r.imported>=3, r
        assert any(v=="Trò chơi mới" for v in project.translations.values())
        assert any(v=="Điểm: %d" for v in project.translations.values())

        # Placeholder safety
        p2=ex.export_payload(result,TranslationProject(jar_path=str(jar)))
        for row in p2["items"]:
            if row["original"]=="Score: %d":
                row["translation"]="Điểm"
            else:
                row["translation"]=row["original"]
        r2=ex.import_payload(p2,result,TranslationProject(jar_path=str(jar)))
        assert r2.rejected_placeholder>=1

        # Simple original -> translation dictionary format
        p3=TranslationProject(jar_path=str(jar))
        r3=ex.import_payload({"New Game":"Game mới","Exit":"Thoát"},result,p3)
        assert r3.imported>=2

        print("V4.5 JSON exchange tests: PASS")

if __name__=="__main__":
    main()
