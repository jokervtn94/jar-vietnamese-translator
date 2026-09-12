from __future__ import annotations

# Portable hook intentionally mirrors the development hook semantically.
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QLabel, QPushButton
from core.runtime_log_correlator import correlate_runtime_log, format_runtime_log_correlation, load_log
from core.runtime_exception_timeline import build_exception_timeline, format_exception_timeline


def _report_value(report, name, default=None):
    if report is None:
        return default
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def install_runtime_log_analysis(MainWindow):
    if getattr(MainWindow, "_runtime_log_hook_installed", False):
        return MainWindow
    MainWindow._runtime_log_hook_installed = True
    original_init = MainWindow.__init__

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        card = QFrame()
        card.setObjectName("InnerCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 9, 10, 9)
        title = QLabel("Runtime Log Diagnostic")
        title.setObjectName("PanelTitle")
        grid.addWidget(title, 0, 0, 1, 2)
        self.runtime_log_btn = QPushButton("Open log file")
        self.runtime_log_btn.clicked.connect(self._analyze_runtime_log)
        grid.addWidget(self.runtime_log_btn, 1, 0, 1, 2)
        self.runtime_log_value = QLabel("Chọn file .log/.txt để phân tích lỗi runtime.")
        self.runtime_log_value.setObjectName("Muted")
        self.runtime_log_value.setWordWrap(True)
        grid.addWidget(self.runtime_log_value, 2, 0, 1, 2)
        self.runtime_log_card = card
        layout = self.right_panel.layout()
        layout.insertWidget(max(0, layout.count() - 2), card)

    def _analyze_runtime_log(self):
        selected, _ = QFileDialog.getOpenFileName(self, "Open runtime log", "", "Log files (*.log *.txt);;All files (*)")
        if not selected:
            return
        try:
            report = getattr(self, "_runtime_compat_export", None)
            log_text = load_log(selected)
            result = correlate_runtime_log(log_text, report)
            timeline = build_exception_timeline(
                log_text,
                startup_path=_report_value(report, "startup_path", []) or [],
                matched_apis=result.matched_apis,
            )
            text = format_runtime_log_correlation(result) + "\n\n" + format_exception_timeline(timeline)
            self.runtime_log_value.setText(text)
            primary = timeline.primary
            if primary is not None:
                self.statusBar().showMessage(f"Priority failure: {primary.error_type}", 9000)
            else:
                self.statusBar().showMessage(result.probable_cause, 9000)
        except Exception as exc:
            self.runtime_log_value.setText(f"Không thể phân tích log: {exc}")

    MainWindow.__init__ = hooked_init
    MainWindow._analyze_runtime_log = _analyze_runtime_log
    return MainWindow
