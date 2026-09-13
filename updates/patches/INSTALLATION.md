# Patch Installation / Rollback

## Cài mới từ baseline portable v4.34

Cài đúng thứ tự trong `patch-index.json`. Chuỗi hiện tại:

`UI-001 → UI-002 → UI-003 → UI-004 → UI-005 → UI-006 → CORE-007 → CORE-008 → CORE-010 → UI-012 → CORE-013 → CORE-014 → CORE-015 → CORE-016 → CORE-017 → CORE-018 → CORE-019 → CORE-020 → CORE-021 → CORE-022 → UI-023`

Không cài `CORE-009` hoặc `UI-011` trên chuỗi hiện tại; hai patch này đã bị superseded.

## Quy tắc trước khi Apply Update Patch

1. Thoát mọi build/scan đang chạy.
2. Kiểm tra SHA-256 của ZIP theo `patch-index.json`.
3. Không đổi tên/cấu trúc file bên trong ZIP.
4. Apply bằng chức năng **Update Patch** của app.
5. Cho phép app tự restart nếu patch yêu cầu.
6. Sau restart, kiểm tra lại các chức năng bị ảnh hưởng theo CHANGELOG.

## Smoke test tối thiểu sau chuỗi stable

- Mở một `.jar` bằng workflow JAR, không bị hỏi patch ZIP.
- Scan ngôn ngữ hoàn tất, UI không treo.
- Technical token như path/filename/code token không xuất vào JSON dịch.
- Import JSON dịch hoạt động.
- Bảng chuỗi ở giữa không cho sửa inline; chỉ sửa ở panel bên phải.
- Diagnostics mở được dashboard 2×2.
- Phân tích font phân biệt được đủ glyph / thiếu glyph.
- Nếu font đủ: Build JAR chính build trực tiếp.
- Nếu font thiếu: chọn **Tích hợp font…**, sau đó vẫn build bằng nút **Build JAR** chính.
- Build report/regression không báo lỗi cấu trúc.

## Rollback

PatchUpdater tạo backup transactional trước khi thay file. Nếu apply thất bại, rollback tự động. Nếu cần rollback thủ công, dùng backup gần nhất trong thư mục update backup của portable và đối chiếu `CHANGELOG.md` + `patch-index.json` để xác định patch cuối đã áp.

## Stable archive

`JVT_PATCH_STABLE_ARCHIVE_20260913.zip`

SHA-256: `ea6b26a768fbc2c1febd4b4b7ec63a33b45534d61b454007ef381bb723753c17`

Archive gồm toàn bộ 21 patch stable và 2 patch superseded để đối chiếu lịch sử. Không lấy patch trong thư mục `archive/` để cài lên current chain.
