# Patch Changelog

Cập nhật archive: **2026-09-13 R4**

## Stable validation policy

Mỗi patch stable phải qua tối thiểu: ZIP/CRC, parse `manifest.json`, SHA-256 payload, compile syntax với Python payload và test chuyên biệt nếu patch có parser/build logic. Runtime test thực tế vẫn được ghi riêng; package validation không được mô tả thành runtime validation nếu chưa chạy trên Windows/KEmulator.

## Stable install chain

`UI-001 → UI-002 → UI-003 → UI-004 → UI-005 → UI-006 → CORE-007 → CORE-008 → CORE-010 → UI-012 → CORE-013 → CORE-014 → CORE-015 → CORE-016 → CORE-017 → CORE-018 → CORE-019 → CORE-020 → CORE-021 → CORE-022 → UI-023 → UI-024 → UI-025 → CORE-026`

## CORE-026 — Scene Script Language Coverage

- Bổ sung parser chuyên biệt cho resource hỗn hợp binary/text `scene/*.sce`.
- Chỉ lấy operand ngôn ngữ người chơi nhìn thấy từ `say` và các biến thể, `info`, `choose`, `black`, `amission`, `poem`, `text`, `fight`, `csprite` và tên NPC dạng `u8-length + UTF-8 + NUL`.
- Không export opcode, event ID, tọa độ, sprite ID, animation token và technical token.
- `fight` tách khỏi delimiter `@`/`&`; `choose` tách khỏi delimiter `|` để không cho bản dịch phá cú pháp script.
- Thêm transactional scene build staging: patch theo offset giảm dần, update length byte của NPC name, giữ nguyên số delimiter `;`, CRC-check stage và verify UTF-8 translation trong JAR cuối.
- Nếu scene verify thất bại, output JAR bị xóa.
- Real-JAR validation với `仙侣情缘之麒麟劫320x240.jar`: **119** file `.sce`, **1946** safe scene strings, **0** unmatched CJK scene segment sau scene-specific coverage audit, syntax PASS, patch smoke PASS.

SHA-256 package: `055759d04691a678a3040f48b17fb3ec6a332c7d9484473686fabd923259fecb`

Chi tiết: `updates/patches/logs/CORE-026-scene-script-language-coverage.md`

## UI-025 — Transparent Label Backgrounds

- Sửa `QLabel` kế thừa background của global `QWidget`, gây các khung label lệch màu với card/panel.
- Label thông thường chuyển sang transparent để dùng đúng surface của parent.
- Giữ nguyên background có chủ đích của `AppMark`, `StepBadge` và các badge trạng thái.

SHA-256 package: `d621d37039238402cc697c1333d90549b42ecc8c16704f911e12e7d0962ade9f`

## UI-024 — Remove Redundant Edit Button

- Loại bỏ nút **Biên tập** khỏi ribbon vì nút cũ chỉ `setFocus()` vào bảng giữa.
- Sau UI-023, bảng giữa read-only; chỉnh sửa chỉ thực hiện tại panel **Chỉnh sửa chuỗi** bên phải.

SHA-256 package: `d0949287b711ec3273da3cc300ddf7d161fa3329a08ab21fcd701c7bfef3fa23`

## UI-023 — Translation Table Read-only

- Tắt inline editing trong bảng chuỗi.
- Double-click chỉ chọn dòng/focus editor bên phải.

SHA-256 package: `ed295af310fe2bd75ae8f007ea9284174772a86f52ceda1c952a42a51992aeac`

## CORE-022 — Font-aware Single Build Flow

- Font subsystem chỉ phân tích/tích hợp font; **Build JAR** là build entry point duy nhất.
- Nếu đủ glyph: build trực tiếp. Nếu thiếu: chọn TTF/OTF rồi Build JAR tự áp dịch + font + regression.

SHA-256 package: `51c16af646998b0bbc28f0cd7f47fe6cbfd75293563c96a71705e008131ceaf7`

## CORE-021 — Residual CJK + Technical Token Filter

- Final precision gate loại path, filename, Java descriptor, resource identifier, snake/camel-case, code/debug token và font-map data.
- Giữ short CJK UI thật.
- Residual CJK audit tách khỏi JSON export.

SHA-256 package: `b5c88e04fddf05edb28e2571b4962bc791b10faac8252849c5fdd3faab85e4a2`

## CORE-020 — Font Loader + CJK Complete Scan

- Patch hard-coded `char.txt` byte length trong proprietary font loader.
- CJK Complete Scan giữ CJK patch-safe bị heuristic cũ loại nhầm.

SHA-256 package: `67823905b25ff120ce148afb5c1fb96e33f62713905190b04f7f6ee1d6952d59`

## CORE-019 — Unified Translation + Font Build

- Pipeline đúng: apply translation → integrate Vietnamese glyphs → final regression validation.

SHA-256 package: `cdade4e8f63da4f520b3ce253042e92dea61e922a0b4b51dc1d571fe205e6b0a`

## CORE-018 — Vietnamese Bitmap Font Builder

- Phát hiện/ghi `char.txt + 13.FON`, Unicode 12×12 / 24 bytes-glyph và rasterize TTF/OTF cục bộ.

SHA-256 package: `5313ffaf5fc2a2ee7d07ac5630e27a9e90b23ed025ace0ac03c1b34128913d87`

## CORE-017 → CORE-007 / UI-012 / UI-001 → UI-006

Lịch sử chi tiết các patch compatibility, diagnostics, Open JAR, auto-restart và nền tảng UI vẫn được lưu trong repository history và `patch-index.json`. Chuỗi stable không bao gồm các patch superseded bên dưới.

## Superseded / archived

- `CORE-009-safe-single-word-scan`: superseded bởi CORE-010 do lỗi thiếu `pathlib.Path`.
- `UI-011-diagnostics-display-fix`: superseded bởi UI-012; bootstrap cũ có nguy cơ regression hook mới.

## Stable archive bundle

`JVT_PATCH_STABLE_ARCHIVE_20260913_R4.zip`

- SHA-256: `409c4a15d949ffcde1d3ab6aaf1b03289555ca9d635c608d1a89e6436a903c2b`
- **24 patch stable**.
- **2 patch archived/superseded**.
- Có README, CHANGELOG và patch-index nội bộ.
