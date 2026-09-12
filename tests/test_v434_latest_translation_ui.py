from pathlib import Path


def test_latest_translation_ui_contract_without_importing_qt():
    root = Path("gui/latest_translation_ui_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/latest_translation_ui_hook.py").read_text(encoding="utf-8")

    assert root == portable
    for text in (root, portable):
        assert '"jar": "#2563EB"' in text
        assert '"folder": "#E0A100"' in text
        assert '"class": "#7C3AED"' in text
        assert '"text": "#0F9D58"' in text
        assert '"binary": "#D97706"' in text
        assert '"image": "#E11D48"' in text
        assert '"audio": "#0891B2"' in text
        assert 'self.findChild(QFrame, "SuggestionCard")' in text
        assert 'self.suggestion_text = None' in text
        assert 'label.setText("Thông tin chuỗi")' in text
        assert 'widget.setWordWrap(True)' in text
        assert 'Qt.TextSelectableByMouse' in text
        assert 'grid.setColumnStretch(1, 1)' in text
        assert '_decorate_tree(self.tree)' in text
        assert 'widget.setToolTip(widget.text())' in text


def test_portable_bootstrap_installs_latest_translation_ui_last():
    text = Path("app/bootstrap.py").read_text(encoding="utf-8")
    polish_pos = text.index("install_cumulative_ui_polish(MainWindow)")
    latest_pos = text.index("install_latest_translation_ui(MainWindow)")
    assert latest_pos > polish_pos
