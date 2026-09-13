# JAR Vietnamese Translator — Patch Archive

Thư mục này là kho patch chuẩn để lưu lại các bản cập nhật modular đã tạo cho **JAR Vietnamese Translator**.

## Quy định bắt buộc

- Mỗi patch mới phải có `manifest.json`, `patch_id`, SHA-256, dependency và mô tả thay đổi.
- Mỗi lần phát hành patch phải cập nhật `CHANGELOG.md` và `patch-index.json`.
- `stable/` là chuỗi patch hiện hành; `archive/` chỉ giữ patch cũ/superseded để rollback hoặc đối chiếu lịch sử.
- Không cài patch trong `archive/` lên trên chuỗi stable hiện tại.
- Trước khi đưa vào stable, ZIP phải vượt qua: ZIP integrity, hash từng payload theo manifest, Python syntax compile và JSON parse (nếu có).
- Kiểm tra cấu trúc/syntax không thay thế kiểm thử runtime Windows/KEmulator; trạng thái runtime được ghi riêng trong changelog.

## Chuỗi stable hiện tại

1. UI-001 — layout 20/50/30
2. UI-002 — icon/workflow header
3. UI-003 — icon/toggle polish
4. UI-004 — grouped header ribbon
5. UI-005 — header ribbon hotfix
6. UI-006 — compact vector header
7. CORE-007 — JAR open hotfix
8. CORE-008 — auto restart after patch
9. CORE-010 — safe single-word scan + Path import fix
10. UI-012 — Diagnostics dashboard 2×2
11. CORE-013 — WMA/SMS compatibility assistant
12. CORE-014 — scan freeze performance fix
13. CORE-015 — activation classification fix
14. CORE-016 — open JAR freeze hotfix
15. CORE-017 — startup activation deep trace
16. CORE-018 — Vietnamese bitmap font builder
17. CORE-019 — unified translation + font pipeline
18. CORE-020 — font-loader byte-length + CJK complete scan
19. CORE-021 — residual CJK + technical-token filter
20. CORE-022 — font-aware single Build JAR flow
21. UI-023 — translation table read-only
22. UI-024 — remove redundant Edit button from main ribbon

## Patch bị superseded

- CORE-009: superseded bởi CORE-010 vì CORE-009 thiếu `pathlib.Path` ở runtime.
- UI-011: superseded bởi UI-012; bootstrap cũ của UI-011 có thể làm mất các hook về sau.

## Stable archive bundle

Bản archive đầy đủ hiện tại:

- `JVT_PATCH_STABLE_ARCHIVE_20260913_R2.zip`
- SHA-256: `90bd69ffe16700143ae5c132c281e6506eddec2f95a875cdd1b5d75e8befb192`
- Chứa: 22 patch stable + 2 patch archived/superseded + README + CHANGELOG + patch-index.

Do GitHub connector hiện tại không nhận file binary trực tiếp qua Contents API, archive binary được giữ ngoài repository khi chưa có cơ chế upload artifact phù hợp. Luôn đối chiếu SHA-256 với `patch-index.json`.
