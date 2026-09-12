from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from core.compatibility_analyzer import CompatibilityAnalyzer
from core.runtime_compat_presenter import summarize_runtime
from core.activation_flow_analyzer import ActivationFlowAnalyzer
from core.dependency_path_presenter import summarize_dependency_path
from core.startup_blocking_assessment import assess_startup_blocking
from core.compatibility_report import CompatibilityReportExporter


class RuntimeCompatibilityWorker(QThread):
    completed = Signal(object, object, object)
    failed = Signal(str)

    def __init__(self, jar_path, result, project):
        super().__init__()
        self.jar_path = jar_path
        self.result = result
        self.project = project

    def run(self):
        try:
            report = CompatibilityAnalyzer().analyze(
                self.jar_path, self.result, self.project
            )
            activation = ActivationFlowAnalyzer().analyze(self.jar_path)
            self.completed.emit(report, summarize_runtime(report.runtime), activation)
        except Exception as exc:
            self.failed.emit(str(exc))


def _risk_text(risk: str) -> str:
    return {
        "low": "LOW · phù hợp",
        "medium": "MEDIUM · cần kiểm thử",
        "high": "HIGH · có API rủi ro",
    }.get((risk or "unknown").lower(), str(risk or "UNKNOWN").upper())


def _activation_text(report) -> str:
    labels = []
    if report.likely_activation_gate:
        labels.append("activation gate")
    if report.likely_payment_flow:
        labels.append("payment/subscription")
    if report.wma_linked:
        labels.append("liên kết WMA/SMS")
    if not labels:
        return "Không thấy flow kích hoạt/thanh toán mạnh"
    suffix = f" · {len(report.suspicious_classes)} class nghi vấn" if report.suspicious_classes else ""
    return f"{report.risk.upper()} · " + ", ".join(labels) + suffix


def _diagnostic_summary(export) -> str:
    top = export.recommended_actions[0] if export.recommended_actions else None
    path = " -> ".join(export.startup_path) if export.startup_path else "not found"
    detected = ", ".join(export.detected_apis) or "none"
    unsupported = ", ".join(export.unsupported_apis) or "none"
    conditional = ", ".join(export.conditional_apis) or "none"
    lines = [
        "JAR RG35XX DIAGNOSTIC SUMMARY",
        f"JAR: {export.jar_name}",
        f"Target: {export.target}",
        f"Runtime: {export.compatibility_score}/100 · {export.runtime_risk.upper()}",
        f"Assessment: {export.startup_title} · {export.startup_severity.upper()}",
        f"Detected APIs: {detected}",
        f"Unsupported APIs: {unsupported}",
        f"Conditional APIs: {conditional}",
        f"Startup path: {path}",
    ]
    if top:
        lines.append(
            f"Next action: P{top['priority']} · {top['title']} · {top['detail']}"
        )
    lines.append(export.diagnostic_note)
    return "\n".join(lines)


def install_runtime_compatibility(MainWindow):
    """Attach RG35XX runtime UI without inflating the main-window controller file."""
    if getattr(MainWindow, "_runtime_compat_hook_installed", False):
        return MainWindow
    MainWindow._runtime_compat_hook_installed = True

    original_init = MainWindow.__init__
    original_scan_complete = MainWindow.scan_complete

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._runtime_compat_worker = None
        self._runtime_compat_report = None
        self._activation_flow_report = None
        self._startup_blocking_assessment = None
        self._runtime_compat_export = None

        card = QFrame()
        card.setObjectName("InnerCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 9, 10, 9)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        title = QLabel("FreeJ2ME / RG35XX Compatibility")
        title.setObjectName("PanelTitle")
        grid.addWidget(title, 0, 0, 1, 2)

        self.runtime_target_value = QLabel("FreeJ2ME / RG35XX")
        self.runtime_score_value = QLabel("—")
        self.runtime_risk_value = QLabel("Chưa phân tích")
        self.runtime_api_value = QLabel("—")
        self.runtime_wma_value = QLabel("—")
        self.runtime_activation_value = QLabel("—")
        self.runtime_startup_path_value = QLabel("—")
        self.runtime_blocker_value = QLabel("—")
        self.runtime_next_action_value = QLabel("—")
        for widget in (
            self.runtime_api_value,
            self.runtime_wma_value,
            self.runtime_activation_value,
            self.runtime_startup_path_value,
            self.runtime_blocker_value,
            self.runtime_next_action_value,
        ):
            widget.setWordWrap(True)

        rows = [
            ("Target:", self.runtime_target_value),
            ("Score:", self.runtime_score_value),
            ("Risk:", self.runtime_risk_value),
            ("API:", self.runtime_api_value),
            ("WMA/SMS:", self.runtime_wma_value),
            ("Activation:", self.runtime_activation_value),
            ("Startup path:", self.runtime_startup_path_value),
            ("Assessment:", self.runtime_blocker_value),
            ("Next action:", self.runtime_next_action_value),
        ]
        for row, (label, widget) in enumerate(rows, start=1):
            key = QLabel(label)
            key.setObjectName("Muted")
            grid.addWidget(key, row, 0)
            grid.addWidget(widget, row, 1)

        button_row = len(rows) + 1
        self.runtime_export_btn = QPushButton("Xuất report JSON + TXT")
        self.runtime_export_btn.setEnabled(False)
        self.runtime_export_btn.clicked.connect(self._export_runtime_compat_report)
        grid.addWidget(self.runtime_export_btn, button_row, 0, 1, 2)

        self.runtime_copy_btn = QPushButton("Copy diagnostic summary")
        self.runtime_copy_btn.setEnabled(False)
        self.runtime_copy_btn.clicked.connect(self._copy_runtime_compat_summary)
        grid.addWidget(self.runtime_copy_btn, button_row + 1, 0, 1, 2)

        self.runtime_compat_card = card
        right_layout = self.right_panel.layout()
        insert_at = max(0, right_layout.count() - 2)
        right_layout.insertWidget(insert_at, card)

    def _runtime_compat_set_pending(self):
        self.runtime_export_btn.setEnabled(False)
        self.runtime_copy_btn.setEnabled(False)
        self._runtime_compat_export = None
        self.runtime_score_value.setText("…")
        self.runtime_risk_value.setText("Đang phân tích")
        self.runtime_api_value.setText("Đang quét bytecode / optional API…")
        self.runtime_wma_value.setText("Đang kiểm tra WMA / SMS…")
        self.runtime_activation_value.setText("Đang kiểm tra activation/payment flow…")
        self.runtime_startup_path_value.setText("Đang dựng dependency graph từ MIDlet entry…")
        self.runtime_blocker_value.setText("Đang tổng hợp mức ảnh hưởng tới startup…")
        self.runtime_next_action_value.setText("Đang xác định bước kiểm tra ưu tiên…")

    def _runtime_compat_start(self):
        if not self.result:
            return
        worker = getattr(self, "_runtime_compat_worker", None)
        if worker is not None and worker.isRunning():
            return
        _runtime_compat_set_pending(self)
        worker = RuntimeCompatibilityWorker(
            self.result.jar_path, self.result, self.project
        )
        self._runtime_compat_worker = worker
        worker.completed.connect(self._runtime_compat_done)
        worker.failed.connect(self._runtime_compat_failed)
        worker.finished.connect(lambda w=worker: self._runtime_compat_release(w))
        worker.start()

    def _runtime_compat_done(self, report, summary, activation):
        self._runtime_compat_report = report
        self._activation_flow_report = activation
        assessment = assess_startup_blocking(report.runtime, activation)
        self._startup_blocking_assessment = assessment
        export = CompatibilityReportExporter().build(
            str(self.result.jar_path), report.runtime, activation
        )
        self._runtime_compat_export = export

        self.runtime_target_value.setText(summary.target)
        self.runtime_score_value.setText(f"{summary.score}/100")
        self.runtime_risk_value.setText(_risk_text(summary.risk))

        detected = ", ".join(summary.detected_apis) or "Không phát hiện optional/vendor API"
        self.runtime_api_value.setText(detected)

        if summary.uses_wma_sms:
            targets = ", ".join(summary.sms_targets) or "không thấy endpoint cố định"
            self.runtime_wma_value.setText("DETECTED · chặn SMS thật · " + targets)
        else:
            self.runtime_wma_value.setText("Không phát hiện")

        self.runtime_activation_value.setText(_activation_text(activation))
        self.runtime_startup_path_value.setText(summarize_dependency_path(activation))
        reason_preview = "; ".join(assessment.reasons[:2])
        self.runtime_blocker_value.setText(
            assessment.title + ((" · " + reason_preview) if reason_preview else "")
        )

        if export.recommended_actions:
            top = export.recommended_actions[0]
            self.runtime_next_action_value.setText(
                f"P{top['priority']} · {top['title']} · {top['detail']}"
            )
        else:
            self.runtime_next_action_value.setText("Chưa có action ưu tiên")

        level = (summary.risk or "low").lower()
        if level == "high":
            self.runtime_risk_value.setStyleSheet("color:#DC2626; font-weight:700;")
        elif level == "medium":
            self.runtime_risk_value.setStyleSheet("color:#D97706; font-weight:700;")
        else:
            self.runtime_risk_value.setStyleSheet("color:#059669; font-weight:700;")

        activation_level = (activation.risk or "low").lower()
        if activation_level == "high":
            self.runtime_activation_value.setStyleSheet("color:#DC2626; font-weight:700;")
        elif activation_level == "medium":
            self.runtime_activation_value.setStyleSheet("color:#D97706; font-weight:600;")
        else:
            self.runtime_activation_value.setStyleSheet("color:#059669;")

        if activation.startup_activation_reachable:
            self.runtime_startup_path_value.setStyleSheet("color:#DC2626; font-weight:600;")
        else:
            self.runtime_startup_path_value.setStyleSheet("")

        if assessment.severity == "high":
            self.runtime_blocker_value.setStyleSheet("color:#DC2626; font-weight:700;")
            self.runtime_next_action_value.setStyleSheet("color:#DC2626; font-weight:700;")
        elif assessment.severity == "medium":
            self.runtime_blocker_value.setStyleSheet("color:#D97706; font-weight:700;")
            self.runtime_next_action_value.setStyleSheet("color:#D97706; font-weight:700;")
        else:
            self.runtime_blocker_value.setStyleSheet("color:#059669; font-weight:600;")
            self.runtime_next_action_value.setStyleSheet("color:#059669; font-weight:600;")

        self.runtime_export_btn.setEnabled(True)
        self.runtime_copy_btn.setEnabled(True)
        self.statusBar().showMessage(
            f"RG35XX: {summary.score}/100 · {summary.risk.upper()} · {assessment.title}",
            9000,
        )

    def _export_runtime_compat_report(self):
        export = getattr(self, "_runtime_compat_export", None)
        if export is None or not self.result:
            return
        jar_path = Path(self.result.jar_path)
        default_base = str(jar_path.with_name(jar_path.stem + "_compatibility_report"))
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất Compatibility Report",
            default_base,
            "Compatibility report (*.compat.json);;Tất cả file (*)",
        )
        if not selected:
            return
        try:
            json_path, txt_path = CompatibilityReportExporter().write_pair(selected, export)
            self.statusBar().showMessage(
                f"Đã xuất report: {json_path.name} + {txt_path.name}", 9000
            )
        except Exception as exc:
            QMessageBox.warning(self, "Xuất report", f"Không thể xuất report:\n{exc}")

    def _copy_runtime_compat_summary(self):
        export = getattr(self, "_runtime_compat_export", None)
        if export is None:
            return
        QApplication.clipboard().setText(_diagnostic_summary(export))
        self.statusBar().showMessage("Đã copy diagnostic summary vào clipboard", 6000)

    def _runtime_compat_failed(self, message):
        self.runtime_export_btn.setEnabled(False)
        self.runtime_copy_btn.setEnabled(False)
        self._runtime_compat_export = None
        self.runtime_score_value.setText("—")
        self.runtime_risk_value.setText("Không phân tích được")
        self.runtime_api_value.setText(message)
        self.runtime_wma_value.setText("—")
        self.runtime_activation_value.setText("—")
        self.runtime_startup_path_value.setText("—")
        self.runtime_blocker_value.setText("—")
        self.runtime_next_action_value.setText("—")

    def _runtime_compat_release(self, worker):
        if getattr(self, "_runtime_compat_worker", None) is worker:
            self._runtime_compat_worker = None
        worker.deleteLater()

    def hooked_scan_complete(self, result):
        original_scan_complete(self, result)
        _runtime_compat_start(self)

    MainWindow.__init__ = hooked_init
    MainWindow.scan_complete = hooked_scan_complete
    MainWindow._start_runtime_compat_scan = _runtime_compat_start
    MainWindow._runtime_compat_done = _runtime_compat_done
    MainWindow._runtime_compat_failed = _runtime_compat_failed
    MainWindow._runtime_compat_release = _runtime_compat_release
    MainWindow._export_runtime_compat_report = _export_runtime_compat_report
    MainWindow._copy_runtime_compat_summary = _copy_runtime_compat_summary
    return MainWindow
