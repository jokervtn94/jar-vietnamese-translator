from __future__ import annotations

from PySide6.QtWidgets import QLabel

from core.version import APP_NAME, APP_VERSION


def install_cumulative_ui_polish(MainWindow):
    """Final presentation pass for the v4.31 cumulative portable UI."""
    if getattr(MainWindow, "_cumulative_ui_polish_hook_installed", False):
        return MainWindow
    MainWindow._cumulative_ui_polish_hook_installed = True
    original_init = MainWindow.__init__

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        title_text = f"{APP_NAME} v{APP_VERSION}-cumulative (Portable)"
        self.setWindowTitle(title_text)
        if hasattr(self, "app_title"):
            self.app_title.setText(f"{APP_NAME} v{APP_VERSION}-cumulative")
        if hasattr(self, "app_subtitle"):
            self.app_subtitle.setText("Dịch, kiểm tra tương thích và rebuild game Java/J2ME")

        diagnostics_page = getattr(self, "diagnostics_page", None)
        if diagnostics_page is not None:
            for label in diagnostics_page.findChildren(QLabel):
                text = label.text()
                if text == "Diagnostics & Compatibility":
                    label.setText("Diagnostics Center")
                elif text == "Phân tích tương thích · Runtime log · Compare · Diagnostic bundle":
                    label.setText("Phân tích khả năng tương thích, log runtime và chẩn đoán lỗi khi chạy game JAR trên FreeJ2ME / RG35XX.")
                elif text == "Integrated":
                    label.setText("v4.31 cumulative")

        nav = getattr(self, "diagnostics_nav_btn", None)
        patch = getattr(self, "patch_update_btn", None)
        build = getattr(self, "build_jar_btn", None)
        if nav is not None and patch is not None and build is not None:
            header = build.parentWidget()
            layout = header.layout() if header is not None else None
            if layout is not None:
                layout.removeWidget(nav)
                layout.removeWidget(patch)
                build_index = layout.indexOf(build)
                layout.insertWidget(max(0, build_index), nav, 0)
                build_index = layout.indexOf(build)
                layout.insertWidget(max(0, build_index), patch, 0)

        if patch is not None:
            patch.setStyleSheet(
                "QPushButton#PatchUpdateButton {"
                "color:#087A55;background:#ECFDF5;border:1px solid #A7F3D0;"
                "border-radius:9px;padding:0 14px;font-weight:700;}"
                "QPushButton#PatchUpdateButton:hover {background:#D1FAE5;border-color:#6EE7B7;}"
            )

        self.statusBar().showMessage(f"Sẵn sàng · Phiên bản {APP_VERSION}-cumulative (v431)")

    MainWindow.__init__ = hooked_init
    return MainWindow
