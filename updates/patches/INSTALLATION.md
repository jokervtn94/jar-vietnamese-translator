# Hướng dẫn sử dụng patch

1. Mở **JAR Vietnamese Translator**.
2. Chọn **Update Patch → Cài Patch**.
3. Chọn ZIP patch cần áp dụng.
4. Đọc `requires` trong manifest hoặc `patch-index.json`; cài đủ dependency trước.
5. Xác nhận cài. App sử dụng backup/rollback hiện có.
6. Nếu patch yêu cầu restart, khởi động lại app hoặc để cơ chế auto-restart thực hiện.

## Khi nâng cấp scanner

Sau patch thay đổi thuật toán scan, phải mở lại JAR gốc, scan lại và export JSON mới. Không nên dùng JSON cũ vì danh sách candidate có thể thay đổi.

## Khi nâng cấp font

Luồng chuẩn từ CORE-022:

**Import bản dịch → Phân tích font → nếu đủ glyph thì Build JAR ngay; nếu thiếu glyph thì chọn Tích hợp font → Build JAR.**

Không còn nút build font riêng.

## Rollback

Nếu app lỗi sau patch, dùng backup do PatchUpdater tạo ra hoặc quay lại portable/baseline trước khi cài patch. Không trộn file thủ công giữa nhiều patch trừ khi đang phục hồi sự cố.
