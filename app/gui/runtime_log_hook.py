from __future__ import annotations

# Portable hook intentionally mirrors the development hook semantically.
from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QGridLayout, QLabel, QPushButton
from core.runtime_log_correlator import correlate_runtime_log, format_runtime_log_correlation, load_log
from core.runtime_exception_timeline import build_exception_timeline, format_exception_timeline
from core.runtime_diagnosis_summary import (
    build_runtime_diagnosis_summary,
    format_runtime_diagnosis_summary,
    write_runtime_diagnosis_summary,
)
from core.diagnostic_bundle import export_diagnostic_bundle, export_diagnostic_bundle_zip


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
        self._runtime_diagnosis_summary = None
        self._runtime_diagnosis_log_path = None

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

        self.runtime_log_copy_btn = QPushButton("Copy runtime diagnosis")
        self.runtime_log_copy_btn.setEnabled(False)
        self.runtime_log_copy_btn.clicked.connect(self._copy_runtime_diagnosis)
        grid.addWidget(self.runtime_log_copy_btn, 2, 0)

        self.runtime_log_export_btn = QPushButton("Export diagnosis TXT")
        self.runtime_log_export_btn.setEnabled(False)
        self.runtime_log_export_btn.clicked.connect(self._export_runtime_diagnosis)
        grid.addWidget(self.runtime_log_export_btn, 2, 1)

        self.runtime_bundle_export_btn = QPushButton("Export Diagnostic Bundle")
        self.runtime_bundle_export_btn.setEnabled(False)
        self.runtime_bundle_export_btn.clicked.connect(self._export_diagnostic_bundle)
        grid.addWidget(self.runtime_bundle_export_btn, 3, 0)

        self.runtime_bundle_zip_btn = QPushButton("Export Bundle ZIP")
        self.runtime_bundle_zip_btn.setEnabled(False)
        self.runtime_bundle_zip_btn.clicked.connect(self._export_diagnostic_bundle_zip)
        grid.addWidget(self.runtime_bundle_zip_btn, 3, 1)

        self.runtime_log_value = QLabel("Chọn file .log/.txt để phân tích lỗi runtime.")
        self.runtime_log_value.setObjectName("Muted")
        self.runtime_log_value.setWordWrap(True)
        grid.addWidget(self.runtime_log_value, 4, 0, 1, 2)
        self.runtime_log_card = card
        layout = self.right_panel.layout()
        layout.insertWidget(max(0, layout.count() - 2), card)

    def _set_runtime_export_controls(self, enabled):
        self.runtime_log_copy_btn.setEnabled(enabled)
        self.runtime_log_export_btn.setEnabled(enabled)
        self.runtime_bundle_export_btn.setEnabled(enabled)
        self.runtime_bundle_zip_btn.setEnabled(enabled)

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
            summary = build_runtime_diagnosis_summary(selected, result, timeline)
            self._runtime_diagnosis_summary = summary
            self._runtime_diagnosis_log_path = selected
            self._set_runtime_export_controls(True)

            text = (
                format_runtime_diagnosis_summary(summary)
                + "\n\n"
                + format_runtime_log_correlation(result)
                + "\n\n"
                + format_exception_timeline(timeline)
            )
            self.runtime_log_value.setText(text)
            primary = timeline.primary
            if primary is not None:
                self.statusBar().showMessage(f"Priority failure: {primary.error_type}", 9000)
            else:
                self.statusBar().showMessage(result.probable_cause, 9000)
        except Exception as exc:
            self._runtime_diagnosis_summary = None
            self._runtime_diagnosis_log_path = None
            self._set_runtime_export_controls(False)
            self.runtime_log_value.setText(f"Không thể phân tích log: {exc}")

    def _copy_runtime_diagnosis(self):
        summary = getattr(self, "_runtime_diagnosis_summary", None)
        if summary is None:
            return
        QApplication.clipboard().setText(format_runtime_diagnosis_summary(summary))
        self.statusBar().showMessage("Đã copy runtime diagnosis summary", 6000)

    def _export_runtime_diagnosis(self):
        summary = getattr(self, "_runtime_diagnosis_summary", None)
        log_path = getattr(self, "_runtime_diagnosis_log_path", None)
        if summary is None or not log_path:
            return
        try:
            target = write_runtime_diagnosis_summary(log_path, summary)
            self.statusBar().showMessage(f"Đã xuất runtime diagnosis: {target.name}", 8000)
        except Exception as exc:
            self.runtime_log_value.setText(f"Không thể xuất diagnosis: {exc}")

    def _export_diagnostic_bundle(self):
        summary = getattr(self, "_runtime_diagnosis_summary", None)
        log_path = getattr(self, "_runtime_diagnosis_log_path", None)
        if summary is None or not log_path:
            return
        output_parent = QFileDialog.getExistingDirectory(self, "Export Diagnostic Bundle")
        if not output_parent:
            return
        try:
            result = export_diagnostic_bundle(
                output_parent,
                log_path,
                summary,
                getattr(self, "_runtime_compat_export", None),
            )
            self.statusBar().showMessage(f"Đã xuất diagnostic bundle: {result.directory.name}", 9000)
        except Exception as exc:
            self.runtime_log_value.setText(f"Không thể xuất diagnostic bundle: {exc}")

    def _export_diagnostic_bundle_zip(self):
        summary = getattr(self, "_runtime_diagnosis_summary", None)
        log_path = getattr(self, "_runtime_diagnosis_log_path", None)
        if summary is None or not log_path:
            return
        output_parent = QFileDialog.getExistingDirectory(self, "Export Diagnostic Bundle ZIP")
        if not output_parent:
            return
        try:
            result = export_diagnostic_bundle_zip(
                output_parent,
                log_path,
                summary,
                getattr(self, "_runtime_compat_export", None),
            )
            self.statusBar().showMessage(f"Đã xuất diagnostic ZIP: {result.zip_path.name}", 9000)
        except Exception as exc:
            self.runtime_log_value.setText(f"Không thể xuất diagnostic ZIP: {exc}")

    MainWindow.__init__ = hooked_init
    MainWindow._analyze_runtime_log = _analyze_runtime_log
    MainWindow._set_runtime_export_controls = _set_runtime_export_controls
    MainWindow._copy_runtime_diagnosis = _copy_runtime_diagnosis
    MainWindow._export_runtime_diagnosis = _export_runtime_diagnosis
    MainWindow._export_diagnostic_bundle = _export_diagnostic_bundle
    MainWindow._export_diagnostic_bundle_zip = _export_diagnostic_bundle_zip
    return MainWindow
