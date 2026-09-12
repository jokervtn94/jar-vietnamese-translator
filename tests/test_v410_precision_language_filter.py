from core.language_detector import LanguageDetector
from models.data import ExtractedString


def accepted(value, source, kind):
    d=LanguageDetector()
    x=ExtractedString(source=source,value=value,kind=kind,index=0,encoding="utf-8")
    score,_=d.classify(value,source,kind)
    return score >= d._threshold(x)


def test_reject_cfg_binary_garbage_patterns():
    bad=[
        ".h[PVLvXh`nLvX}ao|vZX",
        "nLvXi",
        "nLv<i",
        "vXibnLv[ianNvXicnLvZianLvXibnL",
        "v[ianLvXibnLcZianIvXidnLv[ianOvXibnLvXianOvX\x7fKnLv]ianIvXibnLv[ianOvXianLv[ia",
    ]
    for s in bad:
        assert not accepted(s,"cfg.bin","binary:u8-length-prefixed:safe"), s


def test_reject_binary_command_script():
    s="aplayer 1;magic 1 1 146;magic 1 1 142;item 50 1;equip 1 50;stage 4 0;scene 101 10 10 2;"
    assert not accepted(s,"event.bin","binary:u16be-length-prefixed:safe")


def test_keep_real_cjk_binary_text():
    good=[
        ("九转还魂丹","item.bin","binary:u8-length-prefixed:safe"),
        ("全体复活","item.bin","binary:u8-length-prefixed:safe"),
        ("增加体力上限100，30级可用","item.bin","binary:u8-length-prefixed:safe"),
        ("宁云峰","property.bin","binary:u8-length-prefixed:safe"),
        ('(系统提示: )角色已达到(',"tek.bin","binary:u16be-length-prefixed:safe"),
    ]
    for value,source,kind in good:
        assert accepted(value,source,kind), value


def test_reject_common_class_engine_tokens_but_keep_ui():
    for s in ("amission","aplayer","caction","csprite","xmoveto","trigger","cost[","/scene/","VolumeControl"):
        assert not accepted(s,"af.class","class-string"), s
    for s in ("choose","equip","item","map","shop","continue","pause","stage"):
        assert accepted(s,"af.class","class-string"), s


def test_keep_cjk_class_strings():
    for s in ("存档成功","已经升级到满级","领悟","关闭声音","逃跑失败"):
        assert accepted(s,"z.class","class-string"), s
