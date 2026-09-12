# JAR Vietnamese Translator

## Modern desktop interface

The visible application name is always **JAR Vietnamese Translator**. Release/build numbers are intentionally not appended to the window title. The primary workspace follows a dark Fluent-style three-column layout with a four-stage workflow bar, simplified translation table, right-side inspector, and a fixed **Build JAR** action.


**Structured Binary Field Parser** adds nested binary text-field detection and safe length-prefix rewriting for UTF-8 J2ME resources.

# JAR Vietnamese Translator
**V4.9 Binary Text Recovery:** mixed binary records now recover embedded UTF-8/CJK text without mojibake and are only marked patch-safe when whole-record replacement is structurally safe.


Desktop tool for scanning, translating, patching, rebuilding, and validating Java/J2ME `.jar` games with a focus on Vietnamese localization.

Current release: **V4.14 – Direct Binary Framing Verify**




## V4.14 – Direct Binary Framing Verify

V4.14 fixes the remaining post-import GUI stall found in V4.12. The worker-thread parser was already fast, but V4.12 still rebuilt the entire QTableWidget on the GUI thread and then wrote the autosave snapshot from the GUI thread. V4.14 no longer calls `refresh_strings()` after JSON import. It updates only already-materialized visible rows in batches of 32 per event-loop turn and writes autosave JSON in a dedicated worker thread. This keeps the window responsive after large translated JSON imports while preserving V4.11/V4.12 validation and rebuild safety.

## V4.12 – Async JSON Import

V4.12 removes the UI freeze during translated-JSON import. JSON parsing, source-JAR hashing and protocol validation now run in a worker thread. Accepted translations are collected first and committed to the live project in one bulk update only after validation succeeds. The translation table suppresses per-cell repaint/signals while refreshing after import. V4.11 transactional rebuild safety remains unchanged.

## V4.11 – Translation / Rebuild Safety

V4.11 keeps the V4.10 precision extractor and hardens the import/build path. Safe binary resources are patched transactionally, variable-length UTF-8 replacements update their framing lengths, Java class strings continue to use Modified UTF-8, and every translated binary field is re-parsed after patching. If any field in a binary resource cannot be safely rebuilt, that resource is rolled back instead of being partially modified. Bare technical extension tokens such as `.map` are also filtered from export.

## V4.10 – Precision Language Filter

V4.10 keeps the V4.9 structured-binary parser and tightens the final language gate before JSON export. It rejects random ASCII payloads that only happen to match a binary length prefix, command-script streams such as `aplayer ...; item ...; scene ...;`, and common Java/J2ME engine identifiers while preserving CJK game text and known UI labels.

Validation against the V4.9 export of `仙侣情缘之麒麟劫320x240.jar`:
- `cfg.bin` false positives: 58 -> 0
- `event.bin` command-stream false positives: 1 -> 0
- `item.bin` real strings retained: 386/386
- `property.bin` real strings retained: 57/57
- `tek.bin` real strings retained: 25/25
- CJK class strings retained: 80/80


## V4.9 – Extractor V3

V4.9 focuses on extraction recall for real J2ME games before translation filtering:

- Multi-encoding decode: UTF-8, UTF-16, GB18030/GBK, Big5, cp1252/Latin-1.
- UTF-8 mojibake recovery for common double-decoding corruption.
- GB18030/Big5 discovery inside arbitrary binary resources.
- CJK-aware language classification so Chinese/Japanese/Korean text is not rejected by English-oriented heuristics.
- Improved Java Modified UTF-8 decoding including CESU-8 surrogate pairs.
- Existing safe framed binary detection remains conservative for rebuilding.
- V4.6 `jar-translator-exchange-v2` JSON protocol remains unchanged.


## Highlights

- Precision-first language scan for Java/J2ME JARs.
- Deep resource scan for `.class`, text resources, framed binary strings, UTF-8 and UTF-16 data.
- Filters technical/noise strings before they reach the translation editor.
- Responsive PySide6 UI that adapts to common desktop/laptop resolutions.
- Safe patch/rebuild workflow that never overwrites the source JAR.
- Controlled binary patching only for recognized safe framing.
- Encoding/font/glyph compatibility checks.
- Build Readiness gate and post-build Regression Validator.
- Runtime test package and FreeJ2ME/RG35XX log analysis.
- **No OpenAI/Gemini API integration.**
- Translation workflow uses an exported JSON protocol that can be uploaded manually to ChatGPT or Gemini and imported back safely.

## Translation workflow

1. Open a game `.jar`.
2. Run **Precision Scan**.
3. Review detected game text.
4. Click **Xuất JSON dịch**.
5. Upload the JSON file to ChatGPT or Gemini.
6. Ask the model to follow the embedded `translation_protocol` exactly.
7. Download the translated JSON.
8. Click **Nhập JSON dịch**.
9. Review imported translations.
10. Run Build Readiness.
11. Build the Vietnamese JAR.
12. Run Regression Validator.
13. Test with FreeJ2ME/RG35XX when applicable.

Recommended prompt when uploading the JSON:

> Hãy tuân thủ `translation_protocol` trong file JSON này. Chỉ dịch `items[].translation` sang tiếng Việt và trả lại đúng một tài liệu JSON hoàn chỉnh, không Markdown, không giải thích.

## Strict JSON protocol

The V4.6 export format is `jar-translator-exchange-v2`.

The file contains:
- mandatory model rules;
- immutable/editable field declarations;
- exact output contract;
- source JAR SHA-256;
- per-string SHA-256;
- placeholder manifest;
- item-count validation.

During import the app checks the schema, source JAR, item count, duplicate keys, immutable metadata, original text, hashes, and placeholders.

See [docs/JSON_PROTOCOL.md](docs/JSON_PROTOCOL.md).

## Requirements

- Windows 10/11 recommended
- Python 3.10+
- PySide6

Install:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Windows users can also run:

```text
RUN_JAR_TRANSLATOR.bat
```

For a portable build:

```text
BUILD_PORTABLE_EXE.bat
```

## Safety model

The application intentionally prefers a failed/blocked build over silently damaging a game archive.

- Source JAR is not overwritten.
- Signed JARs are refused.
- Unknown/raw binary data is discovery-only.
- Binary patching is enabled only for recognized safe framing.
- Charset conversion is not silently forced.
- Placeholder mismatches are rejected on JSON import.
- Regression failure marks the output invalid.

## Project structure

```text
app.py                     GUI entry point
gui/                       PySide6 user interface
core/                      scanner, patcher, builder, validators, JSON protocol
models/                    scan/result data models
exporters/                 export helpers
tests/                     regression tests
docs/                      current documentation
*.py                       optional CLI diagnostic tools
*.bat / *.vbs              Windows launch/build helpers
JAR_Translator.spec        PyInstaller configuration
```

## Testing

Run the regression tests individually, or use:

```bash
python tests/test_v46_json_protocol.py
```

The repository keeps only the maintained regression tests for the current responsive UI, Deep Scan, Precision Scan, JSON Exchange, and Strict JSON Protocol behavior. Historical tests tied to superseded scanner assumptions are intentionally excluded.

## Limitations

Some J2ME games store language data in custom compressed/encrypted containers or construct text at runtime. Deep Scan may discover these strings, but unknown `deep-*` resources are not automatically patched until their structure is understood.

Font compatibility also depends on the game runtime and bundled font/glyph resources. Detection does not guarantee that every Vietnamese glyph can be rendered.

## Release

See [CHANGELOG.md](CHANGELOG.md) for the current public release history.

## Repository policy

Do not commit copyrighted game JARs, translated commercial game assets, personal translation projects, API keys, build outputs, runtime logs, or temporary files.

### Instant JAR loading
Opening a JAR immediately displays its archive tree. Language extraction continues on a worker thread and the UI displays `Đang quét` until the scan completes. Very large result sets are render-capped to keep the desktop UI responsive.

## Fluent UI reference layout
The desktop UI is implemented from the supplied Fluent-style reference: compact four-step workflow, 20/50/30 three-column workspace, five-column translation table, right-side inspector/editor, and a compact progress status bar. The UI remains PySide6 so the existing application engine does not need to migrate Qt bindings.

Opening a JAR immediately populates the file tree from the ZIP central directory; language scanning then continues on a background worker. JSON import and autosave also remain off the GUI thread.

## Non-blocking Safe Build

Build JAR is executed as a background transaction. Preflight checks are consolidated into one warning summary, the live project is snapshotted before the build starts, and the generated archive is first written to a temporary `.building` file. Only a structurally valid ZIP/JAR is atomically published to the selected output path. Detailed patch and regression results are saved in `<output>.build-report.json`.

### Light Monokai-inspired interface
The default interface now uses the approved light mockup: light editor/inspector panels, dark archive Explorer, magenta primary actions, mint/amber status accents, and a Fluent-style three-column workspace. This is a presentation-only change; scanning, JSON exchange, and safe JAR build behavior are unchanged.

### Scan performance and Build monitor
Opening a JAR shows the ZIP structure immediately. Normal language discovery now starts with an adaptive fast scan of patchable/known resources. A full deep scan is reserved for projects where the fast pass finds almost no usable text, avoiding expensive scans of asset-heavy `.img`, `.map`, and `.sce` archives during normal use.

Build JAR opens a live monitor as soon as the output path is selected. It shows preflight, glyph/compatibility checks, patch/write progress, ZIP/CRC/class validation, regression verification and final publish status. The monitor includes elapsed time, an estimated time remaining and a timestamped task log. Warnings are kept in this single monitor instead of appearing as repeated popups.


## Windows Portable

GitHub Actions builds a self-contained Windows portable package named `JAR_Vietnamese_Translator_Windows_Portable.zip`. It includes the PySide6/Qt runtime and does **not** require Python to be installed on the target PC. Extract the whole ZIP, then run `JAR Vietnamese Translator.exe`.
