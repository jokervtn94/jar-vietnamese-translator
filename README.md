# JAR Vietnamese Translator

Desktop tool for scanning, translating, patching, rebuilding, and validating Java/J2ME `.jar` games with a focus on Vietnamese localization.

## Current application

- Visible app name: **JAR Vietnamese Translator**
- PySide6 desktop UI
- Light Monokai-inspired interface
- Fast Adaptive Scan with deep-scan fallback
- Precision language filtering
- JSON translation exchange (`jar-translator-exchange-v2`)
- Async JSON import/autosave
- Safe class/resource/binary patching
- Async atomic JAR build
- Build JAR Monitor with task log, percent, elapsed time, ETA, warnings and errors
- ZIP/CRC/class validation and regression verification before publish

## Translation workflow

1. Open a Java/J2ME `.jar`.
2. The archive tree appears immediately while language scanning continues in a worker thread.
3. Review detected language strings.
4. Export translation JSON.
5. Translate only `items[].translation` with ChatGPT/Gemini according to the embedded protocol.
6. Import the translated JSON.
7. Review translations and compatibility warnings.
8. Build the Vietnamese JAR.
9. Follow build progress in the live Build JAR Monitor.
10. Test the rebuilt game in the target runtime/device.

## JSON protocol

The current exchange format is `jar-translator-exchange-v2`.

The import validator checks source JAR identity, item count, duplicate keys, immutable metadata, original text hashes, placeholders and translation structure.

See [docs/JSON_PROTOCOL.md](docs/JSON_PROTOCOL.md).

## Safe rebuild

The builder writes to a temporary `.building` archive first. It validates the generated ZIP/JAR and runs translation regression checks before atomically publishing the requested output. A failed structural build does not overwrite the previous good output.

## Performance

Normal discovery begins with a fast scan of known/patchable resources. Deep scanning is reserved for cases where the fast pass finds too little usable language data. Large result sets are render-capped to avoid freezing the Qt table while the backend retains the complete result set.

## Build monitor

Build JAR displays live stages for:

1. Build readiness
2. Font/glyph checks
3. Compatibility checks
4. Snapshot/temp preparation
5. Class/resource/binary patching
6. ZIP/CRC/class validation
7. Translation regression validation
8. Atomic publish

The monitor shows timestamped task logs, progress, elapsed time and estimated remaining time.

## Run from source

Python 3.12 is recommended.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

## Tests

```bash
python -m pytest -q
python -m compileall -q .
```

The current maintained suite contains **35 regression tests**.

## Windows Portable

GitHub Actions builds:

`JAR_Vietnamese_Translator_Windows_Portable.zip`

The package includes `JAR Vietnamese Translator.exe` and the required Python/PySide6 runtime, so Python does **not** need to be installed on the target Windows PC. Extract the entire ZIP before launching the EXE.

## Repository policy

Do not commit copyrighted commercial game JARs, translated game assets, personal translation projects, API keys, temporary build files or runtime logs.
