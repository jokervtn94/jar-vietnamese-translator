from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QLabel, QMessageBox, QPushButton

from core.diagnostic_compare import compare_reports, format_comparison, load_report
from core.diagnostic_verdict import build_compare_verdict, format_compare_verdict


def install_diagnostic_compare(MainWindow):
    """Add report-to-report comparison without expanding the main runtime hook."""
    if getattr(MainWindow, "_diagnostic_compare_hook_installed", False):
        return MainWindow
    MainWindow._diagnostic_compare_hook_installed = True

    original_init = MainWindow.__init__
    original_history_refresh = getattr(MainWindow, "_runtime_history_refresh", None)

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        card = QFrame()
        card.setObjectName("InnerCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 9, 10, 9)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        title = QLabel("Diagnostic Compare")
        title.setObjectName("PanelTitle")
        grid.addWidget(title, 0, 0, 1, 2)

        label_a = QLabel("Report A:")
        label_a.setObjectName("Muted")
        self.diagnostic_compare_a = QComboBox()
        grid.addWidget(label_a, 1, 0)
        grid.addWidget(self.diagnostic_compare_a, 1, 1)

        label_b = QLabel("Report B:")
        label_b.setObjectName("Muted")
        self.diagnostic_compare_b = QComboBox()
        grid.addWidget(label_b, 2, 0)
        grid.addWidget(self.diagnostic_compare_b, 2, 1)

        self.diagnostic_compare_btn = QPushButton("Compare reports")
        self.diagnostic_compare_btn.setEnabled(False)
        self.diagnostic_compare_btn.clicked.connect(self._run_diagnostic_compare)
        grid.addWidget(self.diagnostic_compare_btn, 3, 0, 1, 2)

        self.diagnostic_compare_value = QLabel("Cần ít nhất 2 report trong History để so sánh.")
        self.diagnostic_compare_value.setObjectName("Muted")
        self.diagnostic_compare_value.setWordWrap(True)
        grid.addWidget(self.diagnostic_compare_value, 4, 0, 1, 2)

        self.diagnostic_compare_card = card
        layout = self.right_panel.layout()
        insert_at = max(0, layout.count() - 2)
        layout.insertWidget(insert_at, card)
        self._diagnostic_compare_refresh()

    def _diagnostic_compare_refresh(self):
        if not hasattr(self, "diagnostic_compare_a"):
            return
        entries = self._diagnostic_history.load()
        for combo in (self.diagnostic_compare_a, self.diagnostic_compare_b):
            combo.blockSignals(True)
            combo.clear()
            for entry in entries:
                stamp = entry.generated_at_utc.replace("T", " ")[:19] or "unknown time"
                label = (
                    f"{entry.jar_name} · {entry.compatibility_score}/100 · "
                    f"{entry.startup_severity.upper()} · {stamp}"
                )
                combo.addItem(label, entry)
            combo.blockSignals(False)

        enabled = len(entries) >= 2
        self.diagnostic_compare_a.setEnabled(enabled)
        self.diagnostic_compare_b.setEnabled(enabled)
        self.diagnostic_compare_btn.setEnabled(enabled)
        self.diagnostic_compare_value.setStyleSheet("")
        if enabled:
            self.diagnostic_compare_a.setCurrentIndex(1)
            self.diagnostic_compare_b.setCurrentIndex(0)
            self.diagnostic_compare_value.setText("A = bản cũ, B = bản mới. Bấm Compare reports để xem thay đổi.")
        elif entries:
            self.diagnostic_compare_value.setText("Cần thêm 1 report nữa để so sánh.")
        else:
            self.diagnostic_compare_value.setText("Cần ít nhất 2 report trong History để so sánh.")

    def _run_diagnostic_compare(self):
        left_entry = self.diagnostic_compare_a.currentData()
        right_entry = self.diagnostic_compare_b.currentData()
        if left_entry is None or right_entry is None:
            return
        if left_entry.json_path == right_entry.json_path:
            self.diagnostic_compare_value.setStyleSheet("")
            self.diagnostic_compare_value.setText("Report A và B đang giống nhau.")
            return
        try:
            left = load_report(left_entry.json_path)
            right = load_report(right_entry.json_path)
            comparison = compare_reports(left, right)
            verdict = build_compare_verdict(comparison, left, right)
            text = format_compare_verdict(verdict) + "\n\n" + format_comparison(comparison)
            self.diagnostic_compare_value.setText(text)
            if verdict.label == "IMPROVED":
                self.diagnostic_compare_value.setStyleSheet("color:#059669; font-weight:600;")
            elif verdict.label == "REGRESSED":
                self.diagnostic_compare_value.setStyleSheet("color:#DC2626; font-weight:600;")
            elif verdict.label == "MIXED":
                self.diagnostic_compare_value.setStyleSheet("color:#D97706; font-weight:600;")
            else:
                self.diagnostic_compare_value.setStyleSheet("")
            self.statusBar().showMessage(
                f"{verdict.label}: {left_entry.jar_name} → {right_entry.jar_name}", 7000
            )
        except Exception as exc:
            self.diagnostic_compare_value.setStyleSheet("")
            self.diagnostic_compare_value.setText("Không thể đọc một trong hai report đã chọn.")
            QMessageBox.warning(self, "Diagnostic Compare", f"Không thể so sánh report:\n{exc}")

    def wrapped_history_refresh(self):
        if original_history_refresh is not None:
            original_history_refresh(self)
        _diagnostic_compare_refresh(self)

    MainWindow.__init__ = hooked_init
    if original_history_refresh is not None:
        MainWindow._runtime_history_refresh = wrapped_history_refresh
    MainWindow._diagnostic_compare_refresh = _diagnostic_compare_refresh
    MainWindow._run_diagnostic_compare = _run_diagnostic_compare
    return MainWindow
