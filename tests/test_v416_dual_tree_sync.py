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
