# Architecture

The application treats a Java/J2ME JAR as a ZIP archive and keeps scanning, translation state, patching, validation, and UI responsibilities separated.

## Scan

- `core/class_reader.py`: Java constant-pool string extraction.
- `core/resource_scanner.py`: standard text/binary resource scanning.
- `core/deep_resource_scanner.py`: high-recall discovery for unusual resources.
- `core/language_detector.py`: precision filter and candidate scoring.
- `core/jar_scanner.py`: scan orchestration.

## Translation exchange

- `core/translation_project.py`: stable translation mapping.
- `core/translation_exchange.py`: strict V2 JSON export/import protocol.

## Build

- `core/class_patcher.py`: safe class constant-pool rewriting.
- `core/binary_resource_patcher.py`: controlled framed binary rewriting.
- `core/jar_builder.py`: rebuild and validation.

## Validation

- `core/build_readiness.py`
- `core/regression_validator.py`
- `core/compatibility_analyzer.py`
- `core/glyph_analyzer.py`
- `core/runtime_log_analyzer.py`

## UI

- `gui/main_window.py`: responsive PySide6 desktop interface.
