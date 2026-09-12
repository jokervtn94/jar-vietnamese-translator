from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from services.patch_updater import PatchUpdater
from services.paths import portable_root


def install_patch_update_ui(MainWindow):
    """Expose the modular patch updater in the main UI."""
    if getattr(MainWindow, "_patch_update_hook_installed", False):
        return MainWindow
    MainWindow._patch_update_hook_installed = True
    original_init = MainWindow.__init__

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        action = QAction("Apply Update Patch…", self)
        action.setToolTip("Áp dụng gói patch .zip vào bản portable hiện tại")
        action.triggered.connect(self._apply_update_patch)
        menu = self.settings_btn.menu() if hasattr(self, "settings_btn") else None
        if menu is not None:
            menu.insertSeparator(menu.actions()[0] if menu.actions() else None)
            menu.insertAction(menu.actions()[0] if menu.actions() else None, action)
        self.apply_patch_action = action

        # Also surface the updater directly in the full-width Diagnostics page.
        top = getattr(self, "diagnostics_top_layout", None)
        if top is not None:
            button = QPushButton("Update Patch")
            button.setObjectName("PatchUpdateButton")
            button.setToolTip("Chọn patch ZIP, kiểm tra SHA-256, backup và cập nhật module")
            button.clicked.connect(self._apply_update_patch)
            # Place before the Back button when possible.
            insert_at = max(0, top.count() - 1)
            top.insertWidget(insert_at, button)
            self.patch_update_btn = button

    def _apply_update_patch(self):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Apply Update Patch",
            str(Path(portable_root()) / "updates"),
            "JVT patch (*.zip);;ZIP files (*.zip);;All files (*)",
        )
        if not selected:
            return

        answer = QMessageBox.question(
            self,
            "Apply Update Patch",
            "App sẽ kiểm tra SHA-256, backup file cũ và rollback nếu patch lỗi.\n\n"
            "Tiếp tục áp dụng patch này?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            result = PatchUpdater().apply(selected)
            files = "\n".join(f"• {name}" for name in result.applied[:20]) or "• Không có file thay đổi"
            if len(result.applied) > 20:
                files += f"\n• … và {len(result.applied) - 20} file khác"
            QMessageBox.information(
                self,
                "Update Patch hoàn tất",
                f"Patch: {result.patch_id}\n"
                f"Đã cập nhật: {len(result.applied)} file\n"
                f"Backup: {result.backup_dir}\n\n"
                f"{files}\n\n"
                "Hãy đóng và mở lại app để nạp toàn bộ module mới.",
            )
            self.statusBar().showMessage(
                f"Patch {result.patch_id}: applied {len(result.applied)} file · restart required",
                12000,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Update Patch thất bại",
                f"Patch không được áp dụng hoàn chỉnh. Các thay đổi dở dang đã được rollback.\n\n{exc}",
            )

    MainWindow.__init__ = hooked_init
    MainWindow._apply_update_patch = _apply_update_patch
    return MainWindow
