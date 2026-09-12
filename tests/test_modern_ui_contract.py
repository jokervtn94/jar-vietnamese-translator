from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_modern_ui_contract_matches_reference_layout():
    main=(ROOT/"gui"/"main_window.py").read_text(encoding="utf-8")
    theme=(ROOT/"gui"/"fluent_theme.py").read_text(encoding="utf-8")
    widgets=(ROOT/"gui"/"fluent_widgets.py").read_text(encoding="utf-8")
    assert 'APP_NAME = "JAR Vietnamese Translator"' in main
    assert 'self.setWindowTitle(self.APP_NAME)' in main
    assert 'Nạp & Phân tích' in main
    assert 'Dịch thuật & Biên tập' in main
    assert 'Kiểm tra' in main
    assert 'Xuất bản' in main
    assert 'QTableWidget(0, 5)' in main
    assert '["#", "Trạng thái", "Chuỗi gốc (Original)", "Bản dịch (Vietnamese)", "Nguồn"]' in main
    assert 'workspace.setStretchFactor(0, 20)' in main
    assert 'workspace.setStretchFactor(1, 50)' in main
    assert 'workspace.setStretchFactor(2, 30)' in main
    assert 'self.setStyleSheet(load_fluent_light_theme())' in main
    assert 'class WorkflowStep(QFrame)' in widgets
    assert 'class StatusBadgeDelegate(QStyledItemDelegate)' in widgets
    assert '#F5F7FA' in theme
    assert '#FFFFFF' in theme
    assert '#E60073' in theme
    assert 'QScrollBar:vertical' in theme
    assert 'QComboBox QAbstractItemView' in theme
    assert 'JAR Vietnamese Translator V4.13' not in main
    assert 'JAR Vietnamese Translator V4.14' not in main


def test_instant_jar_preview_is_preserved():
    text=(ROOT/"gui"/"main_window.py").read_text(encoding="utf-8")
    assert 'entries = self._preview_jar_structure(path)' in text
    assert 'self.worker = ScanWorker(path)' in text
    assert 'self.worker.start()' in text
    assert 'Đã nạp cấu trúc JAR. Đang quét ngôn ngữ ở nền…' in text


def test_theme_is_framework_native_and_engine_independent():
    req=(ROOT/"requirements.txt").read_text(encoding="utf-8")
    main=(ROOT/"gui"/"main_window.py").read_text(encoding="utf-8")
    assert 'PySide6' in req
    assert 'PyQt6' not in req
    assert 'qdarkstyle' not in req.lower()
    assert 'from gui.fluent_theme import load_fluent_light_theme' in main


def test_light_monokai_theme_contract():
    from gui.fluent_theme import MONOKAI_LIGHT_QSS, load_fluent_light_theme
    qss = load_fluent_light_theme()
    assert qss == MONOKAI_LIGHT_QSS
    assert "#F5F7FA" in qss
    assert "#E60073" in qss
    assert "ExplorerPanel" in qss
    assert "#18C98A" not in qss  # status badge color is painted by the delegate, not QSS
