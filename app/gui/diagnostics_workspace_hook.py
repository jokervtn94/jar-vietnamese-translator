from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


_TAB_INDEX = {
    "overview": 0,
    "runtime": 1,
    "compare": 2,
    "bundle": 3,
}


def _page(card):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    card.setParent(page)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    layout.addWidget(card)
    layout.addStretch(1)
    return page


def install_diagnostics_workspace(MainWindow):
    """Group diagnostics cards into one integrated tabbed workspace."""
    if getattr(MainWindow, "_diagnostics_workspace_hook_installed", False):
        return MainWindow
    MainWindow._diagnostics_workspace_hook_installed = True
    original_init = MainWindow.__init__

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        required = (
            "runtime_compat_card",
            "runtime_log_card",
            "diagnostic_compare_card",
            "diagnostic_bundle_inspector_card",
        )
        if not all(hasattr(self, name) for name in required):
            return

        right_layout = self.right_panel.layout()
        cards = [
            self.runtime_compat_card,
            self.runtime_log_card,
            self.diagnostic_compare_card,
            self.diagnostic_bundle_inspector_card,
        ]
        for card in cards:
            right_layout.removeWidget(card)

        workspace = QFrame()
        workspace.setObjectName("DiagnosticsWorkspace")
        workspace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root = QVBoxLayout(workspace)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(1)
        title = QLabel("Diagnostics & Compatibility")
        title.setObjectName("DiagnosticsTitle")
        subtitle = QLabel("JAR → Compatibility → Runtime log → Compare → Bundle")
        subtitle.setObjectName("DiagnosticsSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack, 1)
        badge = QLabel("Integrated")
        badge.setObjectName("DiagnosticsBadge")
        header.addWidget(badge, 0)
        root.addLayout(header)

        tabs = QTabWidget()
        tabs.setObjectName("DiagnosticsTabs")
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.addTab(_page(self.runtime_compat_card), "Overview")
        tabs.addTab(_page(self.runtime_log_card), "Runtime Log")
        tabs.addTab(_page(self.diagnostic_compare_card), "Compare")
        tabs.addTab(_page(self.diagnostic_bundle_inspector_card), "Bundle")
        root.addWidget(tabs, 1)

        workspace.setStyleSheet(
            """
            QFrame#DiagnosticsWorkspace {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
            }
            QLabel#DiagnosticsTitle {
                color: #111827;
                font-size: 15px;
                font-weight: 700;
                border: none;
                background: transparent;
            }
            QLabel#DiagnosticsSubtitle {
                color: #6B7280;
                font-size: 11px;
                border: none;
                background: transparent;
            }
            QLabel#DiagnosticsBadge {
                color: #2563EB;
                background: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 9px;
                padding: 4px 8px;
                font-weight: 600;
            }
            QTabWidget#DiagnosticsTabs::pane {
                border: none;
                background: transparent;
                top: 6px;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab {
                color: #4B5563;
                background: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 7px 12px;
                margin-right: 4px;
                min-width: 72px;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab:selected {
                color: #1D4ED8;
                background: #EAF2FF;
                font-weight: 700;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab:hover:!selected {
                background: #E5E7EB;
            }
            """
        )

        self.diagnostics_workspace = workspace
        self.diagnostics_tabs = tabs
        insert_at = max(0, right_layout.count() - 2)
        right_layout.insertWidget(insert_at, workspace, 1)

    def _diagnostics_show_tab(self, name):
        tabs = getattr(self, "diagnostics_tabs", None)
        if tabs is None:
            return
        index = _TAB_INDEX.get(str(name).lower())
        if index is not None:
            tabs.setCurrentIndex(index)

    MainWindow.__init__ = hooked_init
    MainWindow._diagnostics_show_tab = _diagnostics_show_tab
    return MainWindow
