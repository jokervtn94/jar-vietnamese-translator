from pathlib import Path


def test_diagnostics_workspace_groups_existing_cards_without_importing_qt():
    source = Path("gui/diagnostics_workspace_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/diagnostics_workspace_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert 'QLabel("Diagnostics & Compatibility")' in text
        assert 'tabs.addTab(_page(self.runtime_compat_card), "Overview")' in text
        assert 'tabs.addTab(_page(self.runtime_log_card), "Runtime Log")' in text
        assert 'tabs.addTab(_page(self.diagnostic_compare_card), "Compare")' in text
        assert 'tabs.addTab(_page(self.diagnostic_bundle_inspector_card), "Bundle")' in text
        assert 'workspace.setObjectName("DiagnosticsWorkspace")' in text
        assert 'tabs.setObjectName("DiagnosticsTabs")' in text
        assert 'right_layout.removeWidget(card)' in text


def test_runtime_hook_installs_workspace_after_bundle_inspector():
    source = Path("gui/runtime_log_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/runtime_log_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert "from gui.diagnostics_workspace_hook import install_diagnostics_workspace" in text
        inspector_pos = text.rfind("install_diagnostic_bundle_inspector(MainWindow)")
        workspace_pos = text.rfind("install_diagnostics_workspace(MainWindow)")
        assert inspector_pos >= 0
        assert workspace_pos > inspector_pos
        assert 'self._diagnostics_show_tab("runtime")' in text
