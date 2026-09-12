# Async Build Reliability Update

- Build Readiness, Glyph and Compatibility preflight now run off the GUI thread.
- All preflight warnings are consolidated into one confirmation dialog.
- JAR rebuild/patch/CRC/class/regression verification runs in a dedicated BuildWorker.
- The Build button is locked during a build to prevent overlapping transactions.
- TranslationProject is snapshotted before build so edits/imports cannot mutate an in-flight build.
- JAR output is written to a `.building` temporary archive and atomically published only after structural validation.
- Structural ZIP/class failures never overwrite an existing good output.
- Regression/translation mismatches are summarized once in the final report instead of generating repeated popups.
- Build progress uses an indeterminate status progress bar while worker tasks are running.

## Modern Fluent Workspace

- Visible product name and window title standardized to `JAR Vietnamese Translator`; release versions are no longer appended to the title.
- Rebuilt the primary desktop UI as a dark Fluent-style 3-column workspace: Explorer / Translation Editor / Inspector.
- Replaced the crowded legacy toolbar with four workflow stages: Load & Analyze, Translation & Editing, Validation, Publish.
- Build JAR is now the fixed primary CTA.
- Removed project/runtime/regression clutter from the main toolbar; secondary tools live under the gear menu.
- Translation table simplified to Status / Original / Vietnamese / Source with translated/review/untranslated status tags.
- Added JAR tree search, source/status filters, translation progress, UTF-8 byte counters, autosave control and save-next workflow.
- Ctrl+S saves the current translation and advances; Ctrl+F focuses global string search.
- Existing V4.14 binary framing verification and rebuild engine remain unchanged.

## V4.14 - Direct Binary Framing Verify

- Replaced heuristic post-patch binary rediscovery with deterministic framing verification.
- Verifies u8/u16 length prefix, exact UTF-8 payload bytes, bounds, and null terminators after variable-length patching.
- Keeps resource-level transactional rollback on any framing mismatch.
- Fixes false rollback of valid Vietnamese translations in `item.bin` and `property.bin`.
- Verified against the uploaded 仙侣情缘之麒麟劫 build: 386/386 `item.bin` and 57/57 `property.bin` binary fields patch successfully.

## V4.14 - Direct Binary Framing Verify

- Removed full `refresh_strings()` table rebuild after translated JSON import.
- Imported translations are committed in bulk, then only currently materialized rows are updated.
- UI row updates are chunked to 32 rows per Qt event-loop turn.
- Autosave disk serialization/writes moved to a background `AutosaveWorker`.
- Repeated autosaves are coalesced instead of stacking worker threads.
- Keeps V4.12 async parse/validation and V4.11 transactional rebuild safety.
- Full regression suite: 24 tests passing.

## V4.12 - Async JSON Import

- Moved translated-JSON parsing, JAR SHA-256 verification and item validation off the GUI thread.
- Added non-mutating prepare-import stage; translations are committed only after validation completes.
- Bulk-applies accepted translations instead of hundreds/thousands of `project.set()` calls.
- Suppresses QTableWidget repaint/signals/sorting during post-import refresh.
- Added regression tests including the real 559-item translated JSON workflow.
- Full test suite: 21 passed.

## V4.11 - Translation / Rebuild Safety

- Added transactional binary-resource rebuilding: one invalid/oversize translated field now rolls back the entire resource instead of leaving a partial patch.
- Added post-patch structured verification: every translated safe binary field must be rediscovered as a patch-safe framed field before the resource is accepted.
- Verified variable-length Vietnamese UTF-8 replacements update u8/u16 framing correctly.
- Verified longer Vietnamese text can replace Java CONSTANT_Utf8 strings using Modified UTF-8 without corrupting the class constant pool.
- Rejects bare resource-extension tokens such as `.map` while preserving the real `map` UI label.
- Added V4.11 rebuild-safety regression tests; full suite: 19 passed.

# Changelog

## V4.10 - Precision Language Filter

- Reject accidental printable/length-prefixed ASCII garbage from binary config tables.
- Reject command-script streams embedded in binary resources.
- Reject common prefixed engine tokens, script commands, path fragments, MIDlet metadata keys, and class/type identifiers.
- Preserve CJK strings and known player-facing UI labels.
- Added V4.10 precision regression tests based on false positives observed in the real 745-item V4.9 export.
- Full automated suite: 14 tests passing.


## V4.9 - Structured Binary Field Parser
- Merge u8/u16be/u16le/null-terminated detections instead of choosing one framing for an entire binary file.
- Detect nested `[length][UTF-8 text]` fields inside larger J2ME binary records.
- Prefer smaller, higher-confidence patch-safe fields over unsafe enclosing records.
- Patch only UTF-8/ASCII framed fields; GBK/GB18030/Big5 discoveries remain read-only because Vietnamese output is UTF-8.
- Update only the matched field length prefix when translated UTF-8 byte length changes.
- Scan every possible length-prefix position so nested fields are not skipped.
- Added structured-field regression coverage for Chinese item records and binary false-positive safety.

## V4.8 - Binary Text Recovery
- Recover valid UTF-8 islands embedded inside binary records instead of exporting mojibake.
- Preserve structural/raw bytes during discovery so no source bytes are silently discarded.
- Stop treating cp1252/latin-1 as a generic binary language decoder; this reduces random cfg/bin false positives.
- Downgrade mixed binary records with internal control/length bytes from patch-safe to discovery-only unsafe.
- Keep plain framed UTF-8 text patch-safe when the payload contains no structural binary bytes.
- Added V4.8 regression tests for mixed UTF-8 Chinese records and patch-safety classification.

## 4.7 – Extractor V3

- Added multi-encoding detection for UTF-8, UTF-16, GB18030/GBK and Big5.
- Added CJK raw-run discovery for binary/non-standard JAR resources.
- Added UTF-8 mojibake recovery before language classification/export.
- Added CJK-aware scoring to prevent real Chinese/Japanese/Korean strings being filtered out.
- Improved Java Modified UTF-8/CESU-8 decoding for supplementary Unicode characters.
- Added V4.7 extractor regression tests while keeping all V4.2–V4.6 tests passing.
- Kept `jar-translator-exchange-v2` output contract unchanged.


## 4.6 – Strict JSON Protocol

- Replaced API-based translation with manual JSON exchange.
- Added `jar-translator-exchange-v2`.
- Added mandatory translation rules and exact output contract.
- Added source JAR SHA-256 validation.
- Added per-string SHA-256 validation.
- Added placeholder manifests and import validation.
- Added item-count, duplicate ID/key, and immutable metadata validation.
- Kept backward-compatible import for V1/simple JSON formats.

## 4.5 – JSON Exchange

- Removed OpenAI/Gemini API integration.
- Removed API key and credential-storage requirements.
- Added JSON export/import workflow for external ChatGPT/Gemini translation.

## 4.4 – Precision Scan

- Added precision-first per-string classification.
- Reduced Java descriptors, class names, paths, URLs, identifiers, and other technical false positives.

## 4.3 – Deep Scan

- Expanded language discovery to non-standard JAR resources, ASCII, UTF-8, UTF-16LE and UTF-16BE.

## 4.2 – Responsive UI

- Added adaptive toolbar, splitters, table sizing and compact layouts for smaller displays.

## 4.0 – Stable Pipeline

- Integrated scan, safe build, readiness, regression validation, runtime packaging and runtime log analysis.

## UI refinement – Fluent mockup alignment
- Rebuilt the top area to match the approved preview: compact app bar + four large workflow stages + fixed Build JAR CTA.
- Removed the visible cluster of individual toolbar buttons; stage commands are now grouped inside stage menus.
- Increased spacing, contrast, corner radius and hierarchy to match the preview.
- Reworked the workspace cards and inspector header, including previous/next navigation and current-row indicator.
- Moved translation progress into the bottom status bar, matching the preview layout.
- Kept the product title exactly `JAR Vietnamese Translator` with no version suffix.
- Engine/rebuild behavior unchanged.

## UI fidelity pass
- Frameless dark custom title bar matching approved mockup.
- Native window controls recreated in app chrome.
- Workflow geometry and spacing increased.
- Workspace locked to 20/50/30 stretch proportions.
- Inspector editors enlarged and status bar raised for 1366x768 displays.

## Instant JAR Load / Explorer Fix
- JAR Explorer is now populated immediately from the ZIP central directory before deep language scanning starts.
- Added explicit background scan state: indeterminate progress, `Đang quét` status, and live archive entry count.
- Modern UI no longer rebuilds the retired hidden candidate table after scan completion.
- Added render safety cap (3000 rows) so pathological scans cannot freeze the GUI by creating massive QTableWidget contents at once.
- Deferred full-content CRC/deep checks to scan/build validation; instant preview no longer reads the entire JAR.

## Reference Fluent UI integration
- Rebuilt the main window from the user-provided PyQt6 Fluent UI reference while retaining the existing PySide6 engine/runtime.
- Unified dark palette: #121820 / #171F2A / #0F141C with Accent Blue #0066FF.
- Header is a compact 4-step workflow: Nạp & Phân tích, Dịch thuật & Biên tập, Kiểm tra, Xuất bản.
- Main workspace now follows the reference 3-column structure and 20/50/30 stretch factors.
- Translation table now uses 5 columns: #, Trạng thái, Original, Vietnamese, Nguồn.
- Inspector follows the reference editor/metadata arrangement with UTF-8 byte counts and previous/next navigation.
- Preserved instant JAR tree preview, background scan, async JSON import, safe binary/class rebuild, and autosave workers.
- App name remains exactly "JAR Vietnamese Translator" with no version suffix in window/application titles.

## Fluent Dark UI Layer Refactor

- Kept PySide6 as the Qt binding; no PyQt6 migration and no QDarkStyle dependency.
- Moved the full visual system into `gui/fluent_theme.py` so presentation changes no longer touch scanner/import/build controllers.
- Added `WorkflowStep` custom widget for the four-stage workflow header.
- Added `StatusBadgeDelegate` so translation status is rendered as Fluent rounded badges without per-row child widgets.
- Styled ComboBox popups, scrollbars, splitter handles, tooltips, menus, checkboxes and table headers to prevent native light controls from leaking into Dark Mode.
- Preserved 20/50/30 Explorer / Editor / Inspector workspace, instant JAR preview, background scan/import/build and transactional JAR output.
- No version number is appended to the visible app/window title.

## Light Monokai-inspired UI refresh
- Replaced the Fluent Dark presentation layer with a light Monokai-inspired palette matching the approved preview.
- White/light-gray workspace, magenta primary CTA/progress, mint translated badges, amber review badges.
- Explorer remains dark slate for strong hierarchy and code-oriented contrast.
- Added app subtitle, light-theme sun affordance, suggestion card, and light-native menus/scrollbars/inputs.
- Engine, async scan/import/build and transactional JAR patching remain unchanged.

## Performance + Build Monitor
- Default language scan now uses a fast adaptive pass first (class constants + known text/binary resources) instead of deep-scanning every `.img/.map/.sce` entry.
- Deep Scan is only used automatically when the fast pass finds almost no language, preventing large false-positive scans from blocking normal projects.
- Scanner reports live percentage/file status and can publish fast-pass results before fallback analysis completes.
- Binary framed-candidate overlap merging changed from quadratic behavior to an interval/bisect strategy.
- High-frequency u8/u16 probes use a fast decoder while mixed-binary recovery remains available in the discovery path.
- Prevent overlapping scans and keep QThread references until the real `finished` signal, avoiding `QThread destroyed while running` instability.
- Added a live Build JAR monitor with task checklist, task log, percentage, elapsed time and estimated remaining time.
- Build preflight warnings are consolidated into the monitor instead of repeated modal dialogs.
- JAR build emits progress while writing entries, validating CRC/classes, running regression and publishing output.
- Regression validation now groups translations by source and analyzes each class/binary resource once instead of once per string.
- Regression output rescan is fast-mode rather than full deep discovery.
