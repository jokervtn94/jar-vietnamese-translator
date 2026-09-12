from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cumulative_baseline_manifest_is_present_and_current():
    manifest = json.loads((ROOT / "config/integrated_patches.json").read_text(encoding="utf-8"))
    modules = json.loads((ROOT / "config/modules.json").read_text(encoding="utf-8"))
    assert manifest["app_version"] == "4.31"
    assert manifest["patch_level"] == "v434"
    assert manifest["base_commit"] == "c74db123f33f97f88335215aeb288ed09ead984e"
    assert manifest["integrated_through"] == "d49555eabc04a3aeb147dd0aacda16b4129cd740"
    assert manifest["commit_distance"] == 206
    assert modules["app_version"] == "4.31-cumulative"
    assert modules["patch_level"] == "v434"
    assert modules["baseline_manifest"] == "config/integrated_patches.json"
    groups = {item["id"] for item in manifest["groups"]}
    assert "latest-translation-ui" in groups
    assert "stable-app-naming" in groups


def test_portable_and_root_versions_match_cumulative_baseline():
    root_version = (ROOT / "core/version.py").read_text(encoding="utf-8")
    app_version = (ROOT / "app/core/version.py").read_text(encoding="utf-8")
    assert root_version == app_version
    assert 'APP_VERSION = "4.31"' in app_version
    assert 'BUILD_TAG = "Cumulative Modular Diagnostics"' in app_version


def test_portable_workflow_requires_cumulative_manifest():
    workflow = (ROOT / ".github/workflows/build_portable.yml").read_text(encoding="utf-8")
    assert "config/integrated_patches.json" in workflow
    assert "4.31-cumulative" in workflow
    assert "v434" in workflow
    assert "app/gui/patch_update_hook.py" in workflow
    assert "app/gui/latest_translation_ui_hook.py" in workflow
