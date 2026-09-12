# Runtime Compatibility Architecture

## Current execution model

The project currently has two mirrored Python trees:

- `app/` — used by the portable launcher. `launcher.py` inserts `app/` at the front of `sys.path` and executes `app/bootstrap.py`.
- repository root packages (`core/`, `gui/`, …) — still used by tests and developer tooling.

Because both trees are active in different execution paths, deleting either tree without changing the launcher/test architecture can break the application.

## Canonical direction

For the current release line, `app/` remains the portable runtime tree. New runtime-compatibility work must be mirrored into root modules until consolidation is completed.

The test `tests/test_v416_dual_tree_sync.py` guards semantic parity for:

- `core/runtime_profiles.py`
- `core/runtime_api_analyzer.py`
- `core/compatibility_analyzer.py`

Comments may differ, but executable Python AST must remain equivalent.

## RG35XX / FreeJ2ME compatibility flow

1. Read `META-INF/MANIFEST.MF` and record MIDP/CLDC target.
2. Scan `.class` constant pools for optional/vendor API signatures.
3. Detect WMA/SMS (`javax.wireless.messaging`, `MessageConnection`, `TextMessage`, `BinaryMessage`, `sms://`).
4. Detect vendor APIs (Nokia, Samsung, Siemens, Sony Ericsson, Motorola).
5. Detect optional APIs (M3G, Bluetooth, FileConnection, MMAPI).
6. Evaluate findings against the `freej2me_rg35xx` runtime profile.
7. Produce generic runtime risk plus RG35XX-specific score/risk.
8. Feed the result into Compatibility Analyzer and Build Preflight.

## WMA policy

The translator/compatibility toolkit does not send real SMS and does not treat blocked SMS transport as successful activation.

Current policy is diagnostic-first:

- identify the dependency,
- identify affected classes and SMS endpoints when statically visible,
- report target-runtime risk,
- recommend emulator/runtime compatibility work rather than silently changing activation state.

## Consolidation plan

A future cleanup should remove the dual-tree architecture only after all of these are updated together:

1. `launcher.py` / portable entry point,
2. PyInstaller spec and portable build scripts,
3. imports in GUI/core modules,
4. tests and developer scripts,
5. GitHub Actions workflows.

Until then, semantic sync tests are mandatory for compatibility modules.
