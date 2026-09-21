# JAR Vietnamese Translator — Patch Archive

Thư mục này là kho patch chuẩn của **JAR Vietnamese Translator**.

## Quy định bắt buộc

- Mỗi patch mới phải có `manifest.json`, `patch_id`, SHA-256, dependency và mô tả thay đổi.
- Mỗi lần phát hành patch phải cập nhật `CHANGELOG.md` và `patch-index.json`.
- Trước khi đánh dấu stable, patch phải qua ZIP integrity, manifest/hash payload, Python syntax và test chuyên biệt nếu có.
- Runtime test thực tế được ghi riêng; không coi static/package validation là runtime validation.

## Current head

`UI-051-recovery-confirmation-gate`

Chuỗi nền tảng stable qua CORE-026 được giữ trong `patch-index.json`. Toàn bộ patch từ CORE-027 đến UI-051, package SHA-256, dependency và status được ghi trong:

> UI-051 hiện là **recommended head** và đã được người dùng xác nhận chạy ổn định trên Windows; đây là baseline runtime-confirmed hiện tại.

- `POST_CORE026_PATCHES.json`
- `CHANGELOG.md`
- `patch-index.json`

## Các mốc quan trọng sau CORE-026

- CORE-027/028: scene JSON export + fast JSON import.
- UI-029 → UI-034: JSON import progress, statusbar fixes, responsive import và restore modern UI.
- UI-035 → UI-038: branding + recovery performance.
- CORE-039/040: binary whitespace preservation + binary frame overlap fix.
- UI-041 → UI-045A: large JSON performance, Light Monokai progress, Build progress, zero-scroll hydration.
- UI-046: virtual table experiment — **archived** do runtime lag.
- UI-046R: rollback về QTableWidget.
- UI-047: QTableWidget fast path.
- UI-048: full sync trong Import/Recovery progress.
- UI-049: giảm batch sync xuống 20 dòng/lần.
- UI-050: Recovery progress match JSON progress.
- UI-051: Recovery confirmation gate — chỉ mở progress sau khi người dùng bấm Yes. **User-confirmed Windows runtime PASS; stable baseline.**
- CORE-052: structured SRC4 + Java-UTF `.pak` coverage; real-game scan/export **1,611** items and build smoke PASS. **Runtime user-test pending; UI-051 remains recommended head.**

## Patch archived / superseded

- CORE-009: superseded bởi CORE-010.
- UI-011: superseded bởi UI-012.
- UI-046: archived vì load lâu và click/double-click lag trong runtime thực tế.

## Binary ZIP publication

GitHub connector hiện tại chỉ cho phép tạo/cập nhật nội dung UTF-8 qua Contents API và **không upload arbitrary binary ZIP**. Vì vậy repository hiện lưu catalog, SHA-256, dependency, changelog và trạng thái patch; không được coi tên package trong catalog là bằng chứng ZIP binary đã nằm trên GitHub.

Binary patch chỉ được xem là đã publish lên GitHub khi repository listing thực tế hiển thị file `.zip` hoặc có GitHub Release/Artifact đã xác minh.
