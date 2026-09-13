# CORE-026 — Scene Script Language Coverage

Patch ID: `CORE-026-scene-script-language-coverage`

Package: `JVT_PATCH_CORE_026_SCENE_SCRIPT_LANGUAGE_COVERAGE.zip`

SHA-256: `055759d04691a678a3040f48b17fb3ec6a332c7d9484473686fabd923259fecb`

## Mục tiêu

Bổ sung coverage cho game J2ME lưu hội thoại trong resource hỗn hợp binary/text `scene/*.sce`, tránh bỏ sót text thật nhưng vẫn không đưa technical token vào JSON dịch.

## Phát hiện từ game kiểm thử thực tế

Game kiểm thử: `仙侣情缘之麒麟劫320x240.jar`.

Kết quả audit trước CORE-026 cho thấy JSON hiện tại chỉ có 615 item nhưng JAR còn 119 file `scene/*.sce` chứa số lượng lớn text hiển thị thực tế như hội thoại, nhiệm vụ, thông báo, lựa chọn, lời dẫn và tên NPC.

## Nâng cấp scanner

Thêm `SceneScriptAnalyzer` để parse theo command thay vì raw carving:

- `say`, kể cả các biến thể `xsay`, `nsay`, `csay`, `Rsay`, `Ksay`, `Isay`, `9say`
- `info`
- `choose`
- `black`
- `amission`
- `poem`
- `text`
- `fight`
- `csprite`
- tên NPC nhúng trong cấu trúc `[u8 byte length][UTF-8][NUL]`

Scanner chỉ lấy operand người chơi nhìn thấy; không export opcode, event ID, tọa độ, sprite ID, animation token và các tham số kỹ thuật khác.

`fight` được tách theo `@`/`&` và `choose` được tách theo `|` để các delimiter script không nằm trong text dịch.

## Build support

Thêm transactional scene build staging:

1. Xác minh byte gốc đúng tại offset đã scan.
2. Patch từ offset cao xuống thấp để hỗ trợ chuỗi Việt dài/ngắn khác nhau.
3. Với NPC name dạng `u8-length + UTF-8 + NUL`, cập nhật lại length byte.
4. Cấm translation chứa delimiter nguy hiểm `;`, NUL, CR/LF; với `fight` cấm `@`/`&`; với `choose` cấm `|`.
5. Giữ nguyên số lượng `;` của scene script.
6. Stage JAR được CRC-verify trước khi chạy canonical `JarBuilder`.
7. Sau build cuối, mọi translation scene đều được xác minh lại bằng UTF-8 bytes; nếu có lỗi, output JAR bị xóa.

## Validation thực tế

Trên `仙侣情缘之麒麟劫320x240.jar`:

- `scene/*.sce`: **119 file**
- safe player-facing scene strings: **1946**
- residual CJK scene segments chưa được parser bao phủ: **0**
- Python syntax: **PASS**
- patch smoke với hội thoại `scene/2.sce`: **PASS**
- command delimiter count sau patch: **PASS**

## Dependency

- `CORE-021-residual-cjk-and-technical-token-filter`
- stable UI chain through `UI-025-transparent-label-backgrounds`

## Ghi chú

`0 unmatched CJK scene segments` chỉ chứng minh coverage cho các file `.sce` của game kiểm thử này. Các resource type khác vẫn tiếp tục được kiểm chứng bằng binary/class/text/residual scan hiện hành; không coi đây là tuyên bố mọi JAR đều có coverage 100%.