# Director source-change impact preview — 2026-10-16

Baseline: `6ed69e1f6a5bcda902f47d113c3f7c198ae96a18`. The containing commit identifies this local slice. Scope: bounded P1 / CONSOLE-02/05 / U06; broader coordination remains PARTIAL.

## Actual gap and original-owner decision

The mounted console already warned about an outdated selected director pin, and the handoff already created/reopened original-owner storyboard drafts. Neither showed saved content differences or connected-node impact. `CreativeService.history` already authorized every returned current/historical snapshot, but did not return canonical per-snapshot digest receipts. Saved planning nodes are protected; there is no existing rebind action to reuse. No rebind was introduced.

Added `snapshot_digests` to the existing history projection, after all unchanged `assert_current` checks. Each receipt hashes that exact historical item with original `document_digest`, excluding recursive history. No stored document, route, authorization rule or canonical digest definition changed. Existing consumers retain `items`; the additive frontend receipt field is optional for compatibility.

## Mounted user flow

1. In the original graph workspace, select a `director_plan`, open the optional console, and explicitly choose **读取／刷新导演来源影响**.
2. Original export/history/list reads establish current version/digest and, when available, the exact pinned historical content. Exactly one total receipt and one valid item per requested version are required; conflicting duplicates, absent receipts, malformed/null rows or unavailable history produce clearly labelled metadata-only comparison. Invalid current export or denied/network reads clear the preview and show an error.
3. Read before/after title, scene and director-note fields plus other saved authored sections. Scene/note identity is preserved, ordering changes are explicit. At most 40 changed fields and 2000 characters per side render; truncation is labelled. Plain React text escapes markup. This is a deterministic field comparison, not semantic/model analysis.
4. Inspect the selected node ID and structural downstream node IDs/types/exact planning pins in the loaded graph. Disabled nodes remain visible. Structural connections are labelled potential impact, not proven derivation or execution.
5. Inspect current readable related storyboard references. The original owner deliberately excludes stale-source, archived or unavailable records and rejects their exports. That restriction is retained and explained: zero returned rows does not mean zero impact. This slice does not claim a complete project/global lineage inventory.
6. Refresh explicitly after external changes. Graph/selection/source/client lifetime changes discard previews and late A→B→A reads. A successful local source save remounts its preview. Preview does not touch unsaved text, clear UNKNOWN, update a graph pin, adopt a proposal, overwrite a storyboard or dispatch a model/task. Existing graph Save/reopen remains unchanged. Guidance uses the existing explicit creation of a new node/graph for new source versions.

## Verification

Final unchanged-source commands, UTC times, exit codes and SHA256 receipts are retained in the adjacent JSON. All selected checks exited 0:

- 274 targeted mocked UI/geometry tests: source content and digest comparison, malformed/conflicting history, unavailable/denied reads, escaped/truncated text, late client/pin/node/graph/active lifetime changes, dirty/CAS draft preservation and existing graph/handoff/authoring regressions. Mounted original workspace test authors/saves a Director, pins/saves a graph, reopens it and reads impact with the exact selected node identity; no model/run/write is issued by preview.
- Four nonsecurity File checks: original derive/reopen/edit; exact historical digests after source edit with stale storyboard exclusion/export denial and unchanged original reference; two-service CAS preservation; process restart read. Thirty PUBLIC profile contracts.
- `tsc -b`, Vite production build, test discovery, design-token guard, scoped no-raw-color check, `git diff --check` and PUBLIC source closure (487 files).
- Review identified duplicate-receipt ambiguity and malformed-history render risk before finalization. Strict read projection validation and 11 additional malformed/lifetime/text cases address these findings. Earlier successful receipts remain historical; final receipts alone establish the final unchanged source.

No browser/visual/native IME/assistive-technology/performance acceptance, PostgreSQL/P0/security lifecycle, Windows/GPU/provider/user-machine, hosted CI or full RC was attempted. Canonical image-workspace reference and DS-v1.0 were inspected; shared primitives/shell/tokens were not modified. Vite's existing large-chunk warning and Starlette test-client deprecation remain warnings, not acceptance claims.

## Preserved boundaries and next work

P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No second store, new execution node, model request, permission expansion, budget change, paid action, push or hosted CI. Cost remains unknown. This is an inspection slice; exact cross-module proposal/approval/task-result coordination, stale-reference recovery by an authorized owner, complete impact inventory and final browser/model acceptance remain open. Independent parent review precedes the next tracked feature slice.
