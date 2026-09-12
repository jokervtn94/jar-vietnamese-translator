import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTextEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView, QFrame
)


class BuildTaskDialog(QDialog):
    """Non-blocking build monitor with task list, live log, progress and ETA."""

    TASKS = [
        ("preflight", "Kiểm tra điều kiện build"),
        ("glyph", "Kiểm tra font / glyph"),
        ("compat", "Kiểm tra tương thích"),
        ("prepare", "Chuẩn bị bản dịch và file tạm"),
        ("patch", "Patch class / resource / binary"),
        ("validate", "Kiểm tra ZIP / CRC / class"),
        ("regression", "Đối chiếu bản dịch sau build"),
        ("publish", "Xuất bản JAR hoàn chỉnh"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tiến trình Build JAR")
        self.setModal(False)
        self.resize(720, 560)
        self.setMinimumSize(620, 480)
        self._started = time.monotonic()
        self._progress = 0
        self._finished = False
        self._task_items = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Build JAR")
        title.setObjectName("PanelTitle")
        root.addWidget(title)
        self.stage_label = QLabel("Đang chuẩn bị…")
        self.stage_label.setObjectName("Muted")
        root.addWidget(self.stage_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(12)
        self.progress.setMaximumHeight(12)
        root.addWidget(self.progress)

        metrics = QHBoxLayout()
        self.percent_label = QLabel("0%")
        self.elapsed_label = QLabel("Đã chạy: 00:00")
        self.eta_label = QLabel("Còn lại: đang ước tính…")
        for w in (self.percent_label, self.elapsed_label, self.eta_label):
            w.setObjectName("Muted")
        metrics.addWidget(self.percent_label)
        metrics.addStretch()
        metrics.addWidget(self.elapsed_label)
        metrics.addSpacing(16)
        metrics.addWidget(self.eta_label)
        root.addLayout(metrics)

        self.tasks = QTreeWidget()
        self.tasks.setHeaderLabels(["Công việc", "Trạng thái"])
        self.tasks.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tasks.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tasks.setRootIsDecorated(False)
        self.tasks.setAlternatingRowColors(True)
        self.tasks.setMinimumHeight(190)
        for key, label in self.TASKS:
            item = QTreeWidgetItem([label, "Chờ"])
            item.setData(0, Qt.UserRole, key)
            self.tasks.addTopLevelItem(item)
            self._task_items[key] = item
        root.addWidget(self.tasks)

        log_title = QLabel("Task log")
        log_title.setObjectName("PanelTitle")
        root.addWidget(log_title)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(150)
        root.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Đóng")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(500)

    def closeEvent(self, event):
        if not self._finished:
            event.ignore()
            return
        super().closeEvent(event)

    @staticmethod
    def _fmt_seconds(seconds):
        seconds = max(0, int(seconds))
        if seconds >= 3600:
            h, rem = divmod(seconds, 3600)
            m, s = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def _tick(self):
        elapsed = time.monotonic() - self._started
        self.elapsed_label.setText(f"Đã chạy: {self._fmt_seconds(elapsed)}")
        if self._finished:
            self.eta_label.setText("Còn lại: 00:00")
            return
        p = self._progress
        if p >= 5:
            eta = elapsed * (100 - p) / max(1, p)
            self.eta_label.setText(f"Còn lại: ~{self._fmt_seconds(eta)}")
        else:
            self.eta_label.setText("Còn lại: đang ước tính…")

    def append_log(self, message, level="info"):
        prefix = {"warning": "⚠", "error": "✖", "success": "✓"}.get(level, "•")
        stamp = time.strftime("%H:%M:%S")
        self.log.append(f"[{stamp}] {prefix} {message}")
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_task(self, key, status, detail=""):
        item = self._task_items.get(key)
        if item is None:
            return
        labels = {
            "running": "Đang chạy",
            "done": "Hoàn tất",
            "warning": "Cảnh báo",
            "error": "Lỗi",
            "waiting": "Chờ",
        }
        item.setText(1, labels.get(status, status))
        if detail:
            item.setToolTip(0, detail)
            item.setToolTip(1, detail)

    def update_progress(self, percent, stage_key, message, level="info"):
        percent = max(self._progress, min(100, int(percent)))
        self._progress = percent
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        self.stage_label.setText(message)
        if stage_key:
            self.set_task(stage_key, "running")
        if message:
            self.append_log(message, level)

    def mark_finished(self, success, message):
        self._finished = True
        self.timer.stop()
        if success:
            self._progress = 100
            self.progress.setValue(100)
            self.percent_label.setText("100%")
            self.stage_label.setText(message)
            self.append_log(message, "success")
        else:
            self.stage_label.setText(message)
            self.append_log(message, "error")
        self.close_btn.setEnabled(True)
        self._tick()
