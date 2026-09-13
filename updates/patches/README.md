# JVT Patch Archive

Kho lưu patch độc lập cho **JAR Vietnamese Translator** để có thể tra cứu, tải lại và kiểm tra lịch sử thay đổi khi cần.

## Quy ước

- Mỗi patch có `patch_id`, SHA-256, dependency (`requires`) và mô tả thay đổi.
- Cài patch theo thứ tự dependency; không bỏ qua patch được khai báo trong `requires`.
- Ưu tiên cài bằng **Update Patch** trong app để dùng cơ chế backup/rollback.
- Patch có `restart_required: true` cần khởi động lại app sau khi áp dụng.
- Khi thuật toán scanner thay đổi, cần scan lại JAR và export JSON mới; JSON cũ có thể không còn khớp candidate set.

## Log và chỉ mục

- `CHANGELOG.md`: mô tả chi tiết từng patch.
- `patch-index.json`: chỉ mục máy đọc được, gồm SHA-256, dependency và file bị thay đổi.
- `INSTALLATION.md`: hướng dẫn cài/rollback.

## Quy ước từ CORE-022 trở đi

Mọi patch mới phải được lưu vào thư mục này cùng lúc với log mô tả. Patch font không được tạo thêm luồng build riêng; **Build JAR** là entry point build duy nhất.
