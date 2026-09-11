# JAR Vietnamese Translator

Desktop tool for scanning, translating, patching, rebuilding, and validating Java/J2ME `.jar` games with a focus on Vietnamese localization.

Current release: **V4.6 – Strict JSON Protocol**

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
