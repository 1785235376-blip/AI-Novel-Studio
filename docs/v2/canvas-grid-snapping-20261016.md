# World grid and group snapping — 2026-10-16

Baseline: `65b607de422eecfc2e5121c3145ff28885c9d048`. The containing Git commit identifies delivery. Local only; no push or hosted CI (cost unknown).

## Audited owner boundary

GraphCanvas already had a fixed screen-space decorative grid and transient MiniMap visibility. Graph definition/CAS already owns node positions and viewport; StudioPreferencesInput owns only intents/preset/custom_intent. No canvas grid/snap preference exists there. This slice adds no backend, schema, localStorage or second authoritative store. Grid visibility, snapping and step are explicitly **session-only view settings**, reset on owner change/unmount. Saved snapped positions reopen via the original Graph owner; settings are not persisted. Existing unsaved/conflict/UNKNOWN recovery contracts remain unchanged.

## Bounded behavior

- Reuses the existing token-colored grid CSS, shared Buttons and navigator select. World-origin dots follow camera pan/zoom (CSS radial dots are centered within each tile, so the background offset subtracts half a tile).
- Independent visible grid and opt-in drag snap controls; supported grid steps 8/16/24/32 world units. Toggling never moves existing nodes or writes history. Disable snapping for existing free placement.
- Pointer drag snaps the grabbed node's origin, applying one translation to the entire selection. Off-grid relative offsets are preserved. At ±100000 coordinate boundaries, preserving the group's offsets and bounds takes precedence over grid alignment; the UI states this.
- Snap mode/step is captured at gesture start. Existing cancellation, source/owner replacement and readonly/busy fences still apply. Snap no-ops do not publish an undo record; completed movement publishes exactly one original history record.
- Keyboard nudges intentionally retain the established 8 / Shift 32 **screen-pixel** contract, independent of snap. New view controls isolate keys; composing/229 keyboard events are ignored by canvas shortcuts. Native IME is not claimed tested.
- Existing MiniMap/culling/alignment, graph pins, content, viewport and typed edges remain unchanged by snapping. No node/edge/execution budget increase, execution call or model dispatch.

## Verification actually run

Exact commands, timestamps, exit codes and receipt/log hashes: [machine-readable evidence](canvas-grid-snapping-20261016.json).

- Selected nine mock UI/geometry suites: **203 passed**, 0 skipped. Includes zoom 0.35/1/2.5, grabbed anchor differing from selection order, finite/bounded group motion, invalid inputs, cancellation, free placement, no-op history, key isolation, IME event guard, transient reset and original workspace undo/save/reopen while preserving dirty text. Existing layout, culling, MiniMap, Director and PUBLIC placeholder coverage retained.
- Original nonsecurity File presentation-position/camera reopen/CAS test: **1 passed**. PUBLIC package contracts: **30 passed**. No PG/security tests.
- `tsc -b`, Vite build, test discovery (discovery only), existing token guard, changed-file raw-color/token scope check, `git diff --check`: exit 0. Existing large-chunk warning remains.
- PUBLIC source closure: **487 files**, exit 0. This is not Windows/Docker/installer execution acceptance.
- Initial two-suite focused run also passed (65 tests); receipt retained locally. Final receipts bind unchanged source hashes.

## Limits and handoff

Browser runtime remains previously BLOCKED; screenshots, physical input/IME/screen-reader and real render performance are NOT_RUN. No browser workaround, user computer, paid provider, real GPU, Windows or full RC. P0 lifecycle work remains BLOCKED and excluded; R3-GATE HOLD and production Prompt Adoption disabled.

Grid settings persistence, grouping/collapse/annotations, full LOD, durable unsaved recovery and wider canvas acceptance remain PARTIAL/open. Next bounded candidate after independent review is grouping/collapse presentation through a supported original owner, after auditing the schema; do not invent a parallel store or loosen execution constraints.
