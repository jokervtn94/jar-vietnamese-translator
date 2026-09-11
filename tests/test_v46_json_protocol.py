
from pathlib import Path
import tempfile,zipfile,json,copy
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.translation_exchange import TranslationExchange, FORMAT_V2

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
        payload=ex.export_payload(result,project)

        assert payload["format"]==FORMAT_V2
        assert payload["schema_version"]==2
        assert payload["translation_protocol"]["output_contract"]["item_count"]==len(payload["items"])
        assert "mandatory_rules" in payload["translation_protocol"]
        assert payload["source_jar"]["sha256"]
        assert payload["items"]
        for row in payload["items"]:
            assert row["original_sha256"]
            assert "placeholders" in row
            assert row["translation"]==""

        # Simulate compliant model output.
        good=copy.deepcopy(payload)
        for row in good["items"]:
            if row["original"]=="New Game":
                row["translation"]="Trò chơi mới"
            elif row["original"]=="Exit":
                row["translation"]="Thoát"
            elif row["original"]=="Score: %d":
                row["translation"]="Điểm: %d"
            else:
                row["translation"]=row["original"]
        r=ex.import_payload(good,result,project)
        assert r.imported>=3, r
        assert r.rejected_total==0, r

        # Model changed immutable original -> reject.
        bad_original=copy.deepcopy(payload)
        for row in bad_original["items"]:
            row["translation"]=row["original"]
        bad_original["items"][0]["original"]="CHANGED"
        r2=ex.import_payload(bad_original,result,TranslationProject(jar_path=str(jar)))
        assert r2.rejected_original_mismatch>=1

        # Model changed original hash -> reject.
        bad_hash=copy.deepcopy(payload)
        for row in bad_hash["items"]:
            row["translation"]=row["original"]
        bad_hash["items"][0]["original_sha256"]="0"*64
        r3=ex.import_payload(bad_hash,result,TranslationProject(jar_path=str(jar)))
        assert r3.rejected_hash>=1

        # Model dropped an item but left output_contract item_count -> whole file rejected.
        bad_count=copy.deepcopy(payload)
        bad_count["items"]=bad_count["items"][:-1]
        r4=ex.import_payload(bad_count,result,TranslationProject(jar_path=str(jar)))
        assert r4.rejected_schema>=1
        assert r4.imported==0

        # Wrong source JAR hash -> whole file rejected.
        bad_jar=copy.deepcopy(payload)
        bad_jar["source_jar"]["sha256"]="f"*64
        r5=ex.import_payload(bad_jar,result,TranslationProject(jar_path=str(jar)))
        assert r5.rejected_source_jar>=1
        assert r5.imported==0

        # Placeholder changed -> reject.
        bad_ph=copy.deepcopy(payload)
        for row in bad_ph["items"]:
            row["translation"]=row["original"]
            if row["original"]=="Score: %d":
                row["translation"]="Điểm"
        r6=ex.import_payload(bad_ph,result,TranslationProject(jar_path=str(jar)))
        assert r6.rejected_placeholder>=1

        print("V4.6 JSON protocol tests: PASS")

if __name__=="__main__":
    main()
