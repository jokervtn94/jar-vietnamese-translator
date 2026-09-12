# Modular Portable Architecture

`JAR Vietnamese Translator.exe` is a stable runtime launcher. Application code is intentionally stored outside the EXE.

## Portable layout

- `JAR Vietnamese Translator.exe`: stable launcher/runtime entry
- `app/core/`: JAR engine
- `app/features/`: feature-facing modules
- `app/gui/`: UI code
- `app/themes/`: QSS themes
- `app/services/`: paths, module registry, transactional patch updater
- `config/modules.json`: independent module versions and paths
- `updates/`: patch history and rollback backups
- `logs/`: runtime logs

## Update rule

If only UI changes, ship only the changed path, for example:

- `app/gui/main_window.py`
- `app/themes/monokai_light.qss`

If only scanner changes:

- `app/core/jar_scanner.py`
- optionally `app/features/scan/`

If only builder changes:

- `app/core/jar_builder.py`
- optionally `app/features/build/`

The runtime EXE does **not** need to be rebuilt for these changes.

## Patch ZIP format

A patch is `jvt-patch-v1` and contains:

- `manifest.json`
- `files/<portable-relative-path>`

`PatchUpdater` validates SHA-256, backs up overwritten files, copies only changed files, and rolls back automatically if any step fails.

## When a full runtime rebuild is required

Only when one of these changes:

- Python version/runtime
- PySide6/Qt runtime
- native dependency/DLL
- `launcher.py`
- `JAR_Translator.spec`
- `requirements.txt`

Normal engine/UI fixes should be distributed as small patches instead.
