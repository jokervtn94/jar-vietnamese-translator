from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QFrame, QSizePolicy, QTreeWidgetItem


_ICON_COLORS = {
    "jar": "#2563EB",
    "folder": "#E0A100",
    "class": "#7C3AED",
    "text": "#0F9D58",
    "binary": "#D97706",
    "image": "#E11D48",
    "audio": "#0891B2",
    "meta": "#475569",
    "file": "#64748B",
}


def _category(path: str, has_children: bool = False) -> str:
    name = PurePosixPath(path).name.lower()
    if has_children or path.endswith("/"):
        return "folder"
    if name.endswith(".jar"):
        return "jar"
    if name.endswith(".class"):
        return "class"
    if name in {"manifest.mf"} or path.lower().startswith("meta-inf/"):
        return "meta"
    if name.endswith((".properties", ".txt", ".xml", ".ini", ".lang", ".lng", ".json", ".yaml", ".yml", ".csv")):
        return "text"
    if name.endswith((".dat", ".bin", ".res", ".map", ".sce")):
        return "binary"
    if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
        return "image"
    if name.endswith((".mid", ".midi", ".wav", ".mp3", ".amr")):
        return "audio"
    return "file"


def _icon(kind: str) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(_ICON_COLORS.get(kind, _ICON_COLORS["file"])))
    painter.drawRoundedRect(2, 2, 14, 14, 3, 3)
    if kind == "folder":
        painter.setBrush(QColor("#F5C542"))
        painter.drawRoundedRect(2, 5, 14, 10, 2, 2)
        painter.drawRoundedRect(3, 3, 7, 5, 2, 2)
    elif kind == "class":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "C")
    elif kind == "text":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    elif kind == "binary":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "01")
    elif kind == "image":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "▧")
    elif kind == "audio":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "♪")
    elif kind == "meta":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")
    elif kind == "jar":
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "J")
    painter.end()
    return QIcon(pixmap)


def _decorate_tree(tree) -> None:
    tree.setIconSize(QSize(18, 18))

    def visit(item: QTreeWidgetItem, is_root: bool = False) -> None:
        path = str(item.data(0, Qt.UserRole) or item.text(0))
        if is_root:
            kind = "jar"
        else:
            kind = _category(path, item.childCount() > 0)
        item.setIcon(0, _icon(kind))
        item.setToolTip(0, path or item.text(0))
        for i in range(item.childCount()):
            visit(item.child(i), False)

    for i in range(tree.topLevelItemCount()):
        visit(tree.topLevelItem(i), True)


def install_latest_translation_ui(MainWindow):
    """Restore the latest approved translation workspace presentation."""
    if getattr(MainWindow, "_latest_translation_ui_hook_installed", False):
        return MainWindow
    MainWindow._latest_translation_ui_hook_installed = True

    original_init = MainWindow.__init__
    original_populate_tree = getattr(MainWindow, "populate_tree", None)
    original_populate_entries = getattr(MainWindow, "_populate_tree_from_entries", None)
    original_load_editor = getattr(MainWindow, "load_selected_string_editor", None)

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        # Remove the retired translation suggestion panel completely.
        suggestion = self.findChild(QFrame, "SuggestionCard")
        if suggestion is not None:
            parent_layout = suggestion.parentWidget().layout() if suggestion.parentWidget() else None
            if parent_layout is not None:
                parent_layout.removeWidget(suggestion)
            suggestion.hide()
            suggestion.deleteLater()
        if hasattr(self, "suggestion_text"):
            self.suggestion_text = None

        # Repair context/metadata layout so long source paths and stable keys do not overlap.
        values = [
            getattr(self, "info_path", None),
            getattr(self, "info_type", None),
            getattr(self, "info_count", None),
            getattr(self, "info_score", None),
            getattr(self, "info_status", None),
        ]
        for widget in values:
            if widget is None:
                continue
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            widget.setMinimumWidth(0)

        info_path = getattr(self, "info_path", None)
        context = info_path.parentWidget() if info_path is not None else None
        if context is not None and context.layout() is not None:
            grid = context.layout()
            if hasattr(grid, "setColumnStretch"):
                grid.setColumnStretch(0, 0)
                grid.setColumnStretch(1, 1)
            titles = context.findChildren(QLabel, "PanelTitle")
            for label in titles:
                if label.text() == "Thông tin ngữ cảnh":
                    label.setText("Thông tin chuỗi")

        tree = getattr(self, "tree", None)
        if tree is not None:
            _decorate_tree(tree)

    def populate_tree(self, *args, **kwargs):
        if original_populate_tree is not None:
            result = original_populate_tree(self, *args, **kwargs)
        else:
            result = None
        if hasattr(self, "tree"):
            _decorate_tree(self.tree)
        return result

    def populate_entries(self, *args, **kwargs):
        if original_populate_entries is not None:
            result = original_populate_entries(self, *args, **kwargs)
        else:
            result = None
        if hasattr(self, "tree"):
            _decorate_tree(self.tree)
        return result

    def load_editor(self, *args, **kwargs):
        result = original_load_editor(self, *args, **kwargs) if original_load_editor is not None else None
        for name in ("info_path", "info_score"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setToolTip(widget.text())
        return result

    MainWindow.__init__ = hooked_init
    if original_populate_tree is not None:
        MainWindow.populate_tree = populate_tree
    if original_populate_entries is not None:
        MainWindow._populate_tree_from_entries = populate_entries
    if original_load_editor is not None:
        MainWindow.load_selected_string_editor = load_editor
    return MainWindow
