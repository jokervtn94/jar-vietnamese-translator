from models.data import ExtractedString
from core.structured_game_resource import (
    Src4ResourceAnalyzer,
    embedded_gif_regions,
    exclude_embedded_media,
    pack_src4_record,
    patch_src4_translations,
    rebuild_src4,
    scan_java_utf_u16be,
    split_src4_records,
    decompress_src4_record,
    src4_translation_present,
)


def _java_utf(text):
    raw=text.encode("utf-8")
    return len(raw).to_bytes(2,"big")+raw


def test_src4_scan_and_roundtrip_patch_preserves_records_1_to_3():
    r1=b"meta-one"
    r2=b"meta-two"
    r3=b"meta-three"
    d4=b"\x01\x02"+_java_utf("村民: 你好!")+b"\x03"
    d5=b"\x04"+_java_utf("李逍遥")+b"\x05"+_java_utf("赵灵儿: 我们走吧!")+b"\x06"
    original=rebuild_src4([r1,r2,r3,pack_src4_record(d4),pack_src4_record(d5)])

    scan=Src4ResourceAnalyzer().scan("src/1.src4",original)
    values={x.value:x for x in scan.strings}
    assert "村民: 你好!" in values
    assert "李逍遥" in values
    assert "赵灵儿: 我们走吧!" in values

    patched=patch_src4_translations(original,[
        (values["村民: 你好!"],"Dân làng: Xin chào!"),
        (values["李逍遥"],"Lý Tiêu Dao"),
    ])
    before=split_src4_records(original)
    after=split_src4_records(patched)
    assert after[:3] == before[:3]
    assert decompress_src4_record(after[3]) != d4
    assert decompress_src4_record(after[4]) != d5
    assert src4_translation_present(patched,4,"Dân làng: Xin chào!")
    assert src4_translation_present(patched,5,"Lý Tiêu Dao")


def test_java_utf_u16be_keeps_one_character_cjk():
    data=b"\x99"+_java_utf("酒")+b"\x88"
    found=scan_java_utf_u16be("data.pak",data)
    assert len(found)==1
    assert found[0].value=="酒"
    assert found[0].index==3
    assert found[0].kind=="binary:u16be-length-prefixed:safe"


def test_embedded_gif_candidates_are_excluded():
    # 1x1 GIF89a: header + logical screen + GCT + image + trailer.
    gif=(
        b"GIF89a"
        b"\x01\x00\x01\x00\x80\x00\x00"
        b"\x00\x00\x00\xff\xff\xff"
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02\x44\x01\x00"
        b"\x3b"
    )
    data=b"HEAD"+gif+b"TAIL"
    regions=embedded_gif_regions(data)
    assert regions == [(4,4+len(gif))]
    fake=ExtractedString("image.pak","L罁","binary:null-terminated:safe",10,"utf-8")
    real=ExtractedString("image.pak","菜单","binary:u16be-length-prefixed:safe",1,"utf-8")
    kept,removed=exclude_embedded_media([fake,real],data)
    assert removed==1
    assert kept==[real]
