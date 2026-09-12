from pathlib import Path
import json
import zipfile
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect, QPoint
from PySide6.QtGui import QColor, QBrush, QKeySequence, QShortcut, QFont, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QMessageBox, QHeaderView, QStatusBar, QTextEdit, QLineEdit,
    QComboBox, QAbstractItemView, QProgressBar, QCheckBox, QFrame, QGroupBox,
    QGridLayout, QScrollArea, QLayout, QSizePolicy, QMenu
)
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.jar_builder import JarBuilder
from core.binary_resource_analyzer import BinaryResourceAnalyzer
from core.compatibility_analyzer import CompatibilityAnalyzer
from core.glyph_analyzer import GlyphAnalyzer
from core.build_readiness import BuildReadinessAnalyzer
from core.regression_validator import RegressionValidator
from core.runtime_test_packager import RuntimeTestPackager
from core.runtime_log_analyzer import RuntimeLogAnalyzer
from core.translation_exchange import TranslationExchange
from gui.fluent_theme import load_fluent_light_theme
from gui.fluent_widgets import WorkflowStep, StatusBadgeDelegate
from gui.task_progress_dialog import BuildTaskDialog


class ScanWorker(QThread):
    finished_result = Signal(object)
    partial_result = Signal(object)
    progress = Signal(int, str)
    failed = Signal(str)

    def __init__(self, path, force_deep=False):
        super().__init__()
        self.path = path
        self.force_deep = force_deep

    def _progress(self, _stage, current, total, message):
        pct = int((current / max(1, total)) * 100)
        self.progress.emit(pct, message)

    def run(self):
        try:
            # Fast pass first: class constants + known text/binary resources only.
            fast = JarScanner(deep_scan=False).scan(self.path, progress=self._progress)
            self.partial_result.emit(fast)
            fast_count = sum(len(c.strings) for c in fast.candidates)
            # Deep scan is expensive and often produces huge noise on .img/.map/.sce.
            # Run it automatically only when the fast pass found almost nothing, or
            # when the user explicitly requested a deep re-scan.
            if self.force_deep or fast_count < 5:
                self.progress.emit(0, "Fast scan ít kết quả; đang chuyển sang Deep Scan…")
                full = JarScanner(deep_scan=True).scan(self.path, progress=self._progress)
                self.finished_result.emit(full)
            else:
                fast.diagnostics["scan_mode"] = "fast-adaptive"
                fast.diagnostics["deep_scan_skipped"] = True
                self.finished_result.emit(fast)
        except Exception as e:
            self.failed.emit(str(e))


class JsonImportWorker(QThread):
    finished_import = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path, result, existing_translations, overwrite):
        super().__init__()
        self.path = path
        self.result = result
        self.existing_translations = dict(existing_translations)
        self.overwrite = overwrite

    def run(self):
        try:
            report, updates = TranslationExchange().prepare_import_file(
                self.path, self.result, self.existing_translations, self.overwrite
            )
            self.finished_import.emit(report, updates)
        except Exception as e:
            self.failed.emit(str(e))




class AutosaveWorker(QThread):
    finished_save = Signal(str)
    failed = Signal(str)

    def __init__(self, path, payload):
        super().__init__()
        self.path = path
        self.payload = payload

    def run(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.payload, f, ensure_ascii=False, indent=2)
            self.finished_save.emit(self.path)
        except Exception as e:
            self.failed.emit(str(e))


class BuildPreflightWorker(QThread):
    finished_preflight = Signal(object)
    progress = Signal(int, str, str, str)
    failed = Signal(str)

    def __init__(self, result, project):
        super().__init__()
        self.result = result
        self.project = project

    def run(self):
        try:
            blocked = []
            warnings = []
            self.progress.emit(3, "preflight", "Kiểm tra điều kiện build…", "info")
            ready = BuildReadinessAnalyzer().analyze(self.result, self.project)
            blocked.extend(i.message for i in ready.issues if i.level == "BLOCKED")
            warnings.extend(i.message for i in ready.issues if i.level == "WARNING")
            self.progress.emit(8, "preflight", "Kiểm tra điều kiện build hoàn tất", "success")

            self.progress.emit(10, "glyph", "Kiểm tra font / glyph tiếng Việt…", "info")
            try:
                glyph = GlyphAnalyzer().analyze(self.result.jar_path, self.result, self.project)
                if glyph.maps and glyph.missing_chars:
                    chars = " ".join(sorted(glyph.missing_chars, key=lambda c: ord(c)))
                    if len(chars) > 220:
                        chars = chars[:220] + "..."
                    warnings.append(f"Font/Glyph: thiếu {len(glyph.missing_chars)} ký tự trong font map: {chars}")
                    self.progress.emit(13, "glyph", f"Glyph: thiếu {len(glyph.missing_chars)} ký tự", "warning")
                else:
                    self.progress.emit(13, "glyph", "Kiểm tra glyph hoàn tất", "success")
            except Exception as e:
                warnings.append(f"Glyph preflight không chạy được: {e}")
                self.progress.emit(13, "glyph", f"Glyph warning: {e}", "warning")

            self.progress.emit(15, "compat", "Kiểm tra tương thích runtime…", "info")
            try:
                compat = CompatibilityAnalyzer().analyze(self.result.jar_path, self.result, self.project)
                if compat.overall_risk == "high":
                    warnings.append("Compatibility: mức rủi ro HIGH (custom/bitmap font hoặc encoding có thể không hỗ trợ đủ tiếng Việt).")
                    self.progress.emit(19, "compat", "Compatibility risk: HIGH", "warning")
                else:
                    self.progress.emit(19, "compat", f"Compatibility risk: {compat.overall_risk}", "success")
            except Exception as e:
                warnings.append(f"Compatibility preflight không chạy được: {e}")
                self.progress.emit(19, "compat", f"Compatibility warning: {e}", "warning")

            self.finished_preflight.emit({
                "blocked": blocked,
                "warnings": warnings,
                "status": getattr(ready, "status", "UNKNOWN"),
            })
        except Exception as e:
            self.failed.emit(str(e))


class BuildWorker(QThread):
    finished_build = Signal(object, str)
    progress = Signal(int, str, str, str)
    failed = Signal(str)

    def __init__(self, result, project, output_path):
        super().__init__()
        self.result = result
        self.project = project
        self.output_path = output_path

    def _progress(self, percent, stage, message):
        # Builder reports 0..100 for the actual rebuild. Map it to 20..100
        # because 0..20 is reserved for preflight in the UI.
        mapped = 20 + int(max(0, min(100, percent)) * 0.80)
        self.progress.emit(mapped, stage, message, "info")

    def run(self):
        try:
            report = JarBuilder().build(self.result, self.project, self.output_path, progress=self._progress)
            report_path = str(Path(self.output_path).with_suffix(".build-report.json"))
            report.save_json(report_path)
            self.finished_build.emit(report, report_path)
        except Exception as e:
            self.failed.emit(str(e))


class FlowLayout(QLayout):
    """Responsive wrapping layout for toolbar/action buttons."""
    def __init__(self, parent=None, margin=0, hspacing=4, vspacing=4):
        super().__init__(parent)
        self._items=[]
        self._hspacing=hspacing
        self._vspacing=vspacing
        self.setContentsMargins(margin,margin,margin,margin)

    def addItem(self,item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self,index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self,index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self,width):
        return self._do_layout(QRect(0,0,width,0),True)

    def setGeometry(self,rect):
        super().setGeometry(rect)
        self._do_layout(rect,False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size=QSize()
        for item in self._items:
            size=size.expandedTo(item.minimumSize())
        l,t,r,b=self.getContentsMargins()
        return size+QSize(l+r,t+b)

    def _do_layout(self,rect,test_only):
        x=rect.x()
        y=rect.y()
        line_height=0
        right=rect.right()
        for item in self._items:
            w=item.widget()
            if w is not None and not w.isVisible():
                continue
            hint=item.sizeHint()
            next_x=x+hint.width()+self._hspacing
            if next_x-self._hspacing > right and line_height>0:
                x=rect.x()
                y=y+line_height+self._vspacing
                next_x=x+hint.width()+self._hspacing
                line_height=0
            if not test_only:
                item.setGeometry(QRect(QPoint(x,y),hint))
            x=next_x
            line_height=max(line_height,hint.height())
        return y+line_height-rect.y()


class MainWindow(QMainWindow):
    APP_NAME = "JAR Vietnamese Translator"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.APP_NAME)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        screen = self.screen().availableGeometry() if self.screen() else QRect(0,0,1366,768)
        self.resize(min(1536, int(screen.width()*0.96)), min(960, int(screen.height()*0.94)))
        self.setMinimumSize(980, 620)
        self.setAcceptDrops(True)

        self.result = None
        self.worker = None
        self.project = TranslationProject()
        self.current_candidate = None
        self.visible_strings = []
        self._updating_table = False
        self.translation_exchange = TranslationExchange()
        self._json_import_ui_queue = []
        self._json_import_report = None
        self._json_import_updates = {}
        self._autosave_worker = None
        # Worker references are released only from QThread.finished. Clearing them
        # here can destroy a QThread while its run() method is still returning.
        self._pending_build_path = ""
        self._build_in_progress = False
        self._build_dialog = None
        self._scan_started_at = 0.0

        # Presentation is centralized so the UI can evolve without touching scan/build logic.
        self.setStyleSheet(load_fluent_light_theme())

        central = QWidget()
        self.setCentralWidget(central)
        page = QVBoxLayout(central)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        # App title bar: same visual language as the approved preview while keeping
        # reliable custom-window controls on Windows.
        appbar = QFrame(); appbar.setObjectName("AppBar"); appbar.setFixedHeight(58)
        app_l = QHBoxLayout(appbar); app_l.setContentsMargins(20, 8, 12, 8); app_l.setSpacing(10)
        mark = QLabel("J"); mark.setObjectName("AppMark")
        self.app_title = QLabel(self.APP_NAME); self.app_title.setObjectName("AppTitle")
        title_stack = QVBoxLayout(); title_stack.setContentsMargins(0,0,0,0); title_stack.setSpacing(0)
        title_stack.addWidget(self.app_title)
        self.app_subtitle = QLabel("Dịch và rebuild game Java/J2ME theo quy trình an toàn"); self.app_subtitle.setObjectName("AppSubtitle")
        title_stack.addWidget(self.app_subtitle)
        app_l.addWidget(mark); app_l.addLayout(title_stack); app_l.addStretch()
        self.theme_btn = QPushButton("☀"); self.theme_btn.setObjectName("ThemeButton"); self.theme_btn.setFixedSize(34, 32); self.theme_btn.setToolTip("Giao diện sáng")
        self.settings_btn = QPushButton("⋮"); self.settings_btn.setObjectName("IconButton"); self.settings_btn.setFixedSize(34, 32)
        self.min_btn = QPushButton("—"); self.min_btn.setObjectName("WindowButton"); self.min_btn.setFixedSize(38, 32)
        self.max_btn = QPushButton("□"); self.max_btn.setObjectName("WindowButton"); self.max_btn.setFixedSize(38, 32)
        self.close_btn = QPushButton("×"); self.close_btn.setObjectName("CloseButton"); self.close_btn.setFixedSize(38, 32)
        app_l.addWidget(self.theme_btn); app_l.addWidget(self.settings_btn); app_l.addWidget(self.min_btn); app_l.addWidget(self.max_btn); app_l.addWidget(self.close_btn)
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self._toggle_maximize)
        self.close_btn.clicked.connect(self.close)
        self._drag_pos = None
        appbar.mousePressEvent = self._title_mouse_press
        appbar.mouseMoveEvent = self._title_mouse_move
        appbar.mouseReleaseEvent = self._title_mouse_release
        page.addWidget(appbar)

        # Functional buttons are retained as controller endpoints; the clean stepper menus
        # trigger the same actions instead of exposing a crowded toolbar.
        self.open_btn = QPushButton(); self.open_btn.hide()
        self.scan_btn = QPushButton(); self.scan_btn.setEnabled(False); self.scan_btn.hide()
        self.binary_btn = QPushButton(); self.binary_btn.setEnabled(False); self.binary_btn.hide()
        self.import_csv_btn = QPushButton(); self.import_csv_btn.setEnabled(False); self.import_csv_btn.hide()
        self.export_csv_btn = QPushButton(); self.export_csv_btn.setEnabled(False); self.export_csv_btn.hide()
        self.import_json_btn = QPushButton(); self.import_json_btn.setEnabled(False); self.import_json_btn.hide()
        self.export_json_btn = QPushButton(); self.export_json_btn.setEnabled(False); self.export_json_btn.hide()
        self.glyph_btn = QPushButton(); self.glyph_btn.setEnabled(False); self.glyph_btn.hide()
        self.readiness_btn = QPushButton(); self.readiness_btn.setEnabled(False); self.readiness_btn.hide()
        self.log_btn = QPushButton(); self.log_btn.setEnabled(False); self.log_btn.hide()
        self.compat_btn = QPushButton(); self.compat_btn.setEnabled(False); self.compat_btn.hide()
        self.report_btn = QPushButton(); self.report_btn.setEnabled(False); self.report_btn.hide()
        self.regression_btn = QPushButton(); self.regression_btn.setEnabled(False); self.regression_btn.hide()
        self.runtime_btn = QPushButton(); self.runtime_btn.setEnabled(False); self.runtime_btn.hide()
        self.save_project_btn = QPushButton(); self.save_project_btn.setEnabled(False); self.save_project_btn.hide()
        self.open_project_btn = QPushButton(); self.open_project_btn.hide()

        # 1. Header stepper based directly on the supplied PyQt6 reference layout.
        header = QFrame(); header.setObjectName("HeaderFrame"); header.setFixedHeight(86)
        header_l = QHBoxLayout(header); header_l.setContentsMargins(20, 9, 18, 9); header_l.setSpacing(12)
        self.workflow_actions = {}

        def add_step(number, title, subtitle, actions, active=False):
            step = WorkflowStep(number, title, subtitle, header, active=active)
            step.set_actions(actions, self, self.workflow_actions)
            header_l.addWidget(step, 1)
            return step

        add_step(1, "Nạp & Phân tích", "Mở JAR · Quét · Phân tích", [
            ("open", "Mở JAR", self.open_jar, True),
            ("scan", "Quét lại ngôn ngữ", lambda: self.open_jar(self.result.jar_path) if self.result else None, False),
            ("binary", "Phân tích Binary", self.analyze_selected_binary, False),
        ], True)
        a1 = QLabel("›"); a1.setObjectName("StepArrow"); header_l.addWidget(a1)
        add_step(2, "Dịch thuật & Biên tập", "CSV · JSON", [
            ("import_csv", "Nhập CSV", self.import_csv, False),
            ("export_csv", "Xuất CSV", self.export_csv, False),
            ("import_json", "Nhập JSON", self.import_translation_json, False),
            ("export_json", "Xuất JSON", self.export_translation_json, False),
        ])
        a2 = QLabel("›"); a2.setObjectName("StepArrow"); header_l.addWidget(a2)
        add_step(3, "Kiểm tra", "Glyph · Build · Log", [
            ("glyph", "Kiểm tra Glyph", self.analyze_glyphs, False),
            ("readiness", "Kiểm tra Build", self.show_build_readiness, False),
            ("log", "Phân tích Log", self.analyze_runtime_log, False),
        ])
        a3 = QLabel("›"); a3.setObjectName("StepArrow"); header_l.addWidget(a3)
        add_step(4, "Xuất bản", "Tạo file JAR hoàn chỉnh", [])
        header_l.addSpacing(6)
        self.build_jar_btn = QPushButton("Build JAR"); self.build_jar_btn.setObjectName("BuildBtn")
        self.build_jar_btn.setFixedHeight(42); self.build_jar_btn.setEnabled(False)
        header_l.addWidget(self.build_jar_btn, 0, Qt.AlignVCenter)
        page.addWidget(header)

        tools_menu = QMenu(self)
        act_encoding = QAction("Encoding / Font", self); act_encoding.triggered.connect(self.analyze_compatibility)
        act_report = QAction("Báo cáo build", self); act_report.triggered.connect(self.show_build_report)
        act_save = QAction("Lưu project", self); act_save.triggered.connect(self.save_project)
        act_open = QAction("Mở project", self); act_open.triggered.connect(self.open_project)
        act_help = QAction("Hướng dẫn JSON", self); act_help.triggered.connect(self.show_json_exchange_help)
        act_about = QAction("Giới thiệu", self); act_about.triggered.connect(lambda: QMessageBox.information(self, "Giới thiệu", self.APP_NAME))
        for a in (act_encoding, act_report, act_save, act_open): tools_menu.addAction(a)
        tools_menu.addSeparator(); tools_menu.addAction(act_help); tools_menu.addAction(act_about)
        self.settings_btn.setMenu(tools_menu)

        # 2. Three-column workspace matching the supplied UI reference.
        workspace_wrap = QWidget()
        work_l = QHBoxLayout(workspace_wrap); work_l.setContentsMargins(12, 12, 12, 12); work_l.setSpacing(0)
        workspace = QSplitter(Qt.Horizontal); self.workspace = workspace; workspace.setChildrenCollapsible(False)
        work_l.addWidget(workspace)

        # Left panel: archive explorer.
        left_panel = QFrame(); left_panel.setObjectName("ExplorerPanel"); self.left_box = left_panel
        ll = QVBoxLayout(left_panel); ll.setContentsMargins(12, 12, 12, 12); ll.setSpacing(8)
        lt = QLabel("Cấu trúc file JAR"); lt.setObjectName("PanelTitle"); ll.addWidget(lt)
        self.file_search = QLineEdit(); self.file_search.setPlaceholderText("⌕  Tìm file..."); self.file_search.setClearButtonEnabled(True)
        ll.addWidget(self.file_search)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.setIndentation(18)
        ll.addWidget(self.tree, 1)
        workspace.addWidget(left_panel)

        # Center panel: title, filters, two-column translation relationship + status/source context.
        center_panel = QFrame(); center_panel.setObjectName("Panel"); self.center_box = center_panel
        cl = QVBoxLayout(center_panel); cl.setContentsMargins(12, 12, 12, 12); cl.setSpacing(8)
        tr = QHBoxLayout(); tr.setContentsMargins(0,0,0,0)
        self.center_title = QLabel("Chuỗi ngôn ngữ (0)"); self.center_title.setObjectName("PanelTitle")
        tr.addWidget(self.center_title); tr.addStretch(); cl.addLayout(tr)
        fr = QHBoxLayout(); fr.setSpacing(8)
        self.search_box = QLineEdit(); self.search_box.setPlaceholderText("⌕  Tìm trong chuỗi..."); self.search_box.setClearButtonEnabled(True)
        self.source_filter = QComboBox(); self.source_filter.addItem("Tất cả nguồn")
        self.status_filter = QComboBox(); self.status_filter.addItems(["Tất cả trạng thái", "Đã dịch", "Cần kiểm tra", "Chưa dịch"])
        self.filter_btn = QPushButton("≡"); self.filter_btn.setObjectName("IconButton"); self.filter_btn.setFixedWidth(38)
        fr.addWidget(self.search_box, 2); fr.addWidget(self.source_filter, 1); fr.addWidget(self.status_filter, 1); fr.addWidget(self.filter_btn)
        cl.addLayout(fr)

        self.strings = QTableWidget(0, 5)
        self.strings.setHorizontalHeaderLabels(["#", "Trạng thái", "Chuỗi gốc (Original)", "Bản dịch (Vietnamese)", "Nguồn"])
        self.strings.setSelectionBehavior(QAbstractItemView.SelectRows); self.strings.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.strings.setAlternatingRowColors(True); self.strings.setWordWrap(False); self.strings.setShowGrid(False)
        self.strings.setItemDelegateForColumn(1, StatusBadgeDelegate(self.strings))
        self.strings.verticalHeader().setVisible(False); self.strings.verticalHeader().setDefaultSectionSize(34)
        hh = self.strings.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.strings.setColumnWidth(0, 42); self.strings.setColumnWidth(1, 92); self.strings.setColumnWidth(4, 90)
        cl.addWidget(self.strings, 1)
        workspace.addWidget(center_panel)

        # Right panel: detailed editor and metadata.
        right_panel = QFrame(); right_panel.setObjectName("Panel"); self.right_panel = right_panel
        rp = QVBoxLayout(right_panel); rp.setContentsMargins(12, 12, 12, 12); rp.setSpacing(9)
        ihr = QHBoxLayout(); ihr.setSpacing(5)
        it = QLabel("Chỉnh sửa chuỗi"); it.setObjectName("PanelTitle")
        self.prev_string_btn = QPushButton("‹"); self.prev_string_btn.setObjectName("IconButton"); self.prev_string_btn.setFixedSize(28, 28)
        self.next_string_btn = QPushButton("›"); self.next_string_btn.setObjectName("IconButton"); self.next_string_btn.setFixedSize(28, 28)
        self.inspector_count = QLabel("0 / 0"); self.inspector_count.setObjectName("InspectorCount")
        ihr.addWidget(it); ihr.addStretch(); ihr.addWidget(self.prev_string_btn); ihr.addWidget(self.next_string_btn); ihr.addWidget(self.inspector_count)
        rp.addLayout(ihr)

        ol = QLabel("Chuỗi gốc (Original)"); ol.setObjectName("Muted"); rp.addWidget(ol)
        self.original_edit = QTextEdit(); self.original_edit.setReadOnly(True); self.original_edit.setMinimumHeight(70); self.original_edit.setMaximumHeight(105)
        self.original_edit.setFont(QFont("Consolas", 10)); rp.addWidget(self.original_edit)
        self.original_meta = QLabel("Số ký tự: 0  |  Bytes: 0 (UTF-8)"); self.original_meta.setObjectName("Muted"); rp.addWidget(self.original_meta)

        tl = QLabel("Bản dịch (Vietnamese)"); tl.setObjectName("Muted"); rp.addWidget(tl)
        self.translation_edit = QTextEdit(); self.translation_edit.setMinimumHeight(82); self.translation_edit.setMaximumHeight(120)
        self.translation_edit.setFont(QFont("Consolas", 10)); rp.addWidget(self.translation_edit)
        self.char_count = QLabel("Số ký tự: 0  |  Bytes: 0 (UTF-8)"); self.char_count.setObjectName("Muted"); rp.addWidget(self.char_count)

        context = QFrame(); context.setObjectName("InnerCard")
        cg = QGridLayout(context); cg.setContentsMargins(10, 10, 10, 10); cg.setHorizontalSpacing(12); cg.setVerticalSpacing(5)
        ctx_title = QLabel("Thông tin ngữ cảnh"); ctx_title.setObjectName("PanelTitle"); cg.addWidget(ctx_title, 0, 0, 1, 2)
        self.info_path = QLabel("—"); self.info_type = QLabel("—"); self.info_count = QLabel("0"); self.info_score = QLabel("—"); self.info_status = QLabel("—")
        self.info_path.setWordWrap(True)
        for r, (lab, widget) in enumerate([("Nguồn:", self.info_path), ("Loại:", self.info_type), ("Index:", self.info_count), ("ID / Key:", self.info_score), ("Trạng thái:", self.info_status)], start=1):
            k = QLabel(lab); k.setObjectName("Muted"); cg.addWidget(k, r, 0); cg.addWidget(widget, r, 1)
        rp.addWidget(context)

        suggestion = QFrame(); suggestion.setObjectName("SuggestionCard")
        sg = QVBoxLayout(suggestion); sg.setContentsMargins(10, 9, 10, 9); sg.setSpacing(4)
        sg_title = QLabel("💡  Gợi ý dịch"); sg_title.setObjectName("SuggestionTitle")
        self.suggestion_text = QLabel("Chọn một chuỗi để xem gợi ý biên tập."); self.suggestion_text.setObjectName("SuggestionText"); self.suggestion_text.setWordWrap(True)
        sg.addWidget(sg_title); sg.addWidget(self.suggestion_text)
        rp.addWidget(suggestion)

        self.details = QTextEdit(); self.details.setReadOnly(True); self.details.hide()
        rp.addStretch(1)
        quick = QHBoxLayout(); quick.setSpacing(7)
        self.autosave_check = QCheckBox("Tự động lưu (Auto-save)"); self.autosave_check.setChecked(True)
        self.copy_original_btn = QPushButton("Sao chép"); self.copy_original_btn.setEnabled(False)
        self.clear_translation_btn = QPushButton("Xóa"); self.clear_translation_btn.setEnabled(False)
        self.editor_save_btn = QPushButton("Lưu & tiếp"); self.editor_save_btn.setObjectName("Primary"); self.editor_save_btn.setEnabled(False)
        quick.addWidget(self.autosave_check); quick.addStretch(); quick.addWidget(self.copy_original_btn); quick.addWidget(self.clear_translation_btn); quick.addWidget(self.editor_save_btn)
        rp.addLayout(quick)
        workspace.addWidget(right_panel)

        workspace.setStretchFactor(0, 20); workspace.setStretchFactor(1, 50); workspace.setStretchFactor(2, 30)
        workspace.setSizes([260, 680, 340])
        page.addWidget(workspace_wrap, 1)

        # Hidden compatibility table for analyzer methods that still use it internally.
        self.candidates = QTableWidget(0, 5); self.candidates.hide()
        self.candidates.setHorizontalHeaderLabels(["#", "File/Class", "Loại", "Chuỗi", "Điểm"])

        # 3. Bottom status bar from the supplied reference layout.
        self.recovery_label = QLabel("")
        self.file_label = QLabel("Chưa nạp JAR")
        self.total_label = QLabel("Tổng: 0 chuỗi")
        self.progress_bar = QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setFixedWidth(220); self.progress_bar.setValue(0); self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("Đã dịch: 0 / 0 (0%)")
        self.status_progress = QProgressBar(); self.status_progress.setRange(0,100); self.status_progress.hide(); self.status_progress.setValue(0)
        self.statusBar().addWidget(self.file_label, 2)
        self.statusBar().addWidget(self.total_label, 1)
        self.statusBar().addWidget(self.progress_bar, 1)
        self.statusBar().addWidget(self.progress_label, 2)
        self.statusBar().addPermanentWidget(self.recovery_label)
        self.status_ready = QLabel("●  Sẵn sàng"); self.status_ready.setStyleSheet("color:#10B981; font-weight:600;")
        self.statusBar().addPermanentWidget(self.status_ready)

        self.autosave_timer = QTimer(self); self.autosave_timer.setSingleShot(True); self.autosave_timer.setInterval(1500); self.autosave_timer.timeout.connect(self.perform_autosave)

        # Controller bindings.
        self.open_btn.clicked.connect(self.open_jar)
        self.scan_btn.clicked.connect(lambda: self.open_jar(self.result.jar_path) if self.result else None)
        self.import_csv_btn.clicked.connect(self.import_csv); self.export_csv_btn.clicked.connect(self.export_csv)
        self.import_json_btn.clicked.connect(self.import_translation_json); self.export_json_btn.clicked.connect(self.export_translation_json)
        self.binary_btn.clicked.connect(self.analyze_selected_binary); self.glyph_btn.clicked.connect(self.analyze_glyphs)
        self.readiness_btn.clicked.connect(self.show_build_readiness); self.log_btn.clicked.connect(self.analyze_runtime_log)
        self.build_jar_btn.clicked.connect(self.build_vietnamese_jar)
        self.strings.itemSelectionChanged.connect(self.load_selected_string_editor); self.strings.itemChanged.connect(self.translation_edited)
        self.search_box.textChanged.connect(self.refresh_strings); self.status_filter.currentIndexChanged.connect(self.refresh_strings); self.source_filter.currentIndexChanged.connect(self.refresh_strings)
        self.file_search.textChanged.connect(self.filter_tree)
        self.copy_original_btn.clicked.connect(self.copy_original_to_translation); self.clear_translation_btn.clicked.connect(self.clear_selected_translation)
        self.editor_save_btn.clicked.connect(self.save_editor_translation)
        self.prev_string_btn.clicked.connect(lambda: self._select_relative_string(-1)); self.next_string_btn.clicked.connect(lambda: self._select_relative_string(1))
        self.translation_edit.textChanged.connect(self._update_translation_count)

        QShortcut(QKeySequence.Save, self, activated=self.save_editor_translation)
        QShortcut(QKeySequence.Find, self, activated=self.search_box.setFocus)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save_project)
        QShortcut(QKeySequence("Tab"), self, activated=self._focus_translation_editor)
        QShortcut(QKeySequence("Shift+Tab"), self, activated=self._focus_original_editor)
        QTimer.singleShot(0, self.apply_responsive_layout)

    # ---------- V4.6 JSON Protocol UI ----------

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")

    def _title_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton) and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _title_mouse_release(self, event):
        self._drag_pos = None
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,"workspace"):
            self.apply_responsive_layout()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.apply_responsive_layout)

    def apply_responsive_layout(self):
        """Keep the three-column workspace readable without clipping."""
        w=max(1,self.centralWidget().width() if self.centralWidget() else self.width())
        if w < 1180:
            left=max(190,int(w*0.19)); right=max(280,int(w*0.28))
        else:
            left=max(230,int(w*0.20)); right=max(320,int(w*0.28))
        center=max(420,w-left-right-18)
        self.workspace.setSizes([left,center,right])
        self.progress_bar.setMaximumWidth(360 if w>=1280 else 250)

    def filter_tree(self, text):
        q=text.strip().lower()
        def walk(item):
            child_match=any(walk(item.child(i)) for i in range(item.childCount()))
            own=(q in item.text(0).lower()) if q else True
            visible=own or child_match or not q; item.setHidden(not visible)
            if child_match and q: item.setExpanded(True)
            return visible
        for i in range(self.tree.topLevelItemCount()): walk(self.tree.topLevelItem(i))

    def _update_translation_count(self):
        text=self.translation_edit.toPlainText(); self.char_count.setText(f"Số ký tự: {len(text)}  |  Bytes: {len(text.encode('utf-8'))} (UTF-8)")

    def _focus_translation_editor(self):
        if self.original_edit.hasFocus(): self.translation_edit.setFocus()

    def _focus_original_editor(self):
        if self.translation_edit.hasFocus(): self.original_edit.setFocus()

    def _select_relative_string(self, delta):
        if self.strings.rowCount() <= 0:
            return
        rows=self.strings.selectionModel().selectedRows()
        row=rows[0].row() if rows else 0
        row=max(0,min(self.strings.rowCount()-1,row+delta))
        self.strings.selectRow(row)
        item=self.strings.item(row,2)
        if item:
            self.strings.scrollToItem(item,QAbstractItemView.PositionAtCenter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile().lower() for u in event.mimeData().urls()]
            if any(p.endswith((".jar", ".jtv2.json", ".csv")) for p in paths):
                event.acceptProposedAction(); return
        event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not files:
            return
        path = files[0]
        low = path.lower()
        if low.endswith(".jar"):
            self.open_jar(path)
        elif low.endswith(".jtv2.json") or low.endswith(".json"):
            self.open_project(path)
        elif low.endswith(".csv") and self.result:
            self.import_csv(path)
        event.acceptProposedAction()

    # ---------- Window/project lifecycle ----------
    def closeEvent(self, event):
        if self.project.dirty:
            self.perform_autosave()
            ans = QMessageBox.question(
                self, "Unsaved project",
                "Translation changes are not manually saved.\nA recovery snapshot was written when possible.\n\nClose anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans == QMessageBox.No:
                event.ignore(); return
        event.accept()

    def open_jar(self, preset_path=None):
        if self.worker is not None and self.worker.isRunning():
            self.statusBar().showMessage("Đang quét JAR hiện tại. Vui lòng chờ quét hoàn tất trước khi mở file khác.", 5000)
            return
        if self.project.dirty and self.result:
            self.perform_autosave()
        path = preset_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Mở file JAR", "", "Java archive (*.jar);;All files (*)")
        if not path:
            return

        # Phase 1: show the archive immediately. Reading the ZIP directory is cheap and
        # must not wait for the expensive language scan to finish.
        try:
            entries = self._preview_jar_structure(path)
        except Exception as e:
            QMessageBox.critical(self, "Không thể mở JAR", str(e))
            return

        self.result = None
        self.project = TranslationProject(jar_path=path)
        self.visible_strings = []
        self.strings.setRowCount(0)
        self.file_label.setText(f"Đã mở: {Path(path).name}")
        self.total_label.setText("Đang quét ngôn ngữ…")
        self.progress_label.setText(f"{len(entries)} file trong JAR")
        self.progress_bar.setRange(0, 0)
        self.center_title.setText("Chuỗi ngôn ngữ (đang quét…)")
        self.status_ready.setText("●  Đang quét")
        self.statusBar().showMessage("Đã nạp cấu trúc JAR. Đang quét ngôn ngữ ở nền…")
        self._set_scan_actions_enabled(False)

        import time
        self._scan_started_at = time.monotonic()
        self.worker = ScanWorker(path)
        self.worker.partial_result.connect(self.scan_partial)
        self.worker.progress.connect(self.scan_progress)
        scan_worker = self.worker
        self.worker.finished_result.connect(self.scan_complete)
        self.worker.failed.connect(self.scan_failed)
        self.worker.finished.connect(lambda w=scan_worker: self._release_thread("worker", w))
        self.open_btn.setEnabled(False)
        if "open" in getattr(self, "workflow_actions", {}):
            self.workflow_actions["open"].setEnabled(False)
        self.worker.start()

    def _preview_jar_structure(self, path):
        """Populate Explorer immediately from the ZIP central directory.

        This is intentionally independent from JarScanner so opening a JAR always gives
        instant visual feedback, even when deep language analysis takes many seconds.
        """
        with zipfile.ZipFile(path, "r") as zf:
            # Reading the central directory is intentionally enough here. CRC validation
            # would read the whole archive and destroy the instant-open UX. Deep scan/build
            # validation still performs the expensive content checks later.
            entries = [i.filename.rstrip("/") for i in zf.infolist() if i.filename and not i.is_dir()]
        self._populate_tree_from_entries(path, entries)
        return entries

    def _populate_tree_from_entries(self, jar_path, entries):
        self.tree.clear()
        nodes = {}
        root = QTreeWidgetItem([Path(jar_path).name])
        root.setData(0, Qt.UserRole, "")
        self.tree.addTopLevelItem(root)
        nodes[""] = root
        for entry in entries:
            parent = root
            current = ""
            for part in entry.split("/"):
                if not part:
                    continue
                current = f"{current}/{part}" if current else part
                if current not in nodes:
                    item = QTreeWidgetItem([part])
                    item.setData(0, Qt.UserRole, current)
                    parent.addChild(item)
                    nodes[current] = item
                parent = nodes[current]
        root.setExpanded(True)
        self.tree.expandToDepth(1)

    def _set_scan_actions_enabled(self, enabled):
        self.open_btn.setEnabled(True)
        self.scan_btn.setEnabled(enabled)
        self.binary_btn.setEnabled(enabled)
        self.compat_btn.setEnabled(enabled)
        self.glyph_btn.setEnabled(enabled)
        self.readiness_btn.setEnabled(enabled)
        self.log_btn.setEnabled(enabled)
        self.export_json_btn.setEnabled(enabled)
        self.import_json_btn.setEnabled(enabled)
        self.import_csv_btn.setEnabled(enabled)
        self.export_csv_btn.setEnabled(enabled)
        self.build_jar_btn.setEnabled(enabled)
        for key in ("scan","binary","import_csv","export_csv","import_json","export_json","glyph","readiness","log"):
            if key in getattr(self, "workflow_actions", {}):
                self.workflow_actions[key].setEnabled(enabled)

    def _release_thread(self, attr_name, worker):
        if getattr(self, attr_name, None) is worker:
            setattr(self, attr_name, None)
        worker.deleteLater()

    def scan_progress(self, percent, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.progress_label.setText(f"Quét: {int(percent)}%")
        self.statusBar().showMessage(message)

    def scan_partial(self, result):
        """Show fast-pass strings immediately while the worker may continue deeper."""
        if result is None:
            return
        self.result = result
        self.project.jar_path = result.jar_path
        self._sync_sources_and_strings()
        self.update_progress()
        self.center_title.setText(f"Chuỗi ngôn ngữ ({sum(len(c.strings) for c in result.candidates)}) · đang hoàn tất quét…")

    def scan_failed(self, message):
        self.open_btn.setEnabled(True)
        if "open" in getattr(self, "workflow_actions", {}):
            self.workflow_actions["open"].setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.total_label.setText("Quét thất bại")
        self.progress_label.setText("Explorer vẫn khả dụng")
        self.center_title.setText("Chuỗi ngôn ngữ (0)")
        self.status_ready.setText("●  Lỗi quét")
        self._set_scan_actions_enabled(False)
        self.statusBar().showMessage("Quét ngôn ngữ thất bại", 8000)
        QMessageBox.critical(self, "Lỗi quét JAR", message)

    def scan_complete(self, result):
        self.open_btn.setEnabled(True)
        if "open" in getattr(self, "workflow_actions", {}):
            self.workflow_actions["open"].setEnabled(True)
        self.result = result
        if not self.project.jar_path:
            self.project = TranslationProject(jar_path=result.jar_path)
        else:
            self.project.jar_path = result.jar_path
        self.progress_bar.setRange(0, 100)
        self._set_scan_actions_enabled(True)
        self.save_project_btn.setEnabled(True)
        self.copy_original_btn.setEnabled(True)
        self.clear_translation_btn.setEnabled(True)
        self.status_ready.setText("●  Sẵn sàng")
        # Explorer is already visible from phase 1. Re-sync with scanner output only in
        # case the scanner normalized entry names differently. Do not rebuild legacy hidden
        # candidate tables; the modern UI works directly from result.candidates.
        # Explorer was populated immediately from ZIP central directory. Rebuilding
        # the tree here only wastes UI time on large archives.
        self._sync_sources_and_strings()
        self.update_progress()
        d=getattr(result,"diagnostics",{}) or {}
        total_strings=d.get("total_strings",sum(len(c.strings) for c in result.candidates))
        deep_entries=d.get("entries_deep_scanned",0)
        rejected=d.get("strings_rejected_non_language",0)
        self.statusBar().showMessage(
            f"Precision Scan: {len(result.entries)} entries | {deep_entries} deep-scanned | "
            f"{len(result.candidates)} candidates | {total_strings} game-text strings | "
            f"{rejected} technical/noise strings filtered"
        )
        if not result.candidates:
            self.details.setPlainText(
                "DEEP SCAN KHÔNG TÌM THẤY TEXT\n\n"
                f"Entries trong JAR: {d.get('entries_total',len(result.entries))}\n"
                f"Entries đã đọc: {d.get('entries_read',0)}\n"
                f"Entries Deep Scan: {d.get('entries_deep_scanned',0)}\n"
                f"Class parse lỗi: {d.get('class_parse_failed',0)}\n"
                f"Chuỗi thô: {d.get('strings_before_filter',0)}\n"
                f"Chuỗi sau lọc: {d.get('strings_after_filter',0)}\n"
                f"Chuỗi kỹ thuật/noise đã loại: {d.get('strings_rejected_non_language',0)}\n\n"
                "Nếu vẫn bằng 0, game có khả năng dùng text nén/mã hóa, font-map riêng, "
                "hoặc tự giải mã chuỗi lúc runtime. Khi đó cần phân tích chính JAR game cụ thể."
            )
        try:
            import time
            elapsed = time.monotonic() - self._scan_started_at if self._scan_started_at else 0
            self.statusBar().showMessage(self.statusBar().currentMessage() + f" | {elapsed:.1f}s")
        except Exception:
            pass
        self.check_recovery_snapshot()

    # ---------- Views ----------
    def populate_tree(self):
        self.tree.clear(); nodes={}
        if not self.result: return
        root=QTreeWidgetItem([Path(self.result.jar_path).name]); self.tree.addTopLevelItem(root); nodes[""]=root
        for entry in self.result.entries:
            parent=root; current=""
            for part in entry.split("/"):
                current=f"{current}/{part}" if current else part
                if current not in nodes:
                    item=QTreeWidgetItem([part]); item.setData(0,Qt.UserRole,current); parent.addChild(item); nodes[current]=item
                parent=nodes[current]
        root.setExpanded(True); self.tree.expandToDepth(1)

    def _sync_sources_and_strings(self):
        """Populate modern filters/table without touching the retired hidden candidate table."""
        self.source_filter.blockSignals(True)
        try:
            self.source_filter.clear()
            self.source_filter.addItem("Tất cả nguồn")
            seen = set()
            for c in self.result.candidates:
                if c.source not in seen:
                    self.source_filter.addItem(c.source)
                    seen.add(c.source)
        finally:
            self.source_filter.blockSignals(False)
        self.current_candidate = self.result.candidates[0] if self.result.candidates else None
        self.refresh_strings()

    def populate_candidates(self):
        self.candidates.setRowCount(len(self.result.candidates))
        self.source_filter.blockSignals(True); self.source_filter.clear(); self.source_filter.addItem("Tất cả nguồn")
        seen=set()
        for row,c in enumerate(self.result.candidates):
            vals=[str(row+1),c.source,c.source_type,str(len(c.strings)),f"{c.score}%"]
            for col,val in enumerate(vals): self.candidates.setItem(row,col,QTableWidgetItem(val))
            if c.source not in seen: self.source_filter.addItem(c.source); seen.add(c.source)
        self.source_filter.blockSignals(False)
        self.current_candidate=self.result.candidates[0] if self.result.candidates else None
        self.refresh_strings()

    def show_selected_candidate(self):
        rows=self.candidates.selectionModel().selectedRows()
        if rows and self.result:
            self.current_candidate=self.result.candidates[rows[0].row()]
            self.refresh_strings()

    def refresh_strings(self):
        if not self.result:
            self.visible_strings=[]; self.strings.setRowCount(0); return
        query=self.search_box.text().strip().lower(); mode=self.status_filter.currentText(); source_mode=self.source_filter.currentText()
        all_strings=[]; seen=set()
        for c in self.result.candidates:
            for st in c.strings:
                if st.key in seen: continue
                seen.add(st.key); all_strings.append(st)
        self.visible_strings=[]
        for st in all_strings:
            vi=self.project.get(st.key); translated=bool(vi.strip()); review=translated and vi.strip()==st.value.strip()
            if mode=="Đã dịch" and (not translated or review): continue
            if mode=="Chưa dịch" and translated: continue
            if mode=="Cần kiểm tra" and not review: continue
            if source_mode!="Tất cả nguồn" and st.source!=source_mode: continue
            if query and query not in st.value.lower() and query not in vi.lower() and query not in st.source.lower(): continue
            self.visible_strings.append(st)
        render_limit = 3000
        visible_total = len(self.visible_strings)
        rendered_strings = self.visible_strings[:render_limit]
        if hasattr(self,"center_title"):
            if visible_total > render_limit:
                self.center_title.setText(f"Chuỗi ngôn ngữ ({visible_total}) · hiển thị {render_limit}")
            else:
                self.center_title.setText(f"Chuỗi ngôn ngữ ({visible_total})")
        self._updating_table=True; self.strings.blockSignals(True); self.strings.setUpdatesEnabled(False)
        try:
            self.strings.setRowCount(len(rendered_strings))
            for row,st in enumerate(rendered_strings):
                vi=self.project.get(st.key); translated=bool(vi.strip()); review=translated and vi.strip()==st.value.strip()
                status="Cần kiểm tra" if review else ("Đã dịch" if translated else "Chưa dịch")
                vals=[str(row+1),status,st.value,vi,st.source]
                for col,val in enumerate(vals):
                    item=QTableWidgetItem(val); item.setData(Qt.UserRole,st.key)
                    if col!=3: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.strings.setItem(row,col,item)
                self._paint_row(row,translated,review)
        finally:
            self.strings.setUpdatesEnabled(True); self.strings.blockSignals(False); self._updating_table=False

    def _paint_row(self, row, translated, review=False):
        # StatusBadgeDelegate owns the visual badge; keeping the model item free of
        # hard-coded brushes prevents selected-row colors from fighting the theme.
        item=self.strings.item(row,1)
        if item:
            item.setBackground(QBrush(Qt.transparent))
            item.setForeground(QBrush(QColor("#D7E0EA")))
            item.setTextAlignment(Qt.AlignCenter)

    def translation_edited(self, item):
        if self._updating_table or item.column()!=3: return
        row=item.row()
        if row>=len(self.visible_strings): return
        st=self.visible_strings[row]; value=item.text(); self.project.set(st.key,value)
        translated=bool(value.strip()); review=translated and value.strip()==st.value.strip(); status="Cần kiểm tra" if review else ("Đã dịch" if translated else "Chưa dịch")
        self._updating_table=True; self.strings.item(row,1).setText(status); self._paint_row(row,translated,review); self._updating_table=False
        self.update_progress(); self.load_selected_string_editor(); self.schedule_autosave()

    def selected_rows(self):
        return sorted({idx.row() for idx in self.strings.selectionModel().selectedRows()})

    def copy_original_to_translation(self):
        rows=self.selected_rows()
        if not rows: return
        self._updating_table=True
        for row in rows:
            st=self.visible_strings[row]; self.project.set(st.key,st.value); self.strings.item(row,3).setText(st.value); self.strings.item(row,1).setText("Cần kiểm tra"); self._paint_row(row,True,True)
        self._updating_table=False; self.update_progress(); self.load_selected_string_editor(); self.schedule_autosave()

    def clear_selected_translation(self):
        rows=self.selected_rows()
        if not rows: return
        self._updating_table=True
        for row in rows:
            st=self.visible_strings[row]; self.project.set(st.key,""); self.strings.item(row,3).setText(""); self.strings.item(row,1).setText("Chưa dịch"); self._paint_row(row,False,False)
        self._updating_table=False; self.update_progress(); self.load_selected_string_editor(); self.schedule_autosave()

    def update_progress(self):
        if not self.result:
            self.progress_label.setText("Đã dịch: 0 / 0 (0%)"); self.total_label.setText("Tổng: 0 chuỗi"); self.progress_bar.setValue(0); self.status_progress.setValue(0); self.setWindowTitle(self.APP_NAME); return
        total,translated=self.project.stats(self.result); pct=int(round(translated*100/total)) if total else 0
        self.total_label.setText(f"Tổng: {total} chuỗi")
        self.progress_label.setText(f"Đã dịch: {translated} / {total} ({pct}%)"); self.progress_bar.setValue(pct); self.status_progress.setValue(pct)
        self.setWindowTitle(self.APP_NAME)

    def recovery_path(self):
        if not self.result:
            return None
        jar = Path(self.result.jar_path)
        return jar.with_name(jar.stem + ".autosave.jtv2.json")

    def schedule_autosave(self):
        if self.autosave_check.isChecked() and self.result and self.project.dirty:
            self.autosave_timer.start()

    def perform_autosave(self):
        if not (self.result and self.project.dirty and self.autosave_check.isChecked()):
            return
        if self._autosave_worker is not None and self._autosave_worker.isRunning():
            # Coalesce repeated autosaves instead of stacking worker threads.
            self.autosave_timer.start()
            return
        path = self.recovery_path()
        if not path:
            return
        try:
            payload=self.project._payload(self.result)
            payload["autosave"]=True
            self._autosave_worker=AutosaveWorker(str(path),payload)
            self._autosave_worker.finished_save.connect(self._autosave_finished)
            self._autosave_worker.failed.connect(self._autosave_failed)
            self._autosave_worker.start()
            self.recovery_label.setText("Recovery: saving…")
        except Exception as e:
            self.recovery_label.setText("Recovery: failed")
            self.statusBar().showMessage(f"Autosave failed: {e}",5000)

    def _autosave_finished(self,path):
        self.recovery_label.setText("Recovery: saved")
        self.statusBar().showMessage(f"Autosaved recovery snapshot: {path}",3000)
        self._autosave_worker=None

    def _autosave_failed(self,message):
        self.recovery_label.setText("Recovery: failed")
        self.statusBar().showMessage(f"Autosave failed: {message}",5000)
        self._autosave_worker=None

    def check_recovery_snapshot(self):
        path = self.recovery_path()
        if not path or not path.exists() or self.project.project_path:
            return
        try:
            project = TranslationProject.load(str(path))
            if project.jar_path and Path(project.jar_path).resolve() == Path(self.result.jar_path).resolve() and project.translations:
                ans = QMessageBox.question(
                    self, "Recovery snapshot found",
                    f"Found autosaved translations ({len(project.translations)} entries).\nRestore them?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if ans == QMessageBox.Yes:
                    self.project.translations = project.translations
                    self.project.dirty = True
                    self.refresh_strings(); self.update_progress()
                    self.recovery_label.setText("Recovery: restored")
        except Exception:
            pass

    # ---------- Save/import/export ----------
    def save_project(self):
        if not self.result: return
        if not self.project.project_path:
            return self.save_project_as()
        self.project.save(self.project.project_path, self.result)
        self.update_progress(); self.statusBar().showMessage(f"Saved {self.project.project_path}")

    def save_project_as(self):
        if not self.result: return
        default = str(Path(self.result.jar_path).with_suffix(".jtv2.json"))
        path, _ = QFileDialog.getSaveFileName(self, "Save Translation Project", default, "JAR Translator Project (*.jtv2.json);;JSON (*.json)")
        if path:
            self.project.save(path, self.result); self.update_progress(); self.statusBar().showMessage(f"Saved {path}")

    def open_project(self, preset_path=None):
        path = preset_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open Translation Project", "", "JAR Translator Project (*.jtv2.json);;JSON (*.json)")
        if not path: return
        try:
            project = TranslationProject.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Project error", str(e)); return
        jar_path = project.jar_path
        if not jar_path or not Path(jar_path).exists():
            jar_path, _ = QFileDialog.getOpenFileName(self, "Locate source JAR", "", "Java archive (*.jar)")
            if not jar_path: return
            project.jar_path = jar_path
        self.project = project
        self.open_jar(project.jar_path)

    def import_csv(self, preset_path=None):
        if not self.result: return
        path = preset_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Import translations", "", "CSV (*.csv)")
        if not path: return
        try:
            imported, skipped = self.project.import_csv(path, self.result)
            self.refresh_strings(); self.update_progress(); self.schedule_autosave()
            QMessageBox.information(self, "Import complete", f"Imported: {imported}\nSkipped/unmatched: {skipped}")
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))

    def export_csv(self):
        if not self.result: return
        default = str(Path(self.result.jar_path).with_suffix(".translation.csv"))
        path, _ = QFileDialog.getSaveFileName(self, "Export translations", default, "CSV (*.csv)")
        if path:
            self.project.export_csv(self.result, path); self.statusBar().showMessage(f"Exported {path}")








    # ---------- V3.9 Runtime Log Analyzer ----------


    # ---------- V4.5 JSON Translation Exchange ----------
    def show_json_exchange_help(self):
        QMessageBox.information(
            self,
            "Dịch qua JSON",
            "Workflow không dùng API:\n\n"
            "1. Scan JAR và lọc game-text.\n"
            "2. Bấm 'Xuất JSON dịch'.\n"
            "3. Upload JSON lên ChatGPT hoặc Gemini.\n"
            "4. Chỉ cần yêu cầu: Hãy tuân thủ translation_protocol trong file và trả lại đúng JSON hoàn chỉnh.\n"
            "5. Tải JSON đã dịch về máy.\n"
            "6. Bấm 'Nhập JSON dịch'.\n"
            "7. Rà soát trong app rồi Build JAR.\n\n"
            "V4.7 giữ rules V4.6 và bổ sung Extractor V3; V4.6 nhúng rules bắt buộc, output contract, checksum JAR, checksum original và placeholder manifest để giảm lỗi import."
        )

    def export_translation_json(self):
        if not self.result:
            return
        jar=Path(self.result.jar_path)
        default=jar.with_name(jar.stem+"_translate_vi.json")
        path,_=QFileDialog.getSaveFileName(
            self,"Xuất JSON để dịch",str(default),"JSON files (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            count=self.translation_exchange.export_file(
                self.result,self.project,path,include_translated=False
            )
            if count == 0:
                QMessageBox.information(self,"Xuất JSON","Không còn chuỗi chưa dịch phù hợp để xuất.")
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
                return
            self.details.setPlainText(
                "JSON Translation Exchange V4.7\n\n"
                f"File: {path}\n"
                f"Chuỗi xuất: {count}\n\n"
                "Upload file này lên ChatGPT/Gemini.\n"
                "File đã chứa rules và cấu trúc output bắt buộc.\n"
                "Chỉ cần yêu cầu model tuân thủ translation_protocol và trả lại JSON hoàn chỉnh.\n"
                "Sau khi dịch xong, tải JSON về và dùng 'Nhập JSON dịch'."
            )
            QMessageBox.information(
                self,"Xuất JSON thành công",
                f"Đã xuất {count} chuỗi cần dịch.\n\n{path}\n\n"
                "File đã chứa translation_protocol, rules bắt buộc, output contract, checksum và quy tắc bảo toàn placeholder."
            )
        except Exception as e:
            QMessageBox.critical(self,"Xuất JSON",str(e))

    def import_translation_json(self):
        if not self.result:
            return
        path,_=QFileDialog.getOpenFileName(
            self,"Nhập JSON đã dịch",str(Path(self.result.jar_path).parent),
            "JSON files (*.json);;All files (*.*)"
        )
        if not path:
            return

        ans=QMessageBox.question(
            self,
            "Nhập JSON",
            "Có ghi đè những dòng đã có bản dịch trong project hiện tại không?\n\n"
            "Chọn No để chỉ điền các dòng còn trống.",
            QMessageBox.Yes|QMessageBox.No,
            QMessageBox.No
        )
        overwrite=(ans==QMessageBox.Yes)

        # V4.13: JSON parsing/hash/validation runs outside the GUI thread.
        self.import_json_btn.setEnabled(False)
        self.build_jar_btn.setEnabled(False)
        self.statusBar().showMessage("Đang nhập và kiểm tra JSON…")
        self.details.setPlainText(
            "JSON Import\n\n"
            f"File: {path}\n\n"
            "Đang đọc + kiểm tra JSON ở background. Giao diện vẫn có thể thao tác."
        )
        self._json_import_path = path
        self._json_import_worker = JsonImportWorker(
            path, self.result, self.project.translations, overwrite
        )
        self._json_import_worker.finished_import.connect(self._json_import_finished)
        self._json_import_worker.failed.connect(self._json_import_failed)
        self._json_import_worker.start()

    def _json_import_finished(self, report, updates):
        path=getattr(self,"_json_import_path","")
        if updates:
            self.project.translations.update(updates)
            self.project.dirty=True

        self.import_json_btn.setEnabled(True)
        self.build_jar_btn.setEnabled(bool(self.result))

        # V4.13: NEVER rebuild QTableWidget after JSON import.
        # Update only rows that are already materialized on screen, in small
        # event-loop batches. This keeps Windows responsive even for large imports.
        self._json_import_report = report
        self._json_import_updates = dict(updates)
        self._json_import_ui_queue = [
            row for row, s in enumerate(self.visible_strings) if s.key in updates
        ]

        self.update_progress()
        self._continue_import_ui_apply()

        lines=[
            "JSON Translation Import",
            f"File: {path}",
            "",
            f"Imported: {report.imported}",
            f"Skipped existing: {report.skipped_existing}",
            f"Rejected empty: {report.rejected_empty}",
            f"Rejected unknown: {report.rejected_unknown}",
            f"Rejected original mismatch: {report.rejected_original_mismatch}",
            f"Rejected placeholder mismatch: {report.rejected_placeholder}",
            f"Rejected schema: {report.rejected_schema}",
            f"Rejected hash: {report.rejected_hash}",
            f"Rejected duplicate: {report.rejected_duplicate}",
            f"Rejected wrong JAR: {report.rejected_source_jar}",
            "",
            "UI: cập nhật theo lô, không dựng lại toàn bộ bảng.",
        ]
        if report.warnings:
            lines += ["","Warnings:"]+[f"- {x}" for x in report.warnings[:200]]
        self.details.setPlainText("\n".join(lines))
        self.statusBar().showMessage(
            f"Đã nhập dữ liệu; đang cập nhật giao diện theo lô… {len(self._json_import_ui_queue)} dòng",
            5000
        )
        self._json_import_worker=None

    def _continue_import_ui_apply(self):
        # Max 32 rows per event-loop turn to cap GUI latency.
        batch=self._json_import_ui_queue[:32]
        del self._json_import_ui_queue[:32]
        if batch:
            self._updating_table=True
            self.strings.blockSignals(True)
            self.strings.setUpdatesEnabled(False)
            try:
                for row in batch:
                    if row >= len(self.visible_strings):
                        continue
                    s=self.visible_strings[row]
                    vi=self.project.get(s.key)
                    item=self.strings.item(row,3)
                    if item is not None:
                        item.setText(vi)
                    status=self.strings.item(row,1)
                    if status is not None:
                        status.setText("Cần kiểm tra" if vi.strip()==s.value.strip() and vi.strip() else ("Đã dịch" if vi else "Chưa dịch"))
                    self._paint_row(row,bool(vi),bool(vi.strip()) and vi.strip()==s.value.strip())
            finally:
                self.strings.setUpdatesEnabled(True)
                self.strings.blockSignals(False)
                self._updating_table=False
            QTimer.singleShot(0,self._continue_import_ui_apply)
            return

        # Final lightweight work only. No refresh_strings() here.
        self.load_selected_string_editor()
        self.schedule_autosave()
        report=self._json_import_report
        if report is not None:
            self.statusBar().showMessage(
                f"Nhập JSON hoàn tất: {report.imported} imported, {report.rejected_total} rejected",
                5000
            )
        self._json_import_updates={}

    def _json_import_failed(self, message):
        self.import_json_btn.setEnabled(True)
        self.build_jar_btn.setEnabled(bool(self.result))
        self.statusBar().showMessage("Nhập JSON thất bại",5000)
        QMessageBox.critical(self,"Nhập JSON",message)
        self._json_import_worker=None

    def analyze_runtime_log(self):
        if not self.result:
            return
        log_path,_=QFileDialog.getOpenFileName(
            self,"Chọn log FreeJ2ME / RG35XX",str(Path(self.result.jar_path).parent),
            "Log/Text (*.log *.txt);;All files (*.*)"
        )
        if not log_path:
            return

        # Prefer most likely build report beside translated output.
        source=Path(self.result.jar_path)
        candidates=list(source.parent.glob(source.stem+"*_vietnamese.build-report.json"))
        build_report=str(max(candidates,key=lambda p:p.stat().st_mtime)) if candidates else None

        try:
            r=RuntimeLogAnalyzer().analyze(log_path,build_report)
            lines=[
                "Runtime Log Analyzer V4.7 Extractor V3",
                f"Log: {log_path}",
                f"STATUS: {r.status}",
                f"Summary: {r.summary}",
                "",
                f"Lines: {r.total_lines}",
                f"High issues: {r.high_count}",
                f"Medium issues: {r.medium_count}",
                f"Patched sources referenced: {len(r.matched_patch_sources)}",
                "",
                "Exceptions:"
            ]
            if r.exceptions:
                for k,v in sorted(r.exceptions.items(),key=lambda x:(-x[1],x[0])):
                    lines.append(f"- {k}: {v}")
            else:
                lines.append("- none")

            lines += ["","Patched sources referenced:"]
            if r.matched_patch_sources:
                for k,v in sorted(r.matched_patch_sources.items(),key=lambda x:(-x[1],x[0])):
                    lines.append(f"- {k}: {v}")
            else:
                lines.append("- none proven")

            lines += ["","Issues:"]
            for i in r.issues[:300]:
                rel=", ".join(i.related_patch_sources) if i.related_patch_sources else "-"
                lines.append(
                    f"[{i.severity}] line {i.line_no} | {i.category} | {i.exception} | "
                    f"patch={rel}\n  {i.text}\n  {i.hint}"
                )
            self.details.setPlainText("\n".join(lines))

            QMessageBox.information(
                self,"Runtime Log Analyzer",
                f"Status: {r.status}\n"
                f"High: {r.high_count}\n"
                f"Warnings: {r.medium_count}\n"
                f"Patched sources referenced: {len(r.matched_patch_sources)}\n\n"
                f"{r.summary}"
            )
        except Exception as e:
            QMessageBox.critical(self,"Runtime Log Analyzer",str(e))

    # ---------- V3.8 Runtime Test Package ----------
    def create_runtime_test_package(self):
        if not self.result:
            return
        source=Path(self.result.jar_path)
        default_output=source.with_name(source.stem+"_vietnamese.jar")
        output_path,_=QFileDialog.getOpenFileName(
            self,"Chọn JAR tiếng Việt đã build",str(default_output),"JAR files (*.jar)"
        )
        if not output_path:
            return

        dest=QFileDialog.getExistingDirectory(
            self,"Chọn thư mục lưu Runtime Test Package",str(Path(output_path).parent)
        )
        if not dest:
            return

        out=Path(output_path)
        build_report=out.with_suffix(".build-report.json")
        regression_report=out.with_suffix(".regression-report.json")

        try:
            rr=RegressionValidator().validate(self.result,self.project,str(out))
            regression_report.write_text(
                json.dumps({
                    "source_jar":rr.source_jar,
                    "output_jar":rr.output_jar,
                    "archive_ok":rr.archive_ok,
                    "rescan_ok":rr.rescan_ok,
                    "validation_ok":rr.validation_ok,
                    "passed":rr.passed,
                    "failed":rr.failed,
                    "skipped":rr.skipped,
                    "warnings":rr.warnings,
                    "items":[i.__dict__ for i in rr.items],
                },ensure_ascii=False,indent=2),
                encoding="utf-8"
            )

            package=RuntimeTestPackager().create(
                str(source),str(out),dest,
                str(build_report) if build_report.exists() else None,
                str(regression_report),
                notes="Generated by JAR Vietnamese Translator"
            )

            lines=[
                "Runtime Test Package V4.7 Extractor V3",
                f"Folder: {package.folder}",
                f"ZIP: {package.zip_path}",
                "",
                "Contents:",
                f"- {Path(package.source_copy).name}",
                f"- {Path(package.output_copy).name}",
                f"- {Path(package.summary_path).name}",
            ]
            if package.build_report_copy:
                lines.append(f"- {Path(package.build_report_copy).name}")
            if package.regression_report_copy:
                lines.append(f"- {Path(package.regression_report_copy).name}")
            self.details.setPlainText("\n".join(lines))

            QMessageBox.information(
                self,"Runtime Test Package",
                "Đã tạo gói kiểm thử runtime.\n\n"
                f"Folder:\n{package.folder}\n\n"
                f"ZIP:\n{package.zip_path}"
            )
        except Exception as e:
            QMessageBox.critical(self,"Runtime Test Package",str(e))

    # ---------- V3.7 Test Build & Regression Validator ----------
    def run_regression_validation(self):
        if not self.result:
            return
        source=Path(self.result.jar_path)
        default=source.with_name(source.stem+"_vietnamese.jar")
        path,_=QFileDialog.getOpenFileName(self,"Chọn JAR đầu ra để kiểm tra",str(default),"JAR files (*.jar)")
        if not path:
            return
        try:
            rr=RegressionValidator().validate(self.result,self.project,path)
            lines=[
                "Test Build & Regression Validator V4.7 Extractor V3",
                f"Output: {path}",
                f"Archive integrity: {'PASS' if rr.archive_ok else 'FAIL'}",
                f"Rescan: {'PASS' if rr.rescan_ok else 'FAIL'}",
                f"Regression: {'PASS' if rr.validation_ok else 'FAIL'}",
                "",
                f"Passed: {rr.passed}",
                f"Failed: {rr.failed}",
                f"Skipped: {rr.skipped}",
                "",
                "Items:"
            ]
            for i in rr.items:
                lines.append(f"[{i.status}] {i.source} | {i.kind} | {i.original} -> {i.translated} | {i.detail}")
            if rr.warnings:
                lines += ["","Warnings:"]
                lines.extend(f"- {w}" for w in rr.warnings)
            self.details.setPlainText("\n".join(lines))
            QMessageBox.information(
                self,"Regression Validator",
                f"Regression: {'PASS' if rr.validation_ok else 'FAIL'}\n"
                f"Passed: {rr.passed}\nFailed: {rr.failed}\nSkipped: {rr.skipped}"
            )
        except Exception as e:
            QMessageBox.critical(self,"Regression Validator",str(e))

    # ---------- V3.6 Translation Validation & Build Readiness ----------
    def show_build_readiness(self):
        if not self.result:
            return
        try:
            r=BuildReadinessAnalyzer().analyze(self.result,self.project)
            lines=[
                "Translation Validation & Build Readiness V4.7 Extractor V3",
                f"STATUS: {r.status}",
                "",
                f"Strings: {r.total_strings}",
                f"Translated: {r.translated_strings}",
                f"Untranslated: {r.untranslated_strings}",
                f"Coverage: {r.translated_ratio*100:.1f}%",
                f"Binary safe: {r.binary_safe}",
                f"Binary locked: {r.binary_unsafe}",
                f"Compatibility risk: {r.compatibility_risk.upper()}",
                f"Glyph risk: {r.glyph_risk.upper()}",
                "",
                f"Blocked issues: {r.blocked_count}",
                f"Warnings: {r.warning_count}",
                "",
                "Issues:"
            ]
            for i in r.issues:
                lines.append(f"[{i.level}] {i.category} | {i.source} | {i.message}")
            self.details.setPlainText("\n".join(lines))

            icon = {
                "READY": "READY - có thể build",
                "WARNING": "WARNING - có thể build nhưng cần kiểm tra",
                "BLOCKED": "BLOCKED - chưa đủ điều kiện build"
            }[r.status]

            QMessageBox.information(
                self,"Build Readiness",
                f"{icon}\n\n"
                f"Translated: {r.translated_strings}/{r.total_strings} ({r.translated_ratio*100:.1f}%)\n"
                f"Warnings: {r.warning_count}\n"
                f"Blocked: {r.blocked_count}\n\n"
                "Chi tiết đã hiển thị ở khung Xem trước chuỗi."
            )
        except Exception as e:
            QMessageBox.critical(self,"Build Readiness",str(e))

    # ---------- V3.5 Font/Glyph Analyzer ----------
    def analyze_glyphs(self):
        if not self.result:
            return
        try:
            report=GlyphAnalyzer().analyze(self.result.jar_path,self.result,self.project)
            lines=[
                "Font / Glyph Analyzer V4.7 Extractor V3",
                f"Risk: {report.risk.upper()}",
                f"Confidence: {report.confidence}%",
                f"Required characters: {len(report.required_chars)}",
                f"Mapped characters: {len(report.mapped_chars)}",
                f"Missing characters: {len(report.missing_chars)}",
                "",
                "Parsed font maps:"
            ]
            if report.maps:
                for m in report.maps:
                    lines.append(f"- {m.source} | {m.format_name} | {m.confidence}% | {len(m.glyphs)} glyphs")
            else:
                lines.append("- none")

            lines += ["", "Missing glyphs:"]
            if report.missing_chars:
                chars=" ".join(sorted(report.missing_chars,key=lambda c:ord(c)))
                lines.append(chars)
                lines.append("")
                for c in sorted(report.missing_chars,key=lambda c:ord(c)):
                    lines.append(f"{c}  U+{ord(c):04X}")
            else:
                lines.append("- none detected")

            lines += ["", "Notes:"]
            lines.extend(f"- {n}" for n in report.notes)
            self.details.setPlainText("\n".join(lines))

            msg=(
                f"Risk: {report.risk.upper()}\n"
                f"Confidence: {report.confidence}%\n"
                f"Required: {len(report.required_chars)}\n"
                f"Mapped: {len(report.mapped_chars)}\n"
                f"Missing: {len(report.missing_chars)}"
            )
            QMessageBox.information(self,"Font / Glyph Analyzer",msg)
        except Exception as e:
            QMessageBox.critical(self,"Glyph Analyzer",str(e))

    # ---------- V3.4 Encoding & Font Compatibility ----------
    def analyze_compatibility(self):
        if not self.result:
            return
        try:
            report=CompatibilityAnalyzer().analyze(self.result.jar_path,self.result,self.project)
            lines=[
                "Encoding & Font Compatibility Analyzer V4.7 Extractor V3",
                f"Encoding risk: {report.encoding_risk.upper()}",
                f"Font risk: {report.font_risk.upper()}",
                f"Overall risk: {report.overall_risk.upper()}",
                f"Unicode evidence: {report.unicode_evidence}",
                f"Custom font evidence: {report.custom_font_evidence}",
                "",
                "Font candidates:"
            ]
            if report.font_candidates:
                lines.extend(f"- {x}" for x in report.font_candidates[:100])
            else:
                lines.append("- none detected")
            if report.suspicious_images:
                lines += ["", "Possible bitmap-font images:"]
                lines.extend(f"- {x}" for x in report.suspicious_images[:100])

            lines += ["", "Findings:"]
            for f in report.findings:
                lines.append(f"[{f.severity.upper()}] {f.category} | {f.source} | {f.message}")

            self.details.setPlainText("\n".join(lines))
            QMessageBox.information(
                self,"Encoding / Font Compatibility",
                f"Encoding risk: {report.encoding_risk.upper()}\n"
                f"Font risk: {report.font_risk.upper()}\n"
                f"Overall: {report.overall_risk.upper()}\n\n"
                f"Chi tiết đã hiển thị trong khung Xem trước chuỗi."
            )
        except Exception as e:
            QMessageBox.critical(self,"Compatibility Analyzer",str(e))

    # ---------- V3.3 Controlled Binary Patch ----------
    def analyze_selected_binary(self):
        if not self.result:
            return
        entries=[e for e in self.result.entries if e.lower().endswith((".dat",".bin",".res"))]
        if not entries:
            QMessageBox.information(self,"Binary Analyzer","JAR hiện tại không có .dat/.bin/.res.")
            return

        selected=self.tree.selectedItems()
        entry=None
        if selected:
            label=selected[0].text(0)
            for e in entries:
                if e.endswith(label):
                    entry=e; break
        if entry is None:
            entry=entries[0]

        try:
            import zipfile
            with zipfile.ZipFile(self.result.jar_path,"r") as z:
                data=z.read(entry)
            analysis=BinaryResourceAnalyzer().analyze(entry,data)
            lines=[
                "Binary Resource Analyzer v3.2",
                f"File: {analysis.source}",
                f"Format: {analysis.format_name}",
                f"Confidence: {analysis.confidence}%",
                f"Strings: {analysis.total_count}",
                f"Safe to patch: {analysis.safe_count}",
                "",
                *analysis.notes,
                "",
                "Detected strings:"
            ]
            for s in analysis.strings[:200]:
                lines.append(f"0x{s.offset:08X}  [{s.framing}]  safe={s.patch_safe}  {s.text}")
            self.details.setPlainText("\n".join(lines))
            QMessageBox.information(
                self,"Binary Analyzer",
                f"File: {entry}\nFormat: {analysis.format_name}\nConfidence: {analysis.confidence}%\n"
                f"Strings: {analysis.total_count}\nSafe: {analysis.safe_count}")
        except Exception as e:
            QMessageBox.critical(self,"Binary Analyzer",str(e))

    # ---------- Right-side translation editor ----------
    def load_selected_string_editor(self):
        rows=self.strings.selectionModel().selectedRows()
        if not rows:
            self.original_edit.clear(); self.translation_edit.clear(); self.editor_save_btn.setEnabled(False)
            if hasattr(self,"inspector_count"): self.inspector_count.setText(f"0 / {len(self.visible_strings)}")
            return
        row=rows[0].row()
        if row>=len(self.visible_strings): return
        st=self.visible_strings[row]; vi=self.project.get(st.key)
        if hasattr(self,"inspector_count"): self.inspector_count.setText(f"{row+1} / {len(self.visible_strings)}")
        self.original_edit.setPlainText(st.value); self.translation_edit.blockSignals(True); self.translation_edit.setPlainText(vi); self.translation_edit.blockSignals(False)
        self.original_meta.setText(f"Số ký tự: {len(st.value)}  |  Bytes: {len(st.value.encode('utf-8'))} (UTF-8)")
        self.char_count.setText(f"Số ký tự: {len(vi)}  |  Bytes: {len(vi.encode('utf-8'))} (UTF-8)")
        self.info_path.setText(st.source); self.info_type.setText(st.kind); self.info_count.setText(str(st.index)); self.info_score.setText(st.key)
        self.info_status.setText("Cần kiểm tra" if vi.strip()==st.value.strip() and vi.strip() else ("Đã dịch" if vi.strip() else "Chưa dịch")); self.editor_save_btn.setEnabled(True)

    def save_editor_translation(self):
        rows=self.strings.selectionModel().selectedRows()
        if not rows: return
        row=rows[0].row()
        if row>=len(self.visible_strings): return
        st=self.visible_strings[row]; value=self.translation_edit.toPlainText(); self.project.set(st.key,value)
        translated=bool(value.strip()); review=translated and value.strip()==st.value.strip(); status="Cần kiểm tra" if review else ("Đã dịch" if translated else "Chưa dịch")
        self._updating_table=True; self.strings.item(row,3).setText(value); self.strings.item(row,1).setText(status); self._paint_row(row,translated,review); self._updating_table=False
        self.update_progress(); self.schedule_autosave()
        if row+1<self.strings.rowCount(): self.strings.selectRow(row+1)

    def show_build_report(self):
        if not self.result: return
        jar=Path(self.result.jar_path)
        candidates=list(jar.parent.glob(jar.stem+"*_vietnamese.build-report.json"))
        if not candidates:
            QMessageBox.information(self,"Báo cáo","Chưa có báo cáo build cho JAR hiện tại.")
            return
        path=max(candidates,key=lambda x:x.stat().st_mtime)
        try:
            self.details.setPlainText(path.read_text(encoding="utf-8"))
            QMessageBox.information(self,"Báo cáo build",f"Đã mở báo cáo mới nhất trong khung xem trước:\n{path}")
        except Exception as e:
            QMessageBox.warning(self,"Báo cáo",str(e))

    # ---------- Responsive Safe Build ----------
    def build_vietnamese_jar(self):
        """Start one non-blocking build transaction.

        All expensive readiness/compatibility checks and the actual JAR rewrite run
        on QThread workers. The UI shows at most one consolidated warning dialog
        before build and one final result dialog afterwards.
        """
        if not self.result or self._build_in_progress:
            return

        total, translated = self.project.stats(self.result)
        if translated == 0:
            QMessageBox.information(self, "Không có bản dịch", "Chưa có chuỗi tiếng Việt để build.")
            return

        source = Path(self.result.jar_path)
        default = str(source.with_name(source.stem + "_vietnamese.jar"))
        path, _ = QFileDialog.getSaveFileName(self, "Build Vietnamese JAR", default, "Java archive (*.jar)")
        if not path:
            return
        if not path.lower().endswith(".jar"):
            path += ".jar"

        try:
            if Path(path).resolve() == source.resolve():
                QMessageBox.critical(self, "Đường dẫn không hợp lệ", "File xuất phải khác JAR nguồn.")
                return
        except Exception:
            pass

        # Immutable snapshot: editing/importing while preflight/build is running cannot
        # alter the transaction halfway through.
        project_snapshot = TranslationProject(
            jar_path=self.project.jar_path,
            translations=dict(self.project.translations),
            project_path=self.project.project_path,
            dirty=self.project.dirty,
        )
        self._pending_build_path = path
        self._build_in_progress = True
        self._set_build_busy(True, "Đang kiểm tra trước khi build…")
        self._build_dialog = BuildTaskDialog(self)
        self._build_dialog.append_log(f"Nguồn: {source.name}")
        self._build_dialog.append_log(f"Đích: {Path(path).name}")
        self._build_dialog.append_log(f"Bản dịch trong snapshot: {translated}/{total}")
        self._build_dialog.show()
        self._build_dialog.raise_()

        self._build_preflight_worker = BuildPreflightWorker(self.result, project_snapshot)
        preflight_worker = self._build_preflight_worker
        self._build_preflight_worker.progress.connect(self._on_build_progress)
        self._build_preflight_worker.finished.connect(lambda w=preflight_worker: self._release_thread("_build_preflight_worker", w))
        self._build_preflight_worker.finished_preflight.connect(
            lambda payload, snap=project_snapshot: self._on_build_preflight_finished(payload, snap)
        )
        self._build_preflight_worker.failed.connect(self._on_build_preflight_failed)
        self._build_preflight_worker.start()

    def _set_build_busy(self, busy, message=""):
        self.build_jar_btn.setEnabled(not busy and bool(self.result))
        if busy:
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText(message or "Đang build JAR…")
            self.statusBar().showMessage(message or "Đang build JAR…")
        else:
            self.progress_bar.setRange(0, 100)
            self.update_progress()

    def _finish_build_ui(self, message=None):
        self._build_in_progress = False
        # Worker references are released only from QThread.finished. Clearing them
        # here can destroy a QThread while its run() method is still returning.
        self._pending_build_path = ""
        self._set_build_busy(False)
        if message:
            self.statusBar().showMessage(message, 10000)

    def _on_build_preflight_finished(self, payload, project_snapshot):
        blocked = list(payload.get("blocked") or [])
        warnings = list(payload.get("warnings") or [])

        if blocked:
            text = "Build bị chặn:\n\n" + "\n".join(f"• {x}" for x in blocked[:20])
            if len(blocked) > 20:
                text += f"\n• … và {len(blocked)-20} lỗi khác"
            if self._build_dialog:
                self._build_dialog.set_task("preflight", "error", text)
                self._build_dialog.append_log(text, "error")
                self._build_dialog.mark_finished(False, "Build bị chặn bởi preflight")
            self._finish_build_ui("Build bị chặn bởi preflight")
            return

        if warnings:
            if self._build_dialog:
                self._build_dialog.set_task("preflight", "warning")
                for warning in warnings:
                    self._build_dialog.append_log(warning, "warning")
        else:
            if self._build_dialog:
                self._build_dialog.set_task("preflight", "done")

        # One dialog only: warnings are informational and stay in the live task log/report.
        # Only BLOCKED issues stop the transaction; this avoids repeated modal
        # dialogs that previously made the build feel stuck.


        self._set_build_busy(True, "Đang build và xác minh JAR…")
        self._build_worker = BuildWorker(self.result, project_snapshot, self._pending_build_path)
        build_worker = self._build_worker
        self._build_worker.progress.connect(self._on_build_progress)
        self._build_worker.finished.connect(lambda w=build_worker: self._release_thread("_build_worker", w))
        self._build_worker.finished_build.connect(self._on_build_finished)
        self._build_worker.failed.connect(self._on_build_failed)
        self._build_worker.start()

    def _on_build_progress(self, percent, stage, message, level="info"):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(max(0, min(100, int(percent))))
        self.progress_label.setText(f"Build: {int(percent)}%")
        self.statusBar().showMessage(message)
        if self._build_dialog:
            # Mark earlier stage done when a later one starts.
            order=["preflight","glyph","compat","prepare","patch","validate","regression","publish"]
            if stage in order:
                idx=order.index(stage)
                for prev in order[:idx]:
                    item=self._build_dialog._task_items.get(prev)
                    if item and item.text(1) in ("Chờ","Đang chạy"):
                        self._build_dialog.set_task(prev,"done")
            self._build_dialog.update_progress(percent, stage, message, level)

    def _on_build_preflight_failed(self, message):
        if self._build_dialog:
            self._build_dialog.set_task("preflight", "error", message)
            self._build_dialog.mark_finished(False, f"Preflight thất bại: {message}")
        self._finish_build_ui("Preflight thất bại")

    def _on_build_finished(self, report, report_path):
        output_path = report.output_jar
        success = bool(report.validation_ok and report.failed == 0)
        summary = (
            f"Output: {output_path}\n\n"
            f"Đã patch: {report.patched}\n"
            f"Bỏ qua: {report.skipped}\n"
            f"Lỗi: {report.failed}\n"
            f"Entries: {report.entries_written}\n"
            f"CRC/Class validation: {'PASS' if report.validation_ok else 'FAILED'}\n"
            f"Regression: {'PASS' if report.regression_ok else 'FAILED'} "
            f"({report.regression_passed} pass / {report.regression_failed} fail / {report.regression_skipped} skip)\n\n"
            f"Báo cáo: {report_path}"
        )
        warning_lines = [w for w in report.warnings if " PASS:" not in w and not w.startswith("Regression validation PASS")]
        if warning_lines:
            summary += "\n\nCảnh báo tổng hợp:\n" + "\n".join(f"• {w}" for w in warning_lines[:10])
            if len(warning_lines) > 10:
                summary += f"\n• … và {len(warning_lines)-10} cảnh báo khác"

        self.report_btn.setEnabled(True)
        self.regression_btn.setEnabled(True)
        self.runtime_btn.setEnabled(True)
        self._finish_build_ui(
            f"Build hoàn tất: patched {report.patched}, skipped {report.skipped}, failed {report.failed}"
        )
        if self._build_dialog:
            self._build_dialog.set_task("patch", "warning" if report.failed else "done")
            self._build_dialog.set_task("validate", "done" if report.validation_ok else "error")
            self._build_dialog.set_task("regression", "done" if report.regression_ok else "warning")
            self._build_dialog.set_task("publish", "done")
            self._build_dialog.append_log(summary, "success" if success else "warning")
            self._build_dialog.mark_finished(True, "Build JAR hoàn tất" if success else "Build hoàn tất nhưng cần kiểm tra báo cáo")

    def _on_build_failed(self, message):
        if self._build_dialog:
            self._build_dialog.set_task("publish", "error", message)
            self._build_dialog.mark_finished(False, f"Build JAR thất bại: {message}")
        self._finish_build_ui(f"Build thất bại: {message}")

