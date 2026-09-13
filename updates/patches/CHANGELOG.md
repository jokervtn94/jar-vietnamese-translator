# Patch Changelog

Cập nhật archive: **2026-09-13**

## Archive validation refresh

Toàn bộ package patch hiện có đã được kiểm tra lại trước khi đưa vào danh sách stable/archive:

- ZIP mở được và CRC/container hợp lệ.
- `manifest.json` parse được.
- SHA-256 của mọi payload khai báo trong manifest khớp nội dung ZIP.
- Mọi file Python trong patch compile syntax thành công.
- Mọi JSON payload parse thành công.

Lưu ý: kiểm tra trên xác nhận tính toàn vẹn package và syntax. Nó không thay thế test runtime Windows/KEmulator; những patch đã được người dùng test thực tế vẫn được giữ trong stable chain, còn patch có regression đã biết được chuyển sang archive/superseded.

## Stable install chain

`UI-001 → UI-002 → UI-003 → UI-004 → UI-005 → UI-006 → CORE-007 → CORE-008 → CORE-010 → UI-012 → CORE-013 → CORE-014 → CORE-015 → CORE-016 → CORE-017 → CORE-018 → CORE-019 → CORE-020 → CORE-021 → CORE-022 → UI-023`

## UI-023 — Translation Table Read-only

- Tắt hoàn toàn inline editing trong bảng **Chuỗi ngôn ngữ**.
- Click/double-click chỉ chọn dòng; double-click chuyển focus sang editor bên phải.
- Bản dịch chỉ được sửa tại panel **Chỉnh sửa chuỗi**.
- Loại lỗi editor QTableWidget bị cắt/chồng lên text trong cell.
- Không thay đổi Import/Export JSON, autosave hoặc pipeline build.

SHA-256 package: `ed295af310fe2bd75ae8f007ea9284174772a86f52ceda1c952a42a51992aeac`

## CORE-022 — Font-aware Single Build Flow

- Bỏ nút build font/build JAR + font riêng để tránh trùng chức năng.
- Font subsystem chỉ còn **Phân tích font** và **Tích hợp font…** khi thiếu glyph.
- Nếu font game đã đủ tiếng Việt: nút **Build JAR** chính build trực tiếp.
- Nếu thiếu glyph: chọn TTF/OTF, sau đó vẫn dùng **Build JAR** chính; pipeline tự áp bản dịch → tích hợp glyph → regression validation.
- Build JAR là entry point duy nhất để tạo game cuối.

SHA-256 package: `51c16af646998b0bbc28f0cd7f47fe6cbfd75293563c96a71705e008131ceaf7`

## CORE-021 — Residual CJK + Technical Token Filter

- Thêm precision gate cuối trước JSON export.
- Loại path, filename, Java descriptor, resource identifier, snake_case, camelCase, code/debug token và font-map data.
- Giữ các nhãn CJK ngắn thật sự hiển thị trong game.
- Residual CJK scan chạy độc lập để phát hiện chữ Trung còn sót; chuỗi binary chưa chắc an toàn chỉ đưa vào Diagnostics, không tự đưa vào JSON dịch.
- Thêm backend post-build residual Chinese audit.

SHA-256 package: `b5c88e04fddf05edb28e2571b4962bc791b10faac8252849c5fdd3faab85e4a2`

## CORE-020 — Font Loader + CJK Complete Scan

- Sửa game proprietary font `char.txt + 13.FON`: khi `char.txt` tăng kích thước, tự patch hard-coded `SIPUSH 3978` trong font loader sang byte-length mới.
- Nếu không tìm thấy loader hợp lệ, dừng build để tránh xuất JAR có glyph nhưng runtime không nạp được.
- CJK Complete Scan giữ lại CJK patch-safe bị heuristic cũ loại nhầm.

SHA-256 package: `67823905b25ff120ce148afb5c1fb96e33f62713905190b04f7f6ee1d6952d59`

## CORE-019 — Unified Translation + Font Build

- Sửa regression CORE-018: font build không còn bắt đầu từ JAR Trung Quốc gốc.
- Pipeline đúng: JarBuilder áp bản dịch → font builder tích hợp glyph → RegressionValidator kiểm tra JAR cuối.

SHA-256 package: `cdade4e8f63da4f520b3ce253042e92dea61e922a0b4b51dc1d571fe205e6b0a`

## CORE-018 — Vietnamese Bitmap Font Builder

- Phát hiện `char.txt`, `13.FON`, `ascii.FON`.
- Xác nhận layout Unicode 12×12, 24 bytes/glyph.
- Phân tích glyph Việt thiếu theo bản dịch hiện tại.
- Rasterize TTF/OTF cục bộ vào đúng bitmap format của game.

SHA-256 package: `5313ffaf5fc2a2ee7d07ac5630e27a9e90b23ed025ace0ac03c1b34128913d87`

## CORE-017 — Startup Activation Deep Trace

- Tối ưu class dependency graph từ cách dò gần O(N²) sang single-pass + shared BFS.
- Lấy startup path từ nested dependency report.
- Deep Trace chỉ chạy on-demand trong Diagnostics.

SHA-256 package: `7f57d0f903a7a5eac6db14d2d7996b83dbb936d5577c333d66c5d40f81ba7a93`

## CORE-016 — Open JAR Freeze Hotfix

- Legacy Activation/WMA không còn tự scan khi mở JAR.
- Không wrap `scan_complete`, không tự tạo worker mới từ module này.

SHA-256 package: `1f2c9a4c0bab16e7ccae82fba554ffea6efd5c1dadc06c395501ad70ecd310ee`

## CORE-015 — Activation Classification Fix

- Không còn kết luận `no_wma/low` nếu activation vẫn nằm trên startup path.
- Thêm `startup_activation_non_wma / HIGH`.

SHA-256 package: `efc74a5be4afbf9a9fe536f5ec56b137d187968cb8cc6e69b5c84d8a6f2de356`

## CORE-014 — Scan Freeze Performance Fix

- Bỏ WMA/SMS rescan đồng bộ sau language scan.
- Tái sử dụng report đã có, cache theo path + size + mtime.

SHA-256 package: `81f665cd856f6084cc6990a4ec2fa6242629743f668762a8f2ab6b091a789a2c`

## CORE-013 — WMA/SMS Compatibility Assistant

- Static compatibility assistant cho WMA/SMS và legacy activation.
- Chỉ báo cáo/diagnose; không gửi SMS thật, không giả activation/payment success.

SHA-256 package: `0c9a07640e8be2c9427eb428adba941fa64bca81c1358902515b791df1ebf857`

## UI-012 — Diagnostics Dashboard 2×2

- Bỏ tab UI cũ; hiển thị Overview, Runtime Log, Compare, Bundle trong dashboard 2×2 có scroll.
- Giữ API compatibility `_diagnostics_show_tab()`.

SHA-256 package: `161d674857406995a1e07ba791ddd5a6fc5a00c4a21aca86001a043e63d8a70d`

## CORE-010 — Path Import Fix

- Sửa NameError do CORE-009 thiếu `pathlib.Path`.
- Giữ bộ lọc từ đơn an toàn.

SHA-256 package: `6a56ae95d19d0ebb24043ebb8ba74eaa2d0c1f33895ef72bac8e579e7708fb75`

## CORE-008 — Auto Restart After Patch

- Sau Apply Update Patch thành công, app tự relaunch bằng `QProcess.startDetached` rồi mới đóng instance cũ.
- Nếu relaunch lỗi, giữ app hiện tại chạy.

SHA-256 package: `680950f15d7a834d83fa703aa581f3517e113b9202bef750abf040c460465837`

## CORE-007 — JAR Open Hotfix

- File dialog JAR chỉ nhận `.jar`.
- Tách hoàn toàn workflow `.jar` khỏi Update Patch `.zip`.
- Lỗi container ZIP được diễn giải thành lỗi JAR hợp lệ/hỏng.

SHA-256 package: `43ff78c046bdafbee0ee53e62c9d532a7ea7f5dcb4b5f4bbbbbe0895bc59f6a9`

## UI-001 → UI-006

Chuỗi UI nền tảng hiện hành: layout 20/50/30, icon/file categories, grouped workflow ribbon, hotfix TypeError và compact vector header. Các patch này được giữ trong stable archive theo đúng thứ tự cài.

## Superseded / không cài trong current chain

### CORE-009

- Được giữ để đối chiếu lịch sử.
- Không cài; đã được thay thế bởi CORE-010 vì CORE-009 có lỗi runtime thiếu `Path`.

### UI-011

- Được giữ để rollback/lịch sử.
- Không cài; UI-012 đã supersede.
- Bootstrap đi kèm UI-011 dựa trên baseline cũ và có nguy cơ làm mất hook mới.

## Stable archive bundle

`JVT_PATCH_STABLE_ARCHIVE_20260913.zip`

- SHA-256: `ea6b26a768fbc2c1febd4b4b7ec63a33b45534d61b454007ef381bb723753c17`
- 21 patch stable.
- 2 patch archived/superseded.
- Có README, CHANGELOG và patch-index nội bộ.
