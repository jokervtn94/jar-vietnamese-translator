from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Portable launcher executes modules from app/, while repository tests/developer tools
# still import the mirrored root packages. Until the trees are fully consolidated,
# these compatibility modules must stay semantically identical.
MIRRORED_MODULES = (
    "core/runtime_profiles.py",
    "core/runtime_api_analyzer.py",
    "core/compatibility_analyzer.py",
    "core/build_readiness.py",
    "core/runtime_compat_presenter.py",
    "core/activation_flow_analyzer.py",
    "core/class_dependency_inspector.py",
    "core/dependency_path_presenter.py",
    "core/startup_blocking_assessment.py",
    "core/compatibility_report.py",
    "core/diagnostic_history.py",
    "core/diagnostic_compare.py",
    "core/diagnostic_verdict.py",
    "core/diagnostic_recommendation.py",
    "core/runtime_log_correlator.py",
    "core/runtime_exception_timeline.py",
    "core/runtime_diagnosis_summary.py",
    "core/diagnostic_bundle.py",
    "core/diagnostic_bundle_inspector.py",
    "gui/runtime_compat_hook.py",
    "gui/diagnostic_compare_hook.py",
    "gui/runtime_log_hook.py",
    "gui/diagnostic_bundle_inspector_hook.py",
    "gui/diagnostics_workspace_hook.py",
    "gui/task_progress_dialog.py",
)


def _semantic_ast(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return ast.dump(tree, include_attributes=False)


def test_runtime_compatibility_modules_stay_in_sync():
    mismatches = []
    for relative in MIRRORED_MODULES:
        root_file = ROOT / relative
        app_file = ROOT / "app" / relative
        assert root_file.is_file(), f"Missing root module: {relative}"
        assert app_file.is_file(), f"Missing portable module: app/{relative}"
        if _semantic_ast(root_file) != _semantic_ast(app_file):
            mismatches.append(relative)

    assert not mismatches, (
        "Portable app/ and root compatibility modules diverged: "
        + ", ".join(mismatches)
    )


def test_launcher_still_targets_portable_app_tree():
    launcher = (ROOT / "launcher.py").read_text(encoding="utf-8")
    assert 'app_root = root / "app"' in launcher
    assert 'sys.path.insert(0, str(app_root))' in launcher


def test_portable_bootstrap_installs_runtime_compatibility_hooks():
    bootstrap = (ROOT / "app" / "bootstrap.py").read_text(encoding="utf-8")
    assert "from gui.runtime_compat_hook import install_runtime_compatibility" in bootstrap
    assert "install_runtime_compatibility(MainWindow)" in bootstrap
    assert "from gui.diagnostic_compare_hook import install_diagnostic_compare" in bootstrap
    assert "install_diagnostic_compare(MainWindow)" in bootstrap
    assert "from gui.runtime_log_hook import install_runtime_log_analysis" in bootstrap
    assert "install_runtime_log_analysis(MainWindow)" in bootstrap
