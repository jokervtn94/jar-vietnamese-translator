from types import SimpleNamespace

from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.jar_builder import JarBuilder, BuildReport


def _s(kind, index, value, source='item.bin'):
    return SimpleNamespace(kind=kind, index=index, value=value, source=source)


def test_direct_verify_accepts_variable_length_u8_fields_without_rescan_dependency():
    a='九转还魂丹'.encode('utf-8')
    b='全体复活'.encode('utf-8')
    raw=bytes([len(a)])+a+bytes([len(b)])+b
    analysis=BinaryResourceAnalyzer().analyze('item.bin', raw)
    found={(x.text,x.framing):x for x in analysis.strings if x.patch_safe}
    assert ('九转还魂丹','u8-length-prefixed') in found
    assert ('全体复活','u8-length-prefixed') in found

    patches=[
        (_s('binary:u8-length-prefixed:safe', found[('九转还魂丹','u8-length-prefixed')].offset, '九转还魂丹'), 'Cửu Chuyển Hoàn Hồn Đan'),
        (_s('binary:u8-length-prefixed:safe', found[('全体复活','u8-length-prefixed')].offset, '全体复活'), 'Hồi sinh toàn đội'),
    ]
    report=BuildReport('in.jar','out.jar')
    out=JarBuilder()._patch_binary('item.bin', raw, patches, report)
    assert out != raw
    assert report.failed == 0
    assert report.patched == 2
    assert b'C\xe1\xbb\xadu Chuy\xe1\xbb\x83n Ho\xc3\xa0n H\xe1\xbb\x93n \xc4\x90an' in out
    assert 'Hồi sinh toàn đội'.encode('utf-8') in out


def test_direct_verify_rejects_corrupted_length_prefix():
    # Validate helper itself catches a real framing error.
    text='九转还魂丹'.encode('utf-8')
    raw=bytes([len(text)])+text
    item=[x for x in BinaryResourceAnalyzer().analyze('item.bin',raw).strings if x.patch_safe][0]
    vi='Cửu Chuyển Hoàn Hồn Đan'
    prepared=[(item, _s('binary:u8-length-prefixed:safe', item.offset, item.text), vi)]
    enc=vi.encode('utf-8')
    broken=bytes([len(enc)-1])+enc
    failures=JarBuilder._verify_binary_transaction(broken, prepared)
    assert failures and 'length mismatch' in failures[0]
