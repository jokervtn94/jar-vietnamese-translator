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

    install_runtime_compatibility(MainWindow)
    install_diagnostic_compare(MainWindow)
    install_runtime_log_analysis(MainWindow)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
