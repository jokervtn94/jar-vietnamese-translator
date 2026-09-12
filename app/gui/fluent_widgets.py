from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMenu,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle
)


class WorkflowStep(QFrame):
    """Compact Fluent workflow stage with a numbered badge and action menu."""
    def __init__(self, number, title, subtitle, parent=None, active=False):
        super().__init__(parent)
        self.setObjectName("WorkflowStep")
        self.setProperty("active", bool(active))
        self.setMinimumHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10 if active else 4, 6, 10 if active else 4, 6)
        layout.setSpacing(9)
        badge = QLabel(str(number))
        badge.setObjectName("StepBadgeActive" if active else "StepBadge")
        layout.addWidget(badge, 0, Qt.AlignVCenter)
        text = QVBoxLayout(); text.setSpacing(1); text.setContentsMargins(0,0,0,0)
        self.title_button = QPushButton(title)
        self.title_button.setObjectName("StageMenu")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("StepSub")
        text.addWidget(self.title_button)
        text.addWidget(self.subtitle_label)
        layout.addLayout(text, 1)

    def set_actions(self, actions, owner, action_registry):
        menu = QMenu(self.title_button)
        for key, label, callback, enabled in actions:
            from PySide6.QtGui import QAction
            action = QAction(label, owner)
            action.setEnabled(enabled)
            action.triggered.connect(callback)
            menu.addAction(action)
            action_registry[key] = action
        if actions:
            self.title_button.setMenu(menu)


class StatusBadgeDelegate(QStyledItemDelegate):
    """Draw status cells as compact rounded badges without creating child widgets per row."""
    COLORS = {
        "Đã dịch": (QColor("#18C98A"), QColor("#FFFFFF"), QColor("#0FAE76")),
        "Cần kiểm tra": (QColor("#FFD166"), QColor("#3B2A00"), QColor("#E8B33D")),
        "Chưa dịch": (QColor("#DCE3EA"), QColor("#31465D"), QColor("#C5CED8")),
    }

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        text = str(index.data() or "")
        if text not in self.COLORS:
            return super().paint(painter, option, index)
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#CBEAFF"))
        bg, fg, border = self.COLORS[text]
        fm = option.fontMetrics
        width = min(option.rect.width() - 12, max(66, fm.horizontalAdvance(text) + 20))
        height = min(24, option.rect.height() - 6)
        rect = QRect(option.rect.x() + (option.rect.width()-width)//2,
                     option.rect.y() + (option.rect.height()-height)//2,
                     width, height)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()
