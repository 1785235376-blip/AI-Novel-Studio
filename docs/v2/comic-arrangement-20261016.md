# B06 manual comic / Webtoon arrangement

Baseline: `570bbf7e3e422b4e30296ba92ac729b2604f759e`. The containing local commit identifies delivery. B06 remains **PARTIAL**.

## Audit and exact gap

The existing `ComicLayoutsPanel` and `ComicLayoutsService` already own editable page/panel/bubble geometry, approved original asset selection, exact asset version/hash/metadata snapshots, source validation, versioned saves/history/restore, raster preflight, digest-bound human approval and PNG ZIP export. `comicLayoutsClient` already wires those operations. No missing export engine or asset-binding backend was invented. The other Storyboard owner's absent unsaved image reference field remains a separate blocked handoff.

The existing preset resets the layout from source shots and discards authored panel content. Numeric geometry fields are usable but require manually recalculating each panel and every absolute-position bubble. The new bounded action fills this actual manual-edit gap without replacing the preset or owner.

## Implemented flow

1. Open or create a comic layout in the mounted original workbench. Edit dimensions or reading order using its existing fields.
2. Explicitly preview vertical arrangement: existing reading order, page-safe left edge, 16 px gaps, unchanged panel dimensions. The preview lists exact old/new coordinates and identifies itself as geometry, not raster artwork.
3. Reject noninteger/invalid dimensions, page pixel budget, duplicate panel IDs, non-contiguous order, bubbles outside their original 8 px inset, or a stack that cannot fit the current safe page. No automatic page enlargement, text shrinkage, cropping, deletion or order renumbering.
4. Explicitly apply once to the original local document. Bubble coordinates translate by the same delta as their panels. Shot IDs, panel IDs/order, exact image version pins, appearance references, briefs, character references, fit modes, text bytes/font sizes and dimensions remain unchanged. Array order is retained. One original history entry supports undo/redo; there is no autosave.
5. Save through the original CAS owner, which captures and revalidates approved sources and exact digests. Run original raster preflight, inspect all segments, explicitly approve the current digest, then download with existing export. Arrangement application clears prior raster preview/review consent like any other original edit.

Cancel, edit/undo, record/source change, refresh, active request and client replacement discard arrangement preview. A synchronous generation ticket rejects retained apply handlers after cancellation, edit or repeated application. No new request is made by preview/apply. The existing owner still determines permissions, freshness, UNKNOWN/mutation behavior, text metrics, overlaps, segment cuts, pixel and export availability.

## Verification

Exact command/exit/source/log hashes are indexed in `comic-arrangement-20261016.json`.

- 37 selected mock UI/pure checks: geometry/content preservation, Unicode text retention, bounds/order/malformed numeric rejection, exact safe boundary, no-op, preview/apply/undo/redo/original PUT, cancel/edit/refresh/client reset, retained-handler rejection across record/source/owner ABA and pending/409/UNKNOWN failures, and existing raster/export workflow. Independent review requested malformed structure/global bubble-ID checks and explicit unsupported RTL labeling; both are included.
- Four nonsecurity File cases, including new manual two-panel move → original save/reopen → exact raster preflight/approval/export digest → historical restore; existing byte-exact segment export, review revocation/history and appearance-reference source preservation.
- 30 PUBLIC tests, forced TypeScript/Vite, test discovery, design token guard, scoped color check, diff check and 487-file PUBLIC source closure. Intermediate receipts are retained; final indexed checks use unchanged sources.

## Limits and next work

Browser/native input/visual quality/HTTP integration, Windows/GPU/provider/real model artwork, professional print and full RC **NOT_RUN**. Geometry preview does not prove text fit or artwork quality; original saved raster preflight remains mandatory. Arbitrary font/script support, 2D freeform drag editing, durable unsaved recovery and broader comic UNKNOWN/history UX remain separate open work. No backend/schema/security/authority/lifecycle/model/provider/export-engine change. No additional costs, user-computer use, push, hosted CI, merge, release or tag.

P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled. DeliveryCenter entitlement producer remains BLOCKED. All prior receipts and environment/denial/cost boundaries remain in force. Parent independent review before further tracked feature work.
