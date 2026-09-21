# UI-051 — Recovery Confirmation Gate

Date: 2026-09-21

## Scope

Patch ID: `UI-051-recovery-confirmation-gate`

Package: `JVT_PATCH_UI_051_RECOVERY_CONFIRMATION_GATE.zip`

SHA-256: `015a2814d90308510c1fe394a16cf8719b4e11baaab1241095d73d1a83f60696`

Requires: `UI-050-recovery-progress-match-json`

## Intended runtime contract

Recovery flow must be:

`detect snapshot -> validate -> Yes/No -> [Yes only] create Recovery Progress -> start timer -> restore model -> full UI sync -> 100%`

Before the user presses **Yes**:

- Recovery Progress dialog must not exist.
- Recovery progress timer must not start.
- `project.translations` must not be mutated.
- Translation table sync must not start.

If the user presses **No**:

- no Recovery Progress dialog;
- no restore;
- no table sync.

If the user presses **Yes**:

- Recovery Progress is created only after confirmation;
- timer starts from that point;
- recovery uses QTableWidget;
- full table sync uses 20 rows per batch;
- 100% is emitted only after full table sync is complete;
- click/scroll must not trigger hydration.

## Validation state

- Package/static validation: PASS.
- User-confirmed Windows runtime: PENDING.
- Runtime PASS must not be claimed until the user tests the actual installed patch and confirms the contract above.

## Non-regression constraints

- Do not return to UI-046 QTableView/QAbstractTableModel.
- Do not re-enable scroll hydration or click hydration.
- Do not reintroduce a 24 ms scroll timer.
- Keep CORE-039 exact binary whitespace preservation.
- Keep CORE-040 canonical u8-vs-false-u16 overlap protection.
