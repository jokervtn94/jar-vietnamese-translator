from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QLabel, QPushButton
from core.diagnostic_bundle_inspector import (
    format_diagnostic_bundle_inspection,
    inspect_diagnostic_bundle_zip,
)


def install_diagnostic_bundle_inspector(MainWindow):
    if getattr(MainWindow, "_diagnostic_bundle_inspector_hook_installed", False):
        return MainWindow
    MainWindow._diagnostic_bundle_inspector_hook_installed = True
    original_init = MainWindow.__init__

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        card = QFrame()
        card.setObjectName("InnerCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 9, 10, 9)

        title = QLabel("Diagnostic Bundle Inspector")
        title.setObjectName("PanelTitle")
        grid.addWidget(title, 0, 0, 1, 2)

        self.diagnostic_bundle_open_btn = QPushButton("Open Diagnostic ZIP")
        self.diagnostic_bundle_open_btn.clicked.connect(self._open_diagnostic_bundle_zip)
        grid.addWidget(self.diagnostic_bundle_open_btn, 1, 0, 1, 2)

        self.diagnostic_bundle_value = QLabel("Mở file diagnostic ZIP để xem lại kết quả mà không cần scan JAR lại.")
        self.diagnostic_bundle_value.setObjectName("Muted")
        self.diagnostic_bundle_value.setWordWrap(True)
        grid.addWidget(self.diagnostic_bundle_value, 2, 0, 1, 2)

        self.diagnostic_bundle_inspector_card = card
        layout = self.right_panel.layout()
        layout.insertWidget(max(0, layout.count() - 2), card)

    def _open_diagnostic_bundle_zip(self):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open Diagnostic ZIP",
            "",
            "Diagnostic ZIP (*.zip);;All files (*)",
        )
        if not selected:
            return
        try:
            result = inspect_diagnostic_bundle_zip(selected)
            self._diagnostic_bundle_inspection = result
            self.diagnostic_bundle_value.setText(format_diagnostic_bundle_inspection(result))
            state = "valid" if result.is_valid_bundle else "incomplete"
            self.statusBar().showMessage(
                f"Diagnostic bundle {state}: {result.archive_name}", 9000
            )
        except Exception as exc:
            self._diagnostic_bundle_inspection = None
            self.diagnostic_bundle_value.setText(f"Không thể đọc diagnostic ZIP: {exc}")

    MainWindow.__init__ = hooked_init
    MainWindow._open_diagnostic_bundle_zip = _open_diagnostic_bundle_zip
    return MainWindow
