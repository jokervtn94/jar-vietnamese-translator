import json
from pathlib import Path

from core.translation_exchange import TranslationExchange
from models.data import Candidate, ExtractedString, JarScanResult


def _result_from_exchange(path):
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    groups={}
    for row in payload["items"]:
        s=ExtractedString(
            source=row["source"], value=row["original"], kind=row["kind"],
            index=row["index"], encoding="utf-8"
        )
        groups.setdefault(row["source"],[]).append(s)
    candidates=[Candidate(source=k,source_type="test",strings=v,score=100) for k,v in groups.items()]
    # Nonexistent source path intentionally skips JAR-file hashing while preserving name.
    return payload, JarScanResult(jar_path="/tmp/"+payload["source_jar"]["name"], candidates=candidates)


def test_prepare_import_real_559_json_is_complete_and_non_mutating():
    src=Path("/mnt/data/仙侣情缘之麒麟劫320x240_translate_vi_completed_v411.json")
    if not src.exists():
        return
    payload,result=_result_from_exchange(src)
    existing={}
    report,updates=TranslationExchange().prepare_import_payload(payload,result,existing,overwrite=False)
    assert report.imported == 559
    assert report.rejected_total == 0
    assert len(updates) == 559
    assert existing == {}  # preparation must never mutate live project state


def test_prepare_import_respects_existing_without_overwrite(tmp_path):
    original="Score: %d"
    s=ExtractedString(source="a.class",value=original,kind="class-string",index=1)
    result=JarScanResult(jar_path=str(tmp_path/"game.jar"),candidates=[Candidate("a.class","class",[s],100)])
    payload=TranslationExchange().export_payload(result, type("P",(),{"get":lambda self,k:""})())
    payload["items"][0]["translation"]="Điểm: %d"
    existing={s.key:"Cũ: %d"}
    report,updates=TranslationExchange().prepare_import_payload(payload,result,existing,overwrite=False)
    assert report.imported == 0
    assert report.skipped_existing == 1
    assert updates == {}
    assert existing[s.key] == "Cũ: %d"
