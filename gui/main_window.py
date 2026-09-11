from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect, QPoint
from PySide6.QtGui import QColor, QBrush, QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QMessageBox, QHeaderView, QStatusBar, QTextEdit, QLineEdit,
    QComboBox, QAbstractItemView, QProgressBar, QCheckBox, QFrame, QGroupBox,
    QGridLayout, QScrollArea, QLayout, QSizePolicy
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


class ScanWorker(QThread):
    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            self.finished_result.emit(JarScanner().scan(self.path))
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAR Vietnamese Translator V4.6 JSON Protocol")
        screen = self.screen().availableGeometry() if self.screen() else QRect(0,0,1366,768)
        self.resize(min(1536, int(screen.width()*0.96)), min(1000, int(screen.height()*0.94)))
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)

        self.result = None
        self.worker = None
        self.project = TranslationProject()
        self.current_candidate = None
        self.visible_strings = []
        self._updating_table = False
        self.translation_exchange = TranslationExchange()

        self.setStyleSheet("""
            QMainWindow, QWidget { background:#f6f9fd; color:#14284a; font-family:'Segoe UI'; font-size:13px; }
            QFrame#Header { background:#eef5fc; border-bottom:1px solid #d8e4f2; }
            QLabel#AppTitle { font-size:22px; font-weight:700; color:#14284a; }
            QLabel#Subtitle { font-size:13px; color:#405a7a; }
            QFrame#Toolbar { background:white; border:1px solid #d9e4f0; border-radius:8px; }
            QPushButton { background:transparent; border:0; padding:9px 12px; border-radius:6px; font-weight:600; color:#18365d; }
            QPushButton:hover { background:#eaf3ff; }
            QPushButton:disabled { color:#a9b4c3; }
            QPushButton#Primary { background:#2684e8; color:white; padding:10px 18px; }
            QPushButton#Primary:hover { background:#1876d6; }
            QGroupBox { font-weight:700; border:1px solid #cfdeed; border-radius:7px; margin-top:9px; background:white; }
            QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; color:#173a67; }
            QTreeWidget, QTableWidget, QTextEdit, QLineEdit, QComboBox {
                background:white; border:1px solid #d2dfed; border-radius:5px; selection-background-color:#dceeff;
                selection-color:#102b50;
            }
            QHeaderView::section { background:#f3f7fb; border:0; border-right:1px solid #d8e3ef; border-bottom:1px solid #d8e3ef; padding:7px; font-weight:700; }
            QLineEdit, QComboBox { padding:7px; }
            QProgressBar { background:#e5edf5; border:0; border-radius:7px; height:14px; text-align:center; }
            QProgressBar::chunk { background:#20a85a; border-radius:7px; }
            QStatusBar { background:white; border-top:1px solid #d6e2ef; color:#304d70; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        page = QVBoxLayout(central)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(6)

        # Header
        header = QFrame(); header.setObjectName("Header")
        hl = QHBoxLayout(header); hl.setContentsMargins(24, 12, 24, 10)
        title_col = QVBoxLayout()
        self.app_title = QLabel("🫙  JAR Vietnamese Translator V4.6 JSON Protocol"); self.app_title.setObjectName("AppTitle")
        self.subtitle = QLabel("Phân tích  ·  Dịch thuật  ·  Patch  ·  Tạo JAR tiếng Việt"); self.subtitle.setObjectName("Subtitle")
        app_title=self.app_title; subtitle=self.subtitle
        title_col.addWidget(app_title); title_col.addWidget(subtitle)
        hl.addLayout(title_col); hl.addStretch()
        self.settings_btn = QPushButton("⚙  Cài đặt")
        self.about_btn = QPushButton("ⓘ  Giới thiệu")
        hl.addWidget(self.settings_btn); hl.addWidget(self.about_btn)
        page.addWidget(header)

        # Toolbar matching the approved mockup
        toolbar = QFrame(); toolbar.setObjectName("Toolbar"); self.toolbar_frame=toolbar
        tl = FlowLayout(toolbar, margin=6, hspacing=4, vspacing=4)
        self.open_btn = QPushButton("📂  Mở JAR")
        self.scan_btn = QPushButton("🔍  Quét ngôn ngữ"); self.scan_btn.setEnabled(False)
        self.save_project_btn = QPushButton("▣  Lưu dự án"); self.save_project_btn.setEnabled(False)
        self.open_project_btn = QPushButton("📁  Mở dự án")
        self.import_csv_btn = QPushButton("▤  Nhập CSV"); self.import_csv_btn.setEnabled(False)
        self.export_csv_btn = QPushButton("▥  Xuất CSV"); self.export_csv_btn.setEnabled(False)
        self.export_json_btn = QPushButton("⬆  Xuất JSON dịch"); self.export_json_btn.setEnabled(False)
        self.import_json_btn = QPushButton("⬇  Nhập JSON dịch"); self.import_json_btn.setEnabled(False)
        self.build_jar_btn = QPushButton("🫙  Build JAR tiếng Việt"); self.build_jar_btn.setObjectName("Primary"); self.build_jar_btn.setEnabled(False)
        self.report_btn = QPushButton("▧  Báo cáo"); self.report_btn.setEnabled(False)
        self.binary_btn = QPushButton("🧩  Phân tích Binary"); self.binary_btn.setEnabled(False)
        self.compat_btn = QPushButton("🔤  Encoding / Font"); self.compat_btn.setEnabled(False)
        self.glyph_btn = QPushButton("🔡  Kiểm tra Glyph"); self.glyph_btn.setEnabled(False)
        self.readiness_btn = QPushButton("✅  Kiểm tra Build"); self.readiness_btn.setEnabled(False)
        self.regression_btn = QPushButton("🧪  Kiểm tra JAR đầu ra"); self.regression_btn.setEnabled(False)
        self.runtime_btn = QPushButton("📦  Gói Runtime Test"); self.runtime_btn.setEnabled(False)
        self.log_btn = QPushButton("🩺  Phân tích Log"); self.log_btn.setEnabled(False)
        for b in (self.open_btn,self.scan_btn,self.save_project_btn,self.open_project_btn,self.import_csv_btn,self.export_csv_btn,self.binary_btn,self.compat_btn,self.glyph_btn,self.readiness_btn,self.regression_btn,self.runtime_btn,self.log_btn,self.export_json_btn,self.import_json_btn,self.build_jar_btn,self.report_btn):
            tl.addWidget(b)
        page.addWidget(toolbar)

        # Three-column workspace
        workspace = QSplitter(Qt.Horizontal); self.workspace=workspace
        workspace.setChildrenCollapsible(True)

        left_box = QGroupBox("Cấu trúc JAR"); self.left_box=left_box
        left_l = QVBoxLayout(left_box); left_l.setContentsMargins(6,10,6,6)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        left_l.addWidget(self.tree)
        workspace.addWidget(left_box)

        center = QSplitter(Qt.Vertical); self.center_splitter=center
        scan_box = QGroupBox("Kết quả quét ngôn ngữ")
        scan_l = QVBoxLayout(scan_box); scan_l.setContentsMargins(6,10,6,6)
        self.candidates = QTableWidget(0, 5)
        self.candidates.setHorizontalHeaderLabels(["#", "File/Class", "Loại", "Chuỗi", "Điểm"])
        self.candidates.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.candidates.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.candidates.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.candidates.setAlternatingRowColors(True)
        scan_l.addWidget(self.candidates)
        center.addWidget(scan_box)

        trans_box = QGroupBox("Danh sách chuỗi cần dịch")
        trans_l = QVBoxLayout(trans_box); trans_l.setContentsMargins(6,10,6,6)
        filter_row = QHBoxLayout()
        self.search_box = QLineEdit(); self.search_box.setMinimumWidth(120); self.search_box.setPlaceholderText("🔍  Tìm kiếm (Ctrl+F)...")
        self.status_filter = QComboBox(); self.status_filter.addItems(["Tất cả", "Chưa dịch", "Đã dịch"])
        self.source_filter = QComboBox(); self.source_filter.addItems(["Tất cả nguồn"])
        self.progress_label = QLabel("Tiến độ: 0 / 0 (0%)")
        self.progress_bar = QProgressBar(); self.progress_bar.setRange(0,100); self.progress_bar.setValue(0); self.progress_bar.setMinimumWidth(90); self.progress_bar.setMaximumWidth(180); self.progress_bar.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        filter_row.addWidget(self.search_box,2); filter_row.addWidget(self.status_filter); filter_row.addWidget(self.source_filter)
        filter_row.addStretch(); filter_row.addWidget(self.progress_label); filter_row.addWidget(self.progress_bar)
        trans_l.addLayout(filter_row)

        self.strings = QTableWidget(0, 5)
        self.strings.setHorizontalHeaderLabels(["Trạng thái", "Loại", "#", "Chuỗi gốc (Original)", "Bản dịch tiếng Việt (Vietnamese)"])
        self.strings.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.strings.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.strings.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.strings.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.strings.setAlternatingRowColors(False); self.strings.setWordWrap(True)
        trans_l.addWidget(self.strings)

        action_row=QHBoxLayout()
        self.copy_original_btn=QPushButton("Sao chép gốc → bản dịch"); self.copy_original_btn.setEnabled(False)
        self.clear_translation_btn=QPushButton("Xóa bản dịch"); self.clear_translation_btn.setEnabled(False)
        self.autosave_check=QCheckBox("Tự động lưu"); self.autosave_check.setChecked(True)
        action_row.addWidget(self.copy_original_btn); action_row.addWidget(self.clear_translation_btn); action_row.addStretch(); action_row.addWidget(self.autosave_check)
        trans_l.addLayout(action_row)
        center.addWidget(trans_box)
        center.setSizes([290,520])
        workspace.addWidget(center)

        # Right information/editor column
        right_panel=QWidget(); self.right_panel=right_panel; rp=QVBoxLayout(right_panel); rp.setContentsMargins(0,0,0,0); rp.setSpacing(6)
        info_box=QGroupBox("Thông tin file")
        info_grid=QGridLayout(info_box)
        self.info_path=QLabel("—"); self.info_type=QLabel("—"); self.info_count=QLabel("0"); self.info_score=QLabel("0%"); self.info_status=QLabel("—")
        for r,(lab,w) in enumerate([("Đường dẫn:",self.info_path),("Loại:",self.info_type),("Số chuỗi:",self.info_count),("Điểm ngôn ngữ:",self.info_score),("Trạng thái:",self.info_status)]):
            info_grid.addWidget(QLabel(lab),r,0); info_grid.addWidget(w,r,1)
        rp.addWidget(info_box)

        preview_box=QGroupBox("Xem trước chuỗi"); pv=QVBoxLayout(preview_box)
        self.details=QTextEdit(); self.details.setReadOnly(True); self.details.setPlaceholderText("Chọn một file/class để xem các chuỗi...")
        pv.addWidget(self.details); rp.addWidget(preview_box,1)

        edit_box=QGroupBox("Chỉnh sửa bản dịch"); el=QVBoxLayout(edit_box)
        el.addWidget(QLabel("Chuỗi gốc:"))
        self.original_edit=QTextEdit(); self.original_edit.setReadOnly(True); self.original_edit.setMaximumHeight(72)
        el.addWidget(self.original_edit)
        el.addWidget(QLabel("Bản dịch tiếng Việt:"))
        self.translation_edit=QTextEdit(); self.translation_edit.setMaximumHeight(90)
        el.addWidget(self.translation_edit)
        edit_bottom=QHBoxLayout(); self.char_count=QLabel("0 ký tự"); self.editor_save_btn=QPushButton("💾  Lưu"); self.editor_save_btn.setObjectName("Primary")
        edit_bottom.addWidget(self.char_count); edit_bottom.addStretch(); edit_bottom.addWidget(self.editor_save_btn)
        el.addLayout(edit_bottom); rp.addWidget(edit_box)
        workspace.addWidget(right_panel)

        workspace.setSizes([275, 920, 315])
        page.addWidget(workspace,1)

        self.recovery_label=QLabel("")
        self.file_label=QLabel("Chưa mở JAR")
        self.setStatusBar(QStatusBar())
        self.statusBar().addWidget(self.file_label,1)
        self.statusBar().addPermanentWidget(self.recovery_label)
        self.statusBar().addPermanentWidget(QLabel("JAR Vietnamese Translator V4.6 JSON Protocol"))

        self.autosave_timer=QTimer(self); self.autosave_timer.setSingleShot(True); self.autosave_timer.setInterval(1500)
        self.autosave_timer.timeout.connect(self.perform_autosave)

        self.open_btn.clicked.connect(self.open_jar)
        self.scan_btn.clicked.connect(lambda: self.open_jar(self.result.jar_path) if self.result else None)
        self.open_project_btn.clicked.connect(self.open_project)
        self.save_project_btn.clicked.connect(self.save_project)
        self.import_csv_btn.clicked.connect(self.import_csv)
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.build_jar_btn.clicked.connect(self.build_vietnamese_jar)
        self.report_btn.clicked.connect(self.show_build_report)
        self.binary_btn.clicked.connect(self.analyze_selected_binary)
        self.compat_btn.clicked.connect(self.analyze_compatibility)
        self.glyph_btn.clicked.connect(self.analyze_glyphs)
        self.readiness_btn.clicked.connect(self.show_build_readiness)
        self.regression_btn.clicked.connect(self.run_regression_validation)
        self.runtime_btn.clicked.connect(self.create_runtime_test_package)
        self.log_btn.clicked.connect(self.analyze_runtime_log)
        self.settings_btn.clicked.connect(self.show_json_exchange_help)
        self.about_btn.clicked.connect(lambda: QMessageBox.information(self,"Giới thiệu","JAR Vietnamese Translator V4.6 JSON Protocol\nPrecision Scan · JSON Translation · Safe Patch · Rebuild JAR"))
        self.candidates.itemSelectionChanged.connect(self.show_selected_candidate)
        self.strings.itemSelectionChanged.connect(self.load_selected_string_editor)
        self.strings.itemChanged.connect(self.translation_edited)
        self.search_box.textChanged.connect(self.refresh_strings)
        self.status_filter.currentIndexChanged.connect(self.refresh_strings)
        self.source_filter.currentIndexChanged.connect(self.refresh_strings)
        self.copy_original_btn.clicked.connect(self.copy_original_to_translation)
        self.clear_translation_btn.clicked.connect(self.clear_selected_translation)
        self.editor_save_btn.clicked.connect(self.save_editor_translation)
        self.export_json_btn.clicked.connect(self.export_translation_json)
        self.import_json_btn.clicked.connect(self.import_translation_json)
        self.translation_edit.textChanged.connect(lambda: self.char_count.setText(f"{len(self.translation_edit.toPlainText())} ký tự"))

        QShortcut(QKeySequence.Save, self, activated=self.save_project)
        QShortcut(QKeySequence.Find, self, activated=self.search_box.setFocus)

        self._toolbar_full_labels = {
            self.open_btn:"📂  Mở JAR",
            self.scan_btn:"🔍  Quét ngôn ngữ",
            self.save_project_btn:"▣  Lưu dự án",
            self.open_project_btn:"📁  Mở dự án",
            self.import_csv_btn:"▤  Nhập CSV",
            self.export_csv_btn:"▥  Xuất CSV",
            self.binary_btn:"🧩  Phân tích Binary",
            self.compat_btn:"🔤  Encoding / Font",
            self.glyph_btn:"🔡  Kiểm tra Glyph",
            self.readiness_btn:"✅  Kiểm tra Build",
            self.regression_btn:"🧪  Kiểm tra JAR đầu ra",
            self.runtime_btn:"📦  Gói Runtime Test",
            self.log_btn:"🩺  Phân tích Log",
            self.export_json_btn:"⬆  Xuất JSON dịch",
            self.import_json_btn:"⬇  Nhập JSON dịch",
            self.build_jar_btn:"🫙  Build JAR tiếng Việt",
            self.report_btn:"▧  Báo cáo",
        }
        self._toolbar_short_labels = {
            self.open_btn:"📂 Mở JAR", self.scan_btn:"🔍 Quét", self.save_project_btn:"▣ Lưu",
            self.open_project_btn:"📁 Dự án", self.import_csv_btn:"▤ Nhập", self.export_csv_btn:"▥ Xuất",
            self.binary_btn:"🧩 Binary", self.compat_btn:"🔤 Font", self.glyph_btn:"🔡 Glyph",
            self.readiness_btn:"✅ Build", self.regression_btn:"🧪 JAR", self.runtime_btn:"📦 Runtime",
            self.log_btn:"🩺 Log", self.export_json_btn:"⬆ JSON", self.import_json_btn:"⬇ JSON",
            self.build_jar_btn:"🫙 Tạo JAR", self.report_btn:"▧ Báo cáo",
        }
        QTimer.singleShot(0, self.apply_responsive_layout)



    # ---------- V4.6 JSON Protocol UI ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toolbar_full_labels"):
            self.apply_responsive_layout()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.apply_responsive_layout)

    def apply_responsive_layout(self):
        """Adapt controls/panels to the actual window width without clipping."""
        w=max(1,self.centralWidget().width() if self.centralWidget() else self.width())
        h=max(1,self.centralWidget().height() if self.centralWidget() else self.height())

        compact = w < 1180
        very_compact = w < 980
        wide = w >= 1450

        # Header scales rather than forcing a desktop-only minimum.
        self.subtitle.setVisible(not very_compact)
        self.about_btn.setVisible(not very_compact)
        self.app_title.setStyleSheet(
            "font-size:18px;font-weight:700;color:#14284a;" if compact
            else "font-size:22px;font-weight:700;color:#14284a;"
        )

        # Toolbar wraps automatically. Short labels reduce excessive row count.
        labels=self._toolbar_short_labels if compact else self._toolbar_full_labels
        for btn,label in labels.items():
            btn.setText(label)
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed)
        if very_compact:
            # Secondary diagnostics remain available but consume less horizontal space.
            for btn in (self.binary_btn,self.compat_btn,self.glyph_btn,self.regression_btn,self.runtime_btn,self.log_btn):
                btn.setText(btn.text().split()[0])

        # Horizontal workspace ratios.
        if very_compact:
            left=max(170,int(w*0.19))
            right=max(220,int(w*0.25))
        elif compact:
            left=max(190,int(w*0.19))
            right=max(250,int(w*0.25))
        else:
            left=max(220,int(w*0.18))
            right=max(285,int(w*0.22))
        center=max(360,w-left-right-24)
        self.workspace.setSizes([left,center,right])

        # Vertical center split adapts to short laptop screens.
        usable=max(360,h-190)
        top=max(150,int(usable*(0.34 if h<760 else 0.38)))
        bottom=max(220,usable-top)
        self.center_splitter.setSizes([top,bottom])

        # Translation columns: metadata compact, content gets the space.
        header=self.strings.horizontalHeader()
        header.setSectionResizeMode(0,QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1,QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2,QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3,QHeaderView.Stretch)
        header.setSectionResizeMode(4,QHeaderView.Stretch)

        # Candidate table adapts file path column.
        ch=self.candidates.horizontalHeader()
        ch.setSectionResizeMode(0,QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(1,QHeaderView.Stretch)
        ch.setSectionResizeMode(2,QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(3,QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(4,QHeaderView.ResizeToContents)

        # Keep controls usable on 1366x768 / 1280x720 displays.
        self.original_edit.setMaximumHeight(58 if h<760 else 72)
        self.translation_edit.setMaximumHeight(72 if h<760 else 90)
        self.progress_bar.setMaximumWidth(120 if compact else 180)

    # ---------- Drag & drop ----------
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
        if self.project.dirty and self.result:
            self.perform_autosave()
        path = preset_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open Java JAR", "", "Java archive (*.jar);;All files (*)")
        if not path: return
        self.file_label.setText(f"Đã mở: {Path(path).name}")
        self.statusBar().showMessage("Scanning JAR...")
        self.open_btn.setEnabled(False)
        self.worker = ScanWorker(path)
        self.worker.finished_result.connect(self.scan_complete)
        self.worker.failed.connect(self.scan_failed)
        self.worker.start()

    def scan_failed(self, message):
        self.open_btn.setEnabled(True)
        self.statusBar().showMessage("Scan failed")
        QMessageBox.critical(self, "Scan error", message)

    def scan_complete(self, result):
        self.result = result
        if not self.project.jar_path:
            self.project = TranslationProject(jar_path=result.jar_path)
        else:
            self.project.jar_path = result.jar_path
        self.open_btn.setEnabled(True)
        for b in (self.save_project_btn, self.import_csv_btn, self.export_csv_btn, self.build_jar_btn): b.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.binary_btn.setEnabled(True)
        self.compat_btn.setEnabled(True)
        self.glyph_btn.setEnabled(True)
        self.readiness_btn.setEnabled(True)
        self.log_btn.setEnabled(True)
        self.export_json_btn.setEnabled(True)
        self.import_json_btn.setEnabled(True)
        self.copy_original_btn.setEnabled(True); self.clear_translation_btn.setEnabled(True)
        self.populate_tree(); self.populate_candidates(); self.update_progress()
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
        self.check_recovery_snapshot()

    # ---------- Views ----------
    def populate_tree(self):
        self.tree.clear(); nodes = {}
        for entry in self.result.entries:
            parent = self.tree.invisibleRootItem(); current = ""
            for part in entry.split("/"):
                current = f"{current}/{part}" if current else part
                if current not in nodes:
                    item = QTreeWidgetItem([part]); parent.addChild(item); nodes[current] = item
                parent = nodes[current]
        self.tree.expandToDepth(1)

    def populate_candidates(self):
        self.candidates.setRowCount(len(self.result.candidates))
        self.source_filter.blockSignals(True)
        self.source_filter.clear(); self.source_filter.addItem("Tất cả nguồn")
        for row, c in enumerate(self.result.candidates):
            vals = [str(row + 1), c.source, c.source_type, str(len(c.strings)), f"{c.score}%"]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col in (0,3,4): item.setTextAlignment(Qt.AlignCenter)
                self.candidates.setItem(row, col, item)
            self.source_filter.addItem(c.source)
        self.source_filter.blockSignals(False)
        if self.result.candidates:
            self.candidates.selectRow(0)

    def show_selected_candidate(self):
        rows = self.candidates.selectionModel().selectedRows()
        if not rows or not self.result: return
        self.current_candidate = self.result.candidates[rows[0].row()]
        c=self.current_candidate
        self.info_path.setText(c.source)
        self.info_type.setText(c.source_type)
        self.info_count.setText(str(len(c.strings)))
        self.info_score.setText(f"{c.score}%")
        self.info_status.setText("Rất cao" if c.score >= 80 else "Cao" if c.score >= 60 else "Trung bình" if c.score >= 35 else "Thấp")
        preview=[
            f"Source: {c.source}",
            f"Loại: {c.source_type}",
            f"Điểm: {c.score}%",
            f"Số chuỗi: {len(c.strings)}",
        ]
        if c.reasons:
            preview += ["","Lý do nhận diện:"] + [f"- {x}" for x in c.reasons]
        if any(s.kind.startswith("deep-") for s in c.strings):
            preview += [
                "",
                "⚠ Deep Scan discovery-only / Precision-filtered",
                "Các chuỗi deep-* được phát hiện trong format chưa xác định.",
                "App sẽ hiển thị để dịch/phân tích nhưng Safe Build chưa patch loại này cho đến khi biết chính xác cấu trúc resource."
            ]
        preview += ["","Chuỗi:"] + [f"{i+1}. {s.value}" for i,s in enumerate(c.strings[:120])]
        self.details.setPlainText("\n".join(preview))
        self.refresh_strings()

    def refresh_strings(self):
        if not self.current_candidate:
            self.strings.setRowCount(0)
            return
        query = self.search_box.text().strip().lower()
        mode = self.status_filter.currentText()
        source_mode = self.source_filter.currentText()
        self.visible_strings = []
        for s in self.current_candidate.strings:
            vi = self.project.get(s.key)
            translated = bool(vi.strip())
            if mode == "Đã dịch" and not translated: continue
            if mode == "Chưa dịch" and translated: continue
            if source_mode != "Tất cả nguồn" and s.source != source_mode: continue
            if query and query not in s.value.lower() and query not in vi.lower() and query not in s.source.lower(): continue
            self.visible_strings.append(s)

        self._updating_table = True
        self.strings.setRowCount(len(self.visible_strings))
        translated_brush = QBrush(QColor(220, 247, 223))
        untranslated_brush = QBrush(QColor(255, 245, 204))
        for row, s in enumerate(self.visible_strings):
            vi = self.project.get(s.key)
            status = "✓" if vi else "—"
            vals = [status, s.kind, str(s.index), s.value, vi]
            brush = translated_brush if vi else untranslated_brush
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col in (0,1,2): item.setTextAlignment(Qt.AlignCenter)
                if col != 4: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, s.key)
                item.setBackground(brush)
                self.strings.setItem(row, col, item)
        self._updating_table = False

    def _paint_row(self, row, translated):
        brush = QBrush(QColor(220, 247, 223) if translated else QColor(255, 245, 204))
        for col in range(self.strings.columnCount()):
            item = self.strings.item(row, col)
            if item:
                item.setBackground(brush)

    # ---------- Translation editing ----------
    def translation_edited(self, item):
        if self._updating_table or item.column() != 4: return
        row = item.row()
        if row >= len(self.visible_strings): return
        s = self.visible_strings[row]
        self.project.set(s.key, item.text())
        translated = bool(item.text().strip())
        self._updating_table = True
        self.strings.item(row, 0).setText("✓" if translated else "—")
        self._paint_row(row, translated)
        self._updating_table = False
        self.update_progress(); self.schedule_autosave()

    def selected_rows(self):
        return sorted({idx.row() for idx in self.strings.selectionModel().selectedRows()})

    def copy_original_to_translation(self):
        rows = self.selected_rows()
        if not rows: return
        self._updating_table = True
        for row in rows:
            s = self.visible_strings[row]
            self.project.set(s.key, s.value)
            self.strings.item(row, 4).setText(s.value)
            self.strings.item(row, 0).setText("✓")
            self._paint_row(row, True)
        self._updating_table = False
        self.update_progress(); self.schedule_autosave()

    def clear_selected_translation(self):
        rows = self.selected_rows()
        if not rows: return
        self._updating_table = True
        for row in rows:
            s = self.visible_strings[row]
            self.project.set(s.key, "")
            self.strings.item(row, 4).setText("")
            self.strings.item(row, 0).setText("—")
            self._paint_row(row, False)
        self._updating_table = False
        self.update_progress(); self.schedule_autosave()

    # ---------- Progress/autosave ----------
    def update_progress(self):
        if not self.result:
            self.progress_label.setText("Translation progress: 0 / 0 (0%)")
            self.progress_bar.setValue(0); return
        total, translated = self.project.stats(self.result)
        pct = int(round(translated * 100 / total)) if total else 0
        self.progress_label.setText(f"Translation progress: {translated} / {total} ({pct}%)")
        self.progress_bar.setValue(pct)
        marker = " *" if self.project.dirty else ""
        self.setWindowTitle(f"JAR Vietnamese Translator V4.6 JSON Protocol{marker}")

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
        path = self.recovery_path()
        if not path:
            return
        try:
            self.project.autosave(str(path), self.result)
            self.recovery_label.setText("Recovery: saved")
            self.statusBar().showMessage(f"Autosaved recovery snapshot: {path}", 3000)
        except Exception as e:
            self.recovery_label.setText("Recovery: failed")
            self.statusBar().showMessage(f"Autosave failed: {e}", 5000)

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
            "V4.6 nhúng rules bắt buộc, output contract, checksum JAR, checksum original và placeholder manifest để giảm lỗi import."
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
                "JSON Translation Exchange V4.6\n\n"
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

        try:
            report=self.translation_exchange.import_file(
                path,self.result,self.project,overwrite=overwrite
            )
            self.refresh_strings()
            self.update_progress()
            self.schedule_autosave()

            lines=[
                "JSON Translation Import V4.6",
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
            ]
            if report.warnings:
                lines += ["","Warnings:"]+[f"- {x}" for x in report.warnings[:200]]
            self.details.setPlainText("\n".join(lines))

            QMessageBox.information(
                self,"Nhập JSON hoàn tất",
                f"Đã nhập: {report.imported}\n"
                f"Bỏ qua bản dịch cũ: {report.skipped_existing}\n"
                f"Bị từ chối: {report.rejected_total}\n\n"
                "Các dòng đã nhập nằm trong project để bạn kiểm tra trước khi Build."
            )
        except Exception as e:
            QMessageBox.critical(self,"Nhập JSON",str(e))

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
                "Runtime Log Analyzer V4.6 JSON Protocol",
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
                notes="Generated by JAR Vietnamese Translator V4.6 JSON Protocol"
            )

            lines=[
                "Runtime Test Package V4.6 JSON Protocol",
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
                "Test Build & Regression Validator V4.6 JSON Protocol",
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
                "Translation Validation & Build Readiness V4.6 JSON Protocol",
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
                "Font / Glyph Analyzer V4.6 JSON Protocol",
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
                "Encoding & Font Compatibility Analyzer V4.6 JSON Protocol",
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
            self.original_edit.clear(); self.translation_edit.clear(); return
        row=rows[0].row()
        if row >= len(self.visible_strings): return
        s=self.visible_strings[row]
        self.original_edit.setPlainText(s.value)
        self.translation_edit.blockSignals(True)
        self.translation_edit.setPlainText(self.project.get(s.key))
        self.translation_edit.blockSignals(False)
        self.char_count.setText(f"{len(self.translation_edit.toPlainText())} ký tự")

    def save_editor_translation(self):
        rows=self.strings.selectionModel().selectedRows()
        if not rows: return
        row=rows[0].row()
        if row >= len(self.visible_strings): return
        s=self.visible_strings[row]
        value=self.translation_edit.toPlainText()
        self.project.set(s.key,value)
        self._updating_table=True
        self.strings.item(row,4).setText(value)
        self.strings.item(row,0).setText("✓" if value.strip() else "—")
        self._paint_row(row,bool(value.strip()))
        self._updating_table=False
        self.update_progress(); self.schedule_autosave()

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

    # ---------- V3 Safe Build / Patch ----------
    def build_vietnamese_jar(self):
        if not self.result:
            return
        total, translated = self.project.stats(self.result)
        if translated == 0:
            QMessageBox.information(self, "Nothing to build", "There are no Vietnamese translations yet.")
            return

        # V3.6 unified build-readiness gate
        try:
            ready = BuildReadinessAnalyzer().analyze(self.result, self.project)
            if ready.status == "BLOCKED":
                details="\n".join(f"- {i.message}" for i in ready.issues if i.level=="BLOCKED")
                QMessageBox.critical(
                    self,"Build blocked",
                    "Build Readiness = BLOCKED.\n\n" + details + "\n\nHãy xử lý các mục trên trước khi build."
                )
                return
            if ready.status == "WARNING":
                warnings="\n".join(f"- {i.message}" for i in ready.issues if i.level=="WARNING")
                if len(warnings)>900:
                    warnings=warnings[:900]+"..."
                ans=QMessageBox.warning(
                    self,"Build readiness warning",
                    "Build Readiness = WARNING.\n\n" + warnings +
                    "\n\nBạn vẫn có thể build để kiểm thử trên emulator/device. Tiếp tục?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if ans != QMessageBox.Yes:
                    return
        except Exception as e:
            QMessageBox.warning(self,"Build readiness",f"Không thể hoàn tất readiness check: {e}")
            return

        # V3.5 glyph pre-check
        try:
            glyph = GlyphAnalyzer().analyze(self.result.jar_path, self.result, self.project)
            if glyph.maps and glyph.missing_chars:
                chars=" ".join(sorted(glyph.missing_chars, key=lambda c: ord(c)))
                if len(chars) > 180:
                    chars=chars[:180] + "..."
                ans = QMessageBox.warning(
                    self, "Missing font glyphs",
                    f"Font/Glyph Analyzer phát hiện {len(glyph.missing_chars)} ký tự cần dùng nhưng không có trong font map.\n\n"
                    f"Thiếu: {chars}\n\n"
                    "JAR vẫn có thể build, nhưng các ký tự này có nguy cơ hiển thị ô vuông/trống.\n\nTiếp tục?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if ans != QMessageBox.Yes:
                    return
        except Exception:
            pass

        # V3.4 compatibility pre-check
        try:
            compat = CompatibilityAnalyzer().analyze(self.result.jar_path, self.result, self.project)
            if compat.overall_risk == "high":
                ans = QMessageBox.warning(
                    self, "Compatibility warning",
                    "Encoding/Font Analyzer đánh giá mức rủi ro HIGH.\n\n"
                    "Nguyên nhân thường là custom/bitmap font hoặc encoding không chứa được tiếng Việt.\n"
                    "Bạn vẫn có thể build để test trên emulator/device.\n\nTiếp tục?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ans != QMessageBox.Yes:
                    return
        except Exception:
            pass

        source = Path(self.result.jar_path)
        default = str(source.with_name(source.stem + "_vietnamese.jar"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Build Vietnamese JAR", default, "Java archive (*.jar)")
        if not path:
            return
        if not path.lower().endswith(".jar"):
            path += ".jar"

        answer = QMessageBox.question(
            self, "Safe Build",
            "Safe Build will patch translated String constants in .class files and supported text resources.\n\n"
            "Unknown binary resources (.dat/.bin/.res) are NOT patched because changing byte length can corrupt game data.\n"
            "The source JAR will not be modified.\n\nBuild now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return

        self.build_jar_btn.setEnabled(False)
        self.statusBar().showMessage("Building Vietnamese JAR...")
        try:
            report = JarBuilder().build(self.result, self.project, path)
            report_path = str(Path(path).with_suffix(".build-report.json"))
            report.save_json(report_path)

            summary = (
                f"Output: {path}\n\n"
                f"Patched: {report.patched}\n"
                f"Skipped: {report.skipped}\n"
                f"Failed: {report.failed}\n"
                f"Entries written: {report.entries_written}\n"
                f"Validation: {'PASS' if report.validation_ok else 'FAILED'}\n\n"
                f"Build report: {report_path}"
            )
            if report.warnings:
                summary += "\n\nWarnings:\n- " + "\n- ".join(report.warnings[:10])
            if report.validation_ok and report.failed == 0:
                QMessageBox.information(self, "Build complete", summary)
            else:
                QMessageBox.warning(self, "Build completed with warnings", summary)
            self.report_btn.setEnabled(True)
            self.regression_btn.setEnabled(True)
            self.runtime_btn.setEnabled(True)
            self.statusBar().showMessage(
                f"Build complete: patched {report.patched}, skipped {report.skipped}, failed {report.failed}", 8000)
        except Exception as e:
            QMessageBox.critical(self, "Build error", str(e))
            self.statusBar().showMessage(f"Build failed: {e}", 8000)
        finally:
            self.build_jar_btn.setEnabled(True)

