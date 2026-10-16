# Explicit graph-owned view preferences — 2026-10-16

Baseline `fd9bfabe5d6b2b9a053b2b30adbc7e0474a5d5e7`; containing local commit identifies delivery. P1 canvas remains PARTIAL.

## Original owner and bounded scope

The existing `GraphPresentation` owner already persists annotation/groups alongside camera/node positions. This increment adds optional `presentation.view`, containing exactly four required values: boolean `show_grid`, boolean `snap`, integer `grid_step` in the existing 8/16/24/32 options, and boolean `show_minimap`. Backend and frontend reject missing/unknown fields, nulls, coerced booleans/strings and out-of-range/nonfinite steps; existing Unicode annotation/group bounds remain intact. Schemas 1–5 share the original optional presentation contract. Absent preferences and absent presentation remain omitted, preserving legacy canonical definition digests. Execution projection/digest, DAG nodes/edges, budgets, source references, authorization and dispatch are unchanged.

There is no new store, localStorage path or automatic save. Grid/snap/MiniMap controls remain temporary until the explicit “将视图偏好写入图草稿” action records one original history change. The user then saves through the existing graph Save/CAS contract. “移除已存视图偏好” removes only this field, preserving comments/groups and removing the presentation container only when empty. Undo/redo, conflict/UNKNOWN lock, checked-server adoption and reopen remain original-owner behavior. Toggling or persisting preferences does not move nodes, alter the viewport or execute anything. Collapse remains session-only; no group-ID persistence or cleanup complexity was added.

Temporary preferences derive synchronously from the exact active owner and original loaded-record identity plus current draft preference values. Graph selection, same-graph reload/adoption and undo/redo restore the appropriate stored values/defaults without dirtying a graph. Ordinary draft edits retain temporary preferences. Read-only users can inspect temporary display settings but cannot write/remove preferences; busy/UNKNOWN states prevent draft writes. Retained write handlers check current definition/owner/source and editability.

## Verification and honest limits

- 210 selected mocked UI, transport and geometry tests PASS: temporary toggles are clean; explicit one-step history; save/reopen/removal; same-mounted reload; graph owner changes; readonly/busy; legacy defaults; strict transport; existing geometry and production editor regression; 409/UNKNOWN/500 draft retention and explicit checked adoption.
- 81 Python checks PASS: 50 pure presentation contracts including all five schemas, one nonsecurity File original-owner persistence/reopen/CAS/removal integration, and 30 PUBLIC contracts. Execution digests and original definition restoration verified.
- TypeScript, Vite build, discovery, original token guard, scoped raw-color guard, diff check and 487-file PUBLIC source closure PASS. Existing Vite large-chunk warning remains. Canonical IMAGE reference inspected; shared Button/toolbars reused, no CSS/token/protected shell changes.
- Initial File invocation lacked the required owned `--basetemp` and correctly failed the fixture guard (80 passed, one setup error). Corrected invocation uses the owned `.runtime` profile. Failed and superseded receipts retained, not relabeled. Final receipts bind unchanged source hashes. See [evidence](canvas-view-preferences-20261016.json).

Browser/visual/native input/IME/assistive technology/performance, PostgreSQL/P0/security, Windows/GPU/provider/user-computer/full RC NOT_RUN. Mocked UI and separate File integration are not browser-to-backend acceptance. No browser fallback, saved environment, paid provider or hosted CI. P0 BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No push because CI cost remains unknown.

Independent read-only review found no remaining blocker: 185 overlapping UI/transport and 51 schema/nonsecurity File checks passed. These overlap delivery totals and are not added to them. Reviewer made no tracked edits. Parent review remains required before the next feature slice. Nested/collapsed persistence, durable unsaved recovery, browser acceptance and broader frozen canvas/director goals remain open.
