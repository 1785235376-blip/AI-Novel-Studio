# Optional Studio Tutor floating presentation

The existing LocalTutorDialog now has an explicit floating presentation for its Ask view, plus collapse/expand and return-to-dialog controls. It remains the same session, preview, consent, request, cancellation and revocation owner. Switching layout does not discover/connect a peer, share content, grant permissions or execute a model. The existing default-off, lazy entry stays unchanged; no Tutor popup is forced at Studio startup.

The floating layer is nonmodal and does not intercept background pointer events or trap external Tab/Escape. Its close/cancel/status footer remains visible when collapsed. Settings and diagnostics return to the original modal presentation. Unknown revocation/sharing state immediately restores the visible modal and expands the body; a closed/collapsed panel is never represented as proof that sharing stopped. Original disconnect acknowledgement handling is unchanged.

Placement uses CSS-pixel rectangles only: the current/last focused editable area, selection geometry, a visible editor fallback, other modal rectangles and the visual viewport. A bounded six-position solver minimizes overlap, clamps to the viewport and prefers a stable position when scores tie. Resize, scroll, selection/focus and ResizeObserver events schedule measurements; no text/value is captured or transmitted by positioning. When space cannot avoid overlap, the UI explicitly recommends collapse or return to dialog. There is no TTS, Live2D, avatar download, OS window or background screen observer.

## Evidence

- tutor-floating-ui-r1: FAIL, 77 passed / 1 unchanged original test failed. Inserting the layout toggle before the close button altered the original modal Shift-Tab cycle. The production header was reordered to preserve the original first close control; the original test was not changed. Failed receipt retained.
- tutor-floating-ui-r2: 79 tests PASS (7 new geometry/presentation/unknown-revocation checks plus 72 unchanged integration/lazy-entry/scope-review checks), TypeScript PASS and production Vite build PASS. Existing large-chunk advisory remains.

The new checks cover nonmodal keyboard behavior, collapse without extra requests, explicit settings modality, current-input geometry, exact no-additional-sharing behavior, original close handling, viewport clamping, stable placement and visible UNKNOWN revocation. Geometry tests use synthetic DOM rectangles; they are not actual browser screenshots or native-window observations.

## Remaining boundaries

This is an in-Studio floating web panel, not a detached OS window, complete dockable Tutor Slot, real QingJian desktop connection, Windows Named Pipe/dual-product acceptance or multi-monitor/high-DPI validation. Actual browser/visual/accessibility and target-device testing remain pending. TUTOR-03 remains partial at the full product scope. Placement is best-effort for measured active areas, not a guarantee that no text/canvas element can ever be covered.
