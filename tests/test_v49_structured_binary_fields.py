from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.binary_resource_patcher import patch_binary_entry


def test_nested_u8_fields_win_over_outer_record():
    # Mirrors item.bin style records: metadata + [u8 byte length][UTF-8 text]
    # + [u8 byte length][UTF-8 text] + trailing metadata, all inside an outer
    # null-terminated record.
    a='九转还魂丹'.encode('utf-8')
    b='全体复活'.encode('utf-8')
    record=b'\x05\x03'+bytes([len(a)])+a+bytes([len(b)])+b+b'\x00'
    an=BinaryResourceAnalyzer().analyze('item.bin',record)
    safe=[s for s in an.strings if s.patch_safe]
    assert [s.text for s in safe]==['九转还魂丹','全体复活']
    assert all(s.framing=='u8-length-prefixed' for s in safe)
    assert not any(s.framing=='null-terminated' and s.patch_safe for s in an.strings)


def test_patch_updates_inner_length_only():
    a='九转还魂丹'.encode('utf-8')
    b='全体复活'.encode('utf-8')
    record=b'\x05\x03'+bytes([len(a)])+a+bytes([len(b)])+b+b'\x00'
    an=BinaryResourceAnalyzer().analyze('item.bin',record)
    target=next(s for s in an.strings if s.text=='九转还魂丹')
    patched=patch_binary_entry(record,target,'Cửu Chuyển Hoàn Hồn Đan')
    vi='Cửu Chuyển Hoàn Hồn Đan'.encode('utf-8')
    assert patched[target.length_field_offset]==len(vi)
    assert patched[target.length_field_offset+1:target.length_field_offset+1+len(vi)]==vi
    # Metadata before the field survives.
    assert patched[:2]==b'\x05\x03'


def test_random_legacy_decodes_never_become_safe():
    # A legacy decoder can map arbitrary high bytes to characters; such matches
    # must remain discovery-only because Vietnamese replacement is UTF-8.
    data=bytes([8])+bytes([0xD6,0xD0,0xCE,0xC4,0xB2,0xE2,0xCA,0xD4])
    an=BinaryResourceAnalyzer().analyze('cfg.bin',data)
    assert all(not s.patch_safe for s in an.strings)


def test_end_to_end_builder_nested_fields(tmp_path):
    import zipfile
    from core.jar_scanner import JarScanner
    from core.translation_project import TranslationProject
    from core.jar_builder import JarBuilder

    a='九转还魂丹'.encode('utf-8')
    b='全体复活'.encode('utf-8')
    record=b'\x05\x03'+bytes([len(a)])+a+bytes([len(b)])+b+b'\x00'
    src=tmp_path/'game.jar'
    out=tmp_path/'game_vi.jar'
    with zipfile.ZipFile(src,'w') as z:
        z.writestr('item.bin',record)

    result=JarScanner().scan(str(src))
    strings=[s for _,s in result.all_strings() if s.source=='item.bin']
    first=next(s for s in strings if s.value=='九转还魂丹' and s.kind.endswith(':safe'))
    second=next(s for s in strings if s.value=='全体复活' and s.kind.endswith(':safe'))
    project=TranslationProject(jar_path=str(src))
    project.set(first.key,'Cửu Chuyển Hoàn Hồn Đan')
    project.set(second.key,'Hồi sinh toàn đội')
    report=JarBuilder().build(result,project,str(out))
    assert report.failed==0
    assert report.patched==2
    assert report.validation_ok
    assert report.regression_ok
    with zipfile.ZipFile(out,'r') as z:
        blob=z.read('item.bin')
    assert 'Cửu Chuyển Hoàn Hồn Đan'.encode('utf-8') in blob
    assert 'Hồi sinh toàn đội'.encode('utf-8') in blob
