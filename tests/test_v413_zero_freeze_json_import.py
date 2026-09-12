from pathlib import Path


def _source():
    return (Path(__file__).parents[1] / 'gui' / 'main_window.py').read_text(encoding='utf-8')


def test_import_finish_does_not_rebuild_table():
    s=_source()
    a=s.index('    def _json_import_finished')
    b=s.index('    def _json_import_failed', a)
    block=s[a:b]
    assert 'self.refresh_strings()' not in block
    assert '_continue_import_ui_apply' in block


def test_import_ui_updates_are_chunked():
    s=_source()
    a=s.index('    def _continue_import_ui_apply')
    b=s.index('    def _json_import_failed', a)
    block=s[a:b]
    assert '[:32]' in block
    assert 'QTimer.singleShot(0,self._continue_import_ui_apply)' in block


def test_autosave_file_write_is_off_gui_thread():
    s=_source()
    assert 'class AutosaveWorker(QThread)' in s
    a=s.index('    def perform_autosave')
    b=s.index('    def check_recovery_snapshot', a)
    block=s[a:b]
    assert 'AutosaveWorker' in block
    assert 'json.dump(' not in block
