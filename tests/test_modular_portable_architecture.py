from pathlib import Path
import json
import sys
import zipfile

ROOT = Path(__file__).parents[1]


def test_modular_layout_exists():
    required = [
        ROOT / "launcher.py",
        ROOT / "app/bootstrap.py",
        ROOT / "app/core/jar_scanner.py",
        ROOT / "app/core/jar_builder.py",
        ROOT / "app/gui/main_window.py",
        ROOT / "app/themes/monokai_light.qss",
        ROOT / "app/services/patch_updater.py",
        ROOT / "config/modules.json",
    ]
    assert all(p.exists() for p in required)


def test_module_manifest_has_independent_versions():
    data = json.loads((ROOT / "config/modules.json").read_text(encoding="utf-8"))
    for key in ["runtime", "core", "scanner", "builder", "json_exchange", "ui", "theme", "updater"]:
        assert key in data["modules"]
        assert data["modules"][key]["version"]
        assert data["modules"][key]["path"]


def test_external_theme_is_loaded_by_modular_ui():
    text = (ROOT / "app/gui/fluent_theme.py").read_text(encoding="utf-8")
    assert "monokai_light.qss" in text
    assert "read_text" in text
    qss = (ROOT / "app/themes/monokai_light.qss").read_text(encoding="utf-8")
    assert "#E60073" in qss
    assert "#F5F7FA" in qss


def test_patch_updater_can_replace_one_path_transactionally(tmp_path, monkeypatch):
    portable = tmp_path / "portable"
    (portable / "app/test").mkdir(parents=True)
    target = portable / "app/test/value.txt"
    target.write_text("old", encoding="utf-8")
    (portable / "updates").mkdir()

    sys.path.insert(0, str(ROOT / "app"))
    import services.paths as paths
    import services.patch_updater as pu

    monkeypatch.setattr(paths, "portable_root", lambda: portable)
    monkeypatch.setattr(paths, "updates_root", lambda: portable / "updates")
    monkeypatch.setattr(pu, "portable_root", lambda: portable)
    monkeypatch.setattr(pu, "updates_root", lambda: portable / "updates")

    payload = b"new"
    import hashlib
    digest = hashlib.sha256(payload).hexdigest()
    patch = tmp_path / "patch.zip"
    manifest = {
        "format": "jvt-patch-v1",
        "patch_id": "test-001",
        "files": [{"path": "app/test/value.txt", "sha256": digest}],
    }
    with zipfile.ZipFile(patch, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("files/app/test/value.txt", payload)

    result = pu.PatchUpdater().apply(patch)
    assert target.read_text(encoding="utf-8") == "new"
    assert result.applied == ["app/test/value.txt"]
    assert Path(result.backup_dir, "app/test/value.txt").read_text(encoding="utf-8") == "old"
