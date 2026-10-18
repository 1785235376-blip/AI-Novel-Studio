# Media display editor — 2026-10-18

## Implemented scope

The original Studio Graph client now exposes an optional, display-only canvas client. It uses the original captured transport and owner decoder, not new credentials, a model endpoint or another workflow engine. Embedded older Graph clients may omit the extension.

The existing `useStudioGraphEditor` mounts the media view panel under the same workspace, with its dirty and uncertain-save state folded into original Graph navigation/discard and sibling edit locks. The panel supports reading saved views, importing existing image/video/audio metadata references, explicit create/save/reopen, title and numerical position/viewport/zoom edits, reference removal and ID filtering. It does not load media payloads. Original Asset preview/download ownership is unchanged.

The display definition retains up to 1000 cards; rendering culls off-screen cards and caps overlapping DOM cards at 128, with an explicit omission notice. This is bounded DOM work, not measured browser FPS. Geometry reuses the existing Graph coordinate conversion/clamps.

Strict client decoding checks ownership, IDs, scope, exact schema, positions, duplicates, bounded lists, SHA256 format, card/reference-state consistency, false execution/binary-verification declarations, saved version progression and matching submitted definitions. Unavailable bindings remain masked and cannot be sent back as an editable binding. Explicit card removal is available. List responses contain only summary metadata.

A write exception or an authority transition before its response leaves an uncertain state; there is no automatic retry. The user must read saved versions and explicitly consent before replacing a draft. Captured save callbacks are retired across draft/authority ABA/unmount. No claim is made that an unacknowledged request failed on the server.

## Evidence and limits

- Client/geometry/component checks: first full pass 22; final client/geometry/component checks including overlap/late-response: 24 passed in `media-canvas-final-bounds`.
- Original Graph workspace regression, reviewed Director handoff, storyboard authority, and dirty-owner integration: 12 passed. The dedicated dirty-owner test isolates the controller; the existing workspace/Director regression retains original implementations.
- TypeScript and production Vite build passed. The existing token guard covers shared UI primitives; the new CSS additionally uses existing token names and fixed domain card geometry, with no raw colors.
- An initial new component test incorrectly assumed selection survived explicit server adoption. It failed; the test now reselects the rendered card and uses reference-state-shaped fixtures. Product behavior was not weakened. Raw failure retained.
- Actual backend File/PostgreSQL API persistence was verified in the preceding API slice. Frontend tests use deterministic transport/component fixtures; this is not a live browser-to-PostgreSQL end-to-end claim.
- Bundled Playwright Chromium launch was attempted through the original isolation runner and failed because its executable is absent. No new download, security-policy change, screenshot baseline update or browser-performance claim.
- Build reports retain existing large-chunk warnings.

## Still open

Image/video/audio content thumbnails, pointer dragging/panning, minimap, nested reusable media groups/subgraphs, richer source refresh/recovery, production browser geometry/FPS and full-product acceptance remain open. Current title and coordinate controls are the first persisted display workflow, not the finished professional infinite canvas. Prompt adoption's production gate and original graph execution limits remain unchanged.

Source: `frontend/src/creative/MediaCanvasViewPanel.tsx`, `studioCanvasViewClient.ts`, `mediaCanvasGeometry.ts`; raw evidence under `docs/delivery/v2-development/media-canvas-*` and `canvas-view-client.*`.
