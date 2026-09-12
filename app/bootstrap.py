from __future__ import annotations

import sys
from pathlib import Path


def _app_root() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    app_root = _app_root()
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow
    from gui.runtime_compat_hook import install_runtime_compatibility
    from gui.diagnostic_compare_hook import install_diagnostic_compare
    from gui.runtime_log_hook import install_runtime_log_analysis
    from gui.patch_update_hook import install_patch_update_ui
    from gui.cumulative_ui_polish_hook import install_cumulative_ui_polish
    from gui.latest_translation_ui_hook import install_latest_translation_ui

    install_runtime_compatibility(MainWindow)
    install_diagnostic_compare(MainWindow)
    install_runtime_log_analysis(MainWindow)
    install_patch_update_ui(MainWindow)
    install_cumulative_ui_polish(MainWindow)
    install_latest_translation_ui(MainWindow)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
