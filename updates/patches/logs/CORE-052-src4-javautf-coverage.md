# CORE-052 — SRC4 / Java-UTF Coverage

Patch ID: `CORE-052-src4-javautf-coverage`

Package: `JVT_PATCH_CORE_052_SRC4_JAVAUTF_COVERAGE.zip`

SHA-256: `db1d14280a8456cd115e7d80cfc55eb2e573805f3c5574bd608c035a1bcf4754`

Status: **static/integration PASS · user-confirmed runtime PENDING**

Date: 2026-09-21

Requires: `UI-051-recovery-confirmation-gate`

## Real-game evidence

Game: `仙剑奇侠传-2004.jar`

Source SHA-256:

`75aaf194cbd01715d4eaa99720e6876ff2355e494d3ed5f09c33d85cae81b100`

Original exported JSON contained 192 items. Audit found:

- 1,410 missed `src/*.src4` language occurrences;
- 11 missed CJK class strings;
- 1 missed one-character Java-UTF string `酒` in `data.pak`;
- false positive `L罁` inside embedded GIF data;
- two internal ASCII runtime/debug strings that should not be exported.

After CORE-052 on the exact UI-051 runtime baseline:

- exported items: **1,611**;
- SRC4 record-4/5 items: **1,410**;
- class-string items: **146**;
- canonical Java-UTF `data.pak` items: **55**;
- `酒`: present;
- `L罁`: absent;
- internal debug ASCII strings: absent.

## Scanner changes

- Dedicated structured `.src4` parser.
- Five-record RMS container support.
- Record 4/5 LSB-first LZ decompression.
- Java/J2ME `DataInputStream.readUTF()` framing.
- Canonical `u16be byte-length + Modified UTF-8` detection for `.pak`.
- One-character CJK support.
- Embedded GIF region parsing to suppress binary/image false positives.
- CJK class strings containing UI slash notation such as `3/上`, `返回/退出` are retained instead of being mistaken for paths.
- Confirmed debug strings such as `Unknown script command : ` and `has not prefecthed` are filtered.

## Build support

CORE-052 stages structured resources before the existing scene-script build layer.

Supported round trip:

- `src4:r4:java-utf:safe`;
- `src4:r5:java-utf:safe`;
- `binary:java-utf-u16be:safe` for canonical Java-UTF `.pak` strings.

SRC4 build transaction:

1. Validate original Java-UTF field at decompressed offset.
2. Patch from high offset to low offset.
3. Encode Java Modified UTF-8 and update u16be byte length.
4. Recompress record 4/5 with game-compatible literal LZ tokens.
5. Rebuild the five-record container.
6. Verify records 1–3 remain byte-identical.
7. Decompress rebuilt record and verify translated Java-UTF payload.

## Validation on exact UI-051 app baseline

The user supplied the actual `app/` directory from the installed UI-051 runtime.

Validation completed:

- Python compile: **PASS**.
- Patch ZIP integrity: **PASS**.
- Manifest JSON: **PASS**.
- Per-file SHA-256 payload verification: **PASS**.
- Install using the real `PatchUpdater` on a clean copy of the supplied `app.zip`: **PASS**.
- Files applied: **5**.
- CORE-026 scene support still installed: **PASS**.
- CORE-052 structured support installed: **PASS**.
- Real-game re-scan/export count: **1,611**.
- Real-game structured build smoke:
  - one `data.pak` Java-UTF translation: PASS;
  - one SRC4 record-4 translation: PASS;
  - one SRC4 record-5 translation: PASS;
  - patched=3, failed=0;
  - structural validation: PASS;
  - regression validation: PASS;
  - direct post-build translated payload verification: PASS.

## Runtime promotion gate

Do not promote CORE-052 to runtime stable until the user installs this exact patch on the Windows app and confirms:

- app starts normally;
- the test JAR scans successfully;
- exported JSON contains 1,611 items;
- Build completes with translated SRC4/PAK content;
- game launches and translated dialogue/items display correctly.

UI-051 remains the runtime-confirmed stable baseline until that confirmation.
