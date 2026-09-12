from core.binary_resource_analyzer import _decode, _whole_record_patch_safe, scan_null_terminated
from core.encoding_utils import decode_mixed_utf8_binary


def test_mixed_utf8_islands_recover_chinese_and_preserve_raw_bytes():
    raw = b'\x0e\x06\x15' + '武神煌日术心法,可大幅度提升攻击威力，65级可用.'.encode('utf-8') + b'\xe0'
    text, recovered = decode_mixed_utf8_binary(raw)
    assert recovered
    assert '武神煌日术心法' in text
    assert '攻击威力' in text
    assert text.startswith('\x0e\x06\x15')
    assert text.endswith('\xe0')


def test_binary_decoder_uses_mixed_utf8_instead_of_mojibake():
    raw = b'\x1b\x01\x09' + '益神丹'.encode('utf-8') + b'\x18' + '全体恢复灵力300点'.encode('utf-8') + b'\x01\x90'
    text, enc = _decode(raw)
    assert enc == 'mixed-utf8-binary'
    assert '益神丹' in text
    assert '全体恢复灵力300点' in text
    assert 'ç' not in text and 'å' not in text


def test_mixed_record_is_discovery_only_not_whole_record_patch_safe():
    raw = b'\x05\x03\x0f' + '九转还魂丹'.encode('utf-8') + b'\x0c' + '全体复活'.encode('utf-8')
    text, enc = _decode(raw)
    assert '九转还魂丹' in text
    assert not _whole_record_patch_safe(raw, enc)


def test_plain_utf8_framed_text_remains_safe():
    raw = '确定'.encode('utf-8')
    text, enc = _decode(raw)
    assert text == '确定'
    assert _whole_record_patch_safe(raw, enc)


def test_null_terminated_mixed_record_is_marked_unsafe():
    raw = b'\x05\x03\x0f' + '九转还魂丹'.encode('utf-8') + b'\x0c' + '全体复活'.encode('utf-8') + b'\x00'
    items = scan_null_terminated(raw)
    assert items
    assert items[0].text.find('九转还魂丹') >= 0
    assert items[0].patch_safe is False
