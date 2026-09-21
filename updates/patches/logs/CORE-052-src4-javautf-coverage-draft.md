# CORE-052 — SRC4 / Java-UTF Coverage (Development Evidence)

Status: **ENGINE VALIDATED · RUNTIME INTEGRATION PENDING**

Date: 2026-09-21

Baseline requirement: **UI-051-recovery-confirmation-gate** (user-confirmed runtime stable).

## Evidence from real game

Game: `仙剑奇侠传-2004.jar`

Source SHA-256:

`75aaf194cbd01715d4eaa99720e6876ff2355e494d3ed5f09c33d85cae81b100`

The exported JSON contained 192 items, but independent audit confirmed:

- 189 meaningful Chinese occurrences already exported;
- 1 false positive inside an embedded GIF payload (`image.pak`, `L罁`);
- 12 directly missed strings outside SRC4;
- 1,410 missed strings in 18 `src/*.src4` resources;
- SRC4 record 4: 55 Java-UTF language fields;
- SRC4 record 5: 1,355 Java-UTF language fields;
- confirmed Chinese occurrences in the tested game: at least 1,611;
- previous occurrence coverage: about 11.73%.

## Reverse-engineered SRC4 contract

Each `.src4` file contains five RMS-style records.

Records 4 and 5 use:

`[u16le bitstream_length][u16le decompressed_length][LSB-first LZ bitstream]`

After decompression, player-facing strings use Java/J2ME `DataInputStream.readUTF()` framing:

`[u16be byte_length][Modified UTF-8 payload]`

The structured engine implements:

- five-record split/rebuild;
- LSB-first game-compatible decompression;
- Java Modified UTF-8 decode/encode;
- exact Java-UTF framing;
- transactional record patching from high offset to low offset;
- literal-only game-compatible recompression for deterministic safe output;
- preservation check for untouched records 1–3;
- post-rebuild decompression + translated payload verification;
- structural GIF region parsing to suppress candidates inside embedded image streams.

## Real-game validation

Standalone analyzer on the supplied JAR:

- 18/18 SRC4 resources parsed;
- 1,410 SRC4 language occurrences recovered;
- 55 Java-UTF fields found in `data.pak`;
- one-character `酒` retained;
- 31 embedded GIF streams identified;
- known false-positive offset 14743 correctly classified inside GIF data.

Local SRC4 round-trip smoke test:

- patch record-4 text: PASS;
- patch record-5 name: PASS;
- recompress/rebuild: PASS;
- records 1–3 byte-identical: PASS;
- translated Java-UTF rediscovered after rebuild: PASS.

GitHub regression:

- `tests/test_core052_structured_src4.py`
- workflow run 35604231788: **SUCCESS**

## Repository integration safety gate

The current repository `main` does not materialize the cumulative runtime source for CORE-026 → CORE-040 → UI-051. Commit history for `core/jar_scanner.py` / `core/jar_builder.py` stops at the earlier materialized baseline; later scene/binary functionality was distributed as modular patch artifacts and documented in the patch archive.

Therefore CORE-052 must **not** replace `app/core/jar_scanner.py` or `app/core/jar_builder.py` from current `main`, because that could regress:

- CORE-026 scene-script scan/build;
- CORE-039 exact binary whitespace;
- CORE-040 binary frame overlap behavior.

The structured module is intentionally additive until the exact currently installed cumulative `app/core` source is supplied/recovered.

## Promotion requirements

Before CORE-052 can become an installable patch:

1. Obtain the current cumulative `app/core` source from the UI-051 installation.
2. Integrate structured SRC4/Java-UTF logic into that baseline.
3. Preserve scene-script kinds/build behavior.
4. Preserve CORE-039/040 contracts.
5. Run compile + regression.
6. Run real-game scan and compare against the audit counts.
7. Build/import Vietnamese test strings into both `data.pak` and `src4`.
8. Verify output JAR structural/regression checks.
9. Package as `jvt-patch-v1`.
10. Mark runtime status pending until user installs/tests it.
