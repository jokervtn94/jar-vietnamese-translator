from pathlib import Path


def test_patch_update_ui_is_visible_without_importing_qt():
    source = Path("gui/patch_update_hook.py").read_text(encoding="utf-8")
    portable = Path("app/gui/patch_update_hook.py").read_text(encoding="utf-8")

    for text in (source, portable):
        assert 'QAction("Apply Update Patch…", self)' in text
        assert 'QPushButton("Update Patch")' in text
        assert "PatchUpdater().apply(selected)" in text
        assert "result.backup_dir" in text
        assert "rollback" in text.lower()
        assert "restart required" in text
        assert "diagnostics_nav_btn" in text


def test_patch_backend_contract_remains_transactional():
    text = Path("app/services/patch_updater.py").read_text(encoding="utf-8")
    assert 'FORMAT = "jvt-patch-v1"' in text
    assert "hashlib.sha256" in text
    assert "backup_dir" in text
    assert "shutil.copy2(old_backup, dst)" in text
    assert 'updates_root() / "patch_history.jsonl"' in text
