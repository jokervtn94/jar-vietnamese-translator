from __future__ import annotations

# Portable workspace mirrors the development workspace semantically.
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
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
    """Promote diagnostics from sidebar cards into a dedicated full-width page."""
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
            "workspace",
            "build_jar_btn",
        )
        if not all(hasattr(self, name) for name in required):
            return

        # Remove legacy diagnostic cards from the narrow translation editor sidebar.
        right_layout = self.right_panel.layout()
        cards = [
            self.runtime_compat_card,
            self.runtime_log_card,
            self.diagnostic_compare_card,
            self.diagnostic_bundle_inspector_card,
        ]
        for card in cards:
            right_layout.removeWidget(card)

        # Turn the application's work area into two first-class pages:
        # translation workspace and full-width diagnostics center.
        translation_page = self.workspace.parentWidget()
        host = translation_page.parentWidget()
        host_layout = host.layout()
        work_index = host_layout.indexOf(translation_page)

        stack = QStackedWidget()
        stack.setObjectName("MainWorkspaceStack")
        stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        host_layout.removeWidget(translation_page)
        host_layout.insertWidget(work_index, stack, 1)
        stack.addWidget(translation_page)

        diagnostics_page = QWidget()
        diagnostics_page.setObjectName("DiagnosticsPage")
        page_layout = QVBoxLayout(diagnostics_page)
        page_layout.setContentsMargins(18, 16, 18, 16)
        page_layout.setSpacing(12)

        top = QFrame()
        top.setObjectName("DiagnosticsTopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(10)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(2)
        title = QLabel("Diagnostics & Compatibility")
        title.setObjectName("DiagnosticsTitle")
        subtitle = QLabel("Phân tích tương thích · Runtime log · Compare · Diagnostic bundle")
        subtitle.setObjectName("DiagnosticsSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        top_layout.addLayout(title_stack, 1)

        badge = QLabel("Integrated")
        badge.setObjectName("DiagnosticsBadge")
        top_layout.addWidget(badge)

        back_btn = QPushButton("← Quay lại dịch")
        back_btn.setObjectName("DiagnosticsBackButton")
        top_layout.addWidget(back_btn)
        page_layout.addWidget(top)

        tabs = QTabWidget()
        tabs.setObjectName("DiagnosticsTabs")
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.addTab(_page(self.runtime_compat_card), "Overview")
        tabs.addTab(_page(self.runtime_log_card), "Runtime Log")
        tabs.addTab(_page(self.diagnostic_compare_card), "Compare")
        tabs.addTab(_page(self.diagnostic_bundle_inspector_card), "Bundle")
        page_layout.addWidget(tabs, 1)
        stack.addWidget(diagnostics_page)

        # Persistent, visible navigation in the main workflow header.
        header = self.build_jar_btn.parentWidget()
        header_layout = header.layout()
        diagnostics_btn = QPushButton("Diagnostics")
        diagnostics_btn.setObjectName("DiagnosticsNavButton")
        diagnostics_btn.setFixedHeight(42)
        build_index = header_layout.indexOf(self.build_jar_btn)
        header_layout.insertWidget(max(0, build_index), diagnostics_btn, 0)

        def show_diagnostics():
            stack.setCurrentWidget(diagnostics_page)
            diagnostics_btn.setProperty("active", True)
            diagnostics_btn.style().unpolish(diagnostics_btn)
            diagnostics_btn.style().polish(diagnostics_btn)

        def show_translation():
            stack.setCurrentWidget(translation_page)
            diagnostics_btn.setProperty("active", False)
            diagnostics_btn.style().unpolish(diagnostics_btn)
            diagnostics_btn.style().polish(diagnostics_btn)

        diagnostics_btn.clicked.connect(show_diagnostics)
        back_btn.clicked.connect(show_translation)

        diagnostics_page.setStyleSheet(
            """
            QWidget#DiagnosticsPage {
                background: #F7F8FA;
            }
            QFrame#DiagnosticsTopBar {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
            }
            QLabel#DiagnosticsTitle {
                color: #111827;
                font-size: 18px;
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
                padding: 5px 9px;
                font-weight: 600;
            }
            QPushButton#DiagnosticsBackButton {
                min-height: 32px;
                padding: 0 12px;
            }
            QTabWidget#DiagnosticsTabs::pane {
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                background: #FFFFFF;
                top: 8px;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab {
                color: #4B5563;
                background: #EDEFF3;
                border: none;
                border-radius: 8px;
                padding: 9px 16px;
                margin-right: 5px;
                min-width: 90px;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab:selected {
                color: #1D4ED8;
                background: #EAF2FF;
                font-weight: 700;
            }
            QTabWidget#DiagnosticsTabs QTabBar::tab:hover:!selected {
                background: #E2E5EA;
            }
            """
        )

        diagnostics_btn.setStyleSheet(
            """
            QPushButton#DiagnosticsNavButton {
                color: #1D4ED8;
                background: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 9px;
                padding: 0 14px;
                font-weight: 700;
            }
            QPushButton#DiagnosticsNavButton:hover,
            QPushButton#DiagnosticsNavButton[active="true"] {
                background: #DBEAFE;
                border-color: #BFDBFE;
            }
            """
        )

        self.main_workspace_stack = stack
        self.translation_workspace_page = translation_page
        self.diagnostics_page = diagnostics_page
        self.diagnostics_tabs = tabs
        self.diagnostics_nav_btn = diagnostics_btn
        self._show_diagnostics_page = show_diagnostics
        self._show_translation_page = show_translation

        show_translation()

    def _diagnostics_show_tab(self, name):
        tabs = getattr(self, "diagnostics_tabs", None)
        show_page = getattr(self, "_show_diagnostics_page", None)
        if tabs is None or show_page is None:
            return
        index = _TAB_INDEX.get(str(name).lower())
        if index is not None:
            tabs.setCurrentIndex(index)
        show_page()

    MainWindow.__init__ = hooked_init
    MainWindow._diagnostics_show_tab = _diagnostics_show_tab
    return MainWindow
