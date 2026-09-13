# UI-025 — Transparent Label Backgrounds

Patch ID: `UI-025-transparent-label-backgrounds`

Package: `JVT_PATCH_UI_025_TRANSPARENT_LABEL_BACKGROUNDS.zip`

SHA-256: `d621d37039238402cc697c1333d90549b42ecc8c16704f911e12e7d0962ade9f`

Requires: `UI-024-remove-redundant-edit-button`

## Vấn đề

Theme hiện dùng rule tổng quát `QMainWindow, QWidget { background-color: #F5F7FA; ... }`. Trong Qt Style Sheets, `QLabel` là một `QWidget`, vì vậy nhiều label bên trong panel/card trắng nhận nền `#F5F7FA` thay vì bề mặt của parent. Kết quả là xuất hiện các khung chữ nhật quanh label có màu lệch với background của app/panel.

## Thay đổi

- Đặt background mặc định của `QLabel` thành `transparent`.
- Áp dụng rõ ràng cho label nằm trong `Panel`, `InnerCard`, `AppBar`, `HeaderFrame`, `InspectorBody` và `QStatusBar`.
- Không thay đổi màu chữ, font, padding hoặc layout.
- Không thay đổi background chủ đích của các badge/brand có selector cụ thể như `QLabel#AppMark`, `QLabel#StepBadgeActive`, `QLabel#StepBadge`.

## Kết quả mong đợi

Label thông thường hòa vào đúng background của parent card/panel và không còn các mảng nền sáng/tối lệch màu. Các badge có màu nền riêng vẫn giữ nguyên.

## Validation

- ZIP/container CRC: PASS
- manifest.json: PASS
- payload SHA-256: PASS
- QSS contract: PASS
- AppMark/StepBadge selectors preserved: PASS

Runtime Windows visual verification vẫn cần được xác nhận sau khi cài patch.