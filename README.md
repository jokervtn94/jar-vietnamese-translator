# JAR Vietnamese Translator

Ứng dụng desktop PySide6 hỗ trợ quét, trích xuất, biên tập bản dịch và rebuild game Java/J2ME dạng JAR theo quy trình an toàn.

## Điểm chính

- Giao diện Light Monokai-inspired, responsive theo kích thước cửa sổ.
- Fast Adaptive Scan để mở JAR và đưa kết quả lên giao diện nhanh hơn.
- Deep Scan tự động fallback khi fast scan chưa tìm đủ chuỗi ngôn ngữ.
- Lọc chuỗi kỹ thuật để giảm class/path/descriptor/URL và dữ liệu không phải ngôn ngữ.
- Hỗ trợ Modified UTF-8/CESU-8 trong `.class`.
- Hỗ trợ resource UTF-8, UTF-16, GB18030/Big5 và binary framed fields.
- Xuất/nhập JSON `jar-translator-exchange-v2` để dịch ngoài bằng ChatGPT/Gemini mà không cần API key.
- Import JSON chạy nền, tránh block GUI.
- Build JAR chạy nền và dùng file `.building` tạm trước khi publish atomically.
- Build JAR Monitor hiển thị task hiện tại, tiến độ, thời gian đã chạy, ETA, cảnh báo và lỗi.
- Regression validator phân tích mỗi source/binary một lần theo nhóm thay vì lặp lại cho từng chuỗi.

## Chạy từ source

Yêu cầu Python 3.12 khuyến nghị.

```bash
python -m pip install -r requirements.txt
python app.py
```

## Kiểm thử

```bash
python -m pytest -q
python -m compileall -q .
```

Bản source hiện tại có 35 regression tests.

## Windows Portable

GitHub Actions workflow `.github/workflows/build_portable.yml` tạo gói:

`JAR_Vietnamese_Translator_Windows_Portable.zip`

Gói Portable chứa `JAR Vietnamese Translator.exe` và không yêu cầu người dùng cài Python.

## JSON translation exchange

Format chính:

```json
{
  "format": "jar-translator-exchange-v2",
  "schema_version": 2,
  "target_language": "vi-VN",
  "items": []
}
```

Chỉ sửa `items[].translation`; các field định danh và metadata phải được giữ nguyên để import/rebuild an toàn.

## Safe rebuild

Build pipeline thực hiện:

1. preflight/readiness,
2. glyph và compatibility check,
3. snapshot translation project,
4. patch class/resource/binary,
5. ZIP/CRC/class validation,
6. regression validation,
7. atomic publish output JAR.

Nếu structural validation thất bại, file `.building` bị loại bỏ và output tốt trước đó không bị ghi đè.

## License / distribution

Ứng dụng sử dụng PySide6/Qt. Khi phân phối binary, cần tuân thủ các điều khoản license tương ứng của thư viện được đóng gói.
