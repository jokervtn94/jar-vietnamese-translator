# Patch Changelog

Cập nhật catalog: **2026-09-21**

## Stable validation policy

Mỗi patch stable phải qua tối thiểu: ZIP/CRC, parse `manifest.json`, SHA-256 payload, compile syntax với Python payload và test chuyên biệt nếu patch có parser/build logic. Runtime test thực tế vẫn được ghi riêng; package validation không được mô tả thành runtime validation nếu chưa chạy trên Windows/KEmulator.

## Current recommended head

`UI-051-recovery-confirmation-gate`

Chuỗi phát triển sau CORE-026:

`CORE-027 → CORE-028 → UI-029 → UI-030 → UI-031 → UI-032 → UI-033 → UI-034 → UI-035 → UI-036 → UI-037 → UI-038 → CORE-039 → CORE-040 → UI-041 → UI-042 → UI-043 → UI-044 → UI-045A → UI-046 → UI-046R → UI-047 → UI-048 → UI-049 → UI-050 → UI-051`

Lưu ý: `UI-046-virtual-translation-table` đã được đánh dấu **archived** vì trải nghiệm runtime thực tế rất kém (load lâu, click/double-click lag). `UI-046R` là rollback bắt buộc cho máy đã cài UI-046. Từ UI-047 trở đi hướng tối ưu quay lại QTableWidget.

## CORE-027 — Scene JSON Export Fix

- Sửa export JSON để các chuỗi `scene-script:*` được đưa vào file dịch đầy đủ.
- Giữ cấu trúc immutable và metadata cần thiết cho import/build.

SHA-256 package: `5619ee1a6f22c1c8255fc35faea4affa84f0a4375e7ff0091e4368b702aed817`

## CORE-028 — Fast JSON Import

- Cache scan index và source JAR hash.
- Giảm validation lặp lại, tối ưu import file lớn.

SHA-256 package: `99e9ed23c4db003c0181f6ef2764719d536d2ca7ee9983ddf4418acb5be0f8b2`

## UI-029 → UI-034 — JSON Import / Statusbar / Modern UI Recovery

- UI-029: thêm progress monitor cho JSON import.
- UI-030/UI-031/UI-032: sửa statusbar layout/rebuild/startup.
- UI-033: chuyển import sang cooperative processing nhưng có regression stale bootstrap.
- UI-034: khôi phục đầy đủ modern UI hook chain và giữ responsive JSON import.

Package hashes được ghi trong `POST_CORE026_PATCHES.json`.

## UI-035 → UI-038 — Branding + Recovery Performance

- UI-035/UI-036: logo/ICO và PySide6 branding hotfix.
- UI-037: recovery restore optimizer.
- UI-038: lazy recovery restore, model authoritative, không rewrite toàn bảng ngay lập tức.

## CORE-039 — Binary Whitespace Preservation

- Không còn `.strip()` làm mất tab/space có ý nghĩa trong binary framed strings.

SHA-256 package: `080e17fc1b8e6d7f3ba84e2cda350e4362126f6cc15e1dee39dd197678a57a69`

## CORE-040 — Binary Frame Overlap Fix

- Sửa false-positive overlap giữa u8-length và u16be-length binary candidates.
- Ngăn patch translation ghi đè structural bytes trong `property.bin`.
- Đây là fix đã cô lập bằng diagnostic JAR G/H và xác nhận game chạy bình thường.

SHA-256 package: `8ea0ae02c057154bfc4b2e2bd85ba218685eafb854a2c896e5aab11dc48eb5ea`

## UI-041 → UI-045A — Large JSON Performance

- UI-041: merge translation vào authoritative model một lần; bỏ repaint toàn bộ 2.159 dòng trong import.
- UI-042: Light Monokai JSON progress.
- UI-043: compact + accurate progress, ring và linear bar dùng cùng progress source.
- UI-044: Build JAR progress đồng bộ phong cách JSON progress.
- UI-045A: zero-scroll hydration, loại bỏ 24ms scroll timer.

## UI-046 — Virtual Translation Table [ARCHIVED]

- Thử nghiệm `QTableView + QAbstractTableModel`.
- Runtime thực tế: load lâu, double-click xử lý chậm và lag.
- Không dùng tiếp hướng này nếu chưa rewrite sạch toàn bộ dependency UI.

SHA-256 package: `1c68e97589ed5b6aa44f2ff45cd2981f57b34cdda7b503ddefccca33d7529f40`

## UI-046R — Rollback Virtual Table

- Khôi phục QTableWidget và zero-scroll path.
- Thêm selection/editor callback coalescing.

SHA-256 package: `c577acbf127f4c9eedd6d190072546cd2fe61ca0b859d2325fe08ecc8ec7f697`

## UI-047 — QTableWidget Fast Path

- Build table một lần cho mỗi ScanResult.
- Search/status/source filter dùng hide/unhide thay vì rebuild toàn bộ rows.
- Search debounce 140ms.
- Không gắn xử lý vào scroll.

SHA-256 package: `2868322b853a406c00db6204d864b72319f9d0f04d720225cd335036e5702d93`

## UI-048 — Full Sync During Import/Recovery

- Chuyển toàn bộ UI synchronization vào progress phase.
- Không còn click/scroll hydration sau khi progress kết thúc.

SHA-256 package: `c6099324bb604e90b8e2f84cd2deef03fe0d4b2b9706d7964685e30f2a2cff33`

## UI-049 — Fine Grained Sync Batch

- Giảm sync batch từ 96 xuống 20 dòng/lần cho Import và Recovery.
- Progress cập nhật sát số dòng thực tế hơn và Qt event loop được yield thường xuyên hơn.

SHA-256 package: `7daa13e1ece931e518ac9f4a8dd5c3e7f6c8bd15e0b4de7dfbf57f70ae427c66`

## UI-050 — Recovery Progress Match JSON

- Recovery progress được dựng lại theo đúng Light Monokai/compact JSON progress.
- Có ring progress, linear progress, elapsed/ETA, task table 3 cột và log.

SHA-256 package: `fcf75d1af0adbd1c5f79dc33442bb5c8e5857d4503125559d909dec5cc64bfa4`

## UI-051 — Recovery Confirmation Gate

**Validation:** static/package PASS · user-confirmed Windows runtime PASS · stable baseline.

- Sửa lỗi progress Recovery xuất hiện và timer chạy trước khi người dùng xác nhận.
- Luồng đúng: verify snapshot → hỏi Yes/No → nếu Yes mới tạo progress dialog, bắt đầu timer, restore model và sync UI.
- Nếu No: không mở Recovery progress, không mutate project.

SHA-256 package: `015a2814d90308510c1fe394a16cf8719b4e11baaab1241095d73d1a83f60696`

Runtime acceptance checklist: `updates/patches/logs/UI-051-recovery-confirmation-gate.md`

## Historical stable chain through CORE-026

`UI-001 → UI-002 → UI-003 → UI-004 → UI-005 → UI-006 → CORE-007 → CORE-008 → CORE-010 → UI-012 → CORE-013 → CORE-014 → CORE-015 → CORE-016 → CORE-017 → CORE-018 → CORE-019 → CORE-020 → CORE-021 → CORE-022 → UI-023 → UI-024 → UI-025 → CORE-026`

Historical archive bundle: `JVT_PATCH_STABLE_ARCHIVE_20260913_R4.zip`

- SHA-256: `409c4a15d949ffcde1d3ab6aaf1b03289555ca9d635c608d1a89e6436a903c2b`
- 24 patch stable through CORE-026.
- 2 patch archived/superseded (`CORE-009`, `UI-011`).

## Binary package publication note

The connected GitHub contents interface can create/update UTF-8 repository files but does not upload arbitrary binary ZIP payloads. Therefore exact binary package filenames, SHA-256 values, dependency/status metadata and changelog are committed here; a ZIP must not be claimed as present in GitHub unless the repository listing verifies the binary file itself.
