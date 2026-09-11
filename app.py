import sys
from PySide6.QtWidgets import QApplication
from core.rebuild_support import install_same_name_build_support

install_same_name_build_support()

from gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
