# Patch Changelog

## CORE-022-font-aware-single-build-flow
- Tách phân tích font khỏi build.
- Bỏ nút Build font/Build JAR + Font riêng.
- Build JAR là entry point duy nhất.
- Font đủ glyph: build ngay.
- Font thiếu glyph: chọn TTF/OTF rồi Build JAR tự áp bản dịch, tích hợp glyph và regression validation.
- SHA-256: `51c16af646998b0bbc28f0cd7f47fe6cbfd75293563c96a71705e008131ceaf7`

## CORE-021-residual-cjk-and-technical-token-filter
- Thêm final precision gate trước khi xuất JSON.
- Loại path, filename, Java descriptor, resource identifier, snake_case/camelCase, technical ASCII token và font-map data.
- Giữ nhãn CJK ngắn có khả năng là UI.
- Thêm Residual CJK discovery và post-build Chinese audit.
- SHA-256: `b5c88e04fddf05edb28e2571b4962bc791b10faac8252849c5fdd3faab85e4a2`

## CORE-020-font-loader-and-cjk-complete-scan
- Patch hard-coded byte-length của `char.txt` trong font loader khi thêm glyph Việt.
- Thêm CJK Complete Scan để giữ Chinese string patch-safe bị heuristic loại nhầm.
- SHA-256: `67823905b25ff120ce148afb5c1fb96e33f62713905190b04f7f6ee1d6952d59`

## CORE-019-unified-translation-font-build
- Sửa lỗi build font từ JAR gốc khiến bản build vẫn còn tiếng Trung.
- Pipeline: JarBuilder áp dịch -> font integration -> RegressionValidator trên JAR cuối.
- SHA-256: `cdade4e8f63da4f520b3ce253042e92dea61e922a0b4b51dc1d571fe205e6b0a`

## CORE-018-vietnamese-bitmap-font-builder
- Phát hiện `char.txt + 13.FON`.
- Xác định font Unicode 12x12, 24 byte/glyph.
- Phân tích glyph Việt thiếu và rasterize từ TTF/OTF.
- SHA-256: `5313ffaf5fc2a2ee7d07ac5630e27a9e90b23ed025ace0ac03c1b34128913d87`

## CORE-017 -> CORE-007
- CORE-017: tối ưu dependency graph + Startup Activation Deep Trace.
- CORE-016: loại compatibility sâu khỏi Open JAR tự động để tránh treo.
- CORE-015: sửa phân loại activation non-WMA trên startup path.
- CORE-014: bỏ WMA/SMS rescan đồng bộ sau scan.
- CORE-013: WMA/SMS Compatibility Assistant theo chính sách an toàn.
- CORE-010: hotfix thiếu `pathlib.Path`.
- CORE-009: lọc từ ASCII đơn mơ hồ trong class/code context.
- CORE-008: auto-restart sau Update Patch.
- CORE-007: tách workflow mở JAR và cài ZIP patch.

## UI patch chain
- UI-001 -> UI-006: layout 20/50/30, vector icon, grouped ribbon, compact header và hotfix.
- UI-011 -> UI-012: Diagnostics display fix và dashboard 2x2.

## Quy ước bắt buộc từ CORE-022
Mọi patch mới phải cập nhật `updates/patches/` cùng lúc và ghi rõ patch ID, dependency, file ảnh hưởng, thay đổi hành vi, regression/rủi ro và SHA-256 của ZIP.
