from pathlib import Path


def test_cumulative_ui_preview_contract_without_importing_qt():
    root = Path("gui/cumulative_ui_polish_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/cumulative_ui_polish_hook.py").read_text(encoding="utf-8")

    assert root == portable
    for text in (root, portable):
        assert 'f"{APP_NAME} v{APP_VERSION}-cumulative (Portable)"' in text
        assert 'label.setText("Diagnostics Center")' in text
        assert 'label.setText("v4.31 cumulative")' in text
        assert 'layout.insertWidget(max(0, build_index), nav, 0)' in text
        assert 'layout.insertWidget(max(0, build_index), patch, 0)' in text
        assert '#ECFDF5' in text
        assert 'Phiên bản {APP_VERSION}-cumulative (v431)' in text


def test_portable_bootstrap_installs_polish_after_patch_ui():
    text = Path("app/bootstrap.py").read_text(encoding="utf-8")
    patch_pos = text.index("install_patch_update_ui(MainWindow)")
    polish_pos = text.index("install_cumulative_ui_polish(MainWindow)")
    assert polish_pos > patch_pos
