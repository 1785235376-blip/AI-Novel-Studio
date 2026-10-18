# Comic geometry and selective Director camera authoring

Product checkpoint: 2bbecf3e20ba277a6342d5ae279ea7ae878059fd. These are bounded manual authoring improvements; full V2 and intelligent Director acceptance remain open.

## Comic schematic geometry

The existing Image Comic editor now includes a selectable schematic for panel and bubble rectangles, pointer move/resize and keyboard 1 px nudging (Shift: 10 px). One pointer gesture commits one original undoable edit. Panel moves translate their bubbles; resizing retains child margins. Page safe-area bounds and the original uniform 8 px bubble inset are enforced. Invalid numeric drafts remain unchanged for correction with the existing numeric fields.

The surface uses matching percentage geometry and an outline to avoid border-box scale drift. Pointer cancel, stale revision, retired owner and disabled states discard projection. Text, image/source bindings, layer metadata and unselected fields are preserved. The original editor still owns undo, explicit save/reopen and authoritative preview. The schematic does not render image pixels, fonts, layer effects or live production output; overlap and text overflow still require original preflight.

Review caught and corrected two concrete issues: bubble clamping initially allowed edges contrary to original 8 px inset, and bordered measurement differed from inner geometry. Invalid page-dimension/safe-area no-op coverage was added. Independent final focused review: 21 tests passed. Mounted save/reopen fixtures are synthetic endpoint contracts, not actual browser acceptance.

## Director selective camera reuse

The existing Director scene-note editor now offers an explicit source note, same-scene target notes and selected camera fields: shot size, camera angle, camera motion, lens and composition. A before/after preview precedes author-confirmed application. Empty values are disclosed as clearing the selected field. IDs, duration, performance, story/source metadata and all unselected fields remain untouched.

Preview captures exact draft/scene/version/authority and selection revisions; changed or ABA state retires it. Apply is one-shot. Undo requires the exact resulting draft and is retired by intervening edits, save/busy/version changes, or authority loss rather than clobbering other work. The original explicit Save remains the persistence owner. No model dispatch, approval or new workflow engine is introduced.

Review caught a clean-baseline edge: applying camera values can return to the already-saved content, making dirty=false without a Save. Undo now remains available for that exact result. Independent corrected review: 39 tests passed, including 22 camera-reuse cases.

## Integrated verification

- Root combined frontend: 213 tests in 20 suites passed, followed by full TypeScript build, Vite production build and token guard. All 3178 source paths match; source was stable during the run.
- Geometry worker: 110 targeted regressions plus types/token passed. Camera worker: 103 targeted regressions and token passed. These overlap the root combined suite; do not add the counts.
- The earlier standalone camera exit137 is superseded by the successful serialized combined build, with its raw failed receipt retained. Existing production chunk-size warnings remain; this is not large-scene performance acceptance.

Both feature slices are frontend-only. All 1,527 non-frontend hashes from the preceding final PG receipt match exactly; backend/tests/scripts/packaging/catalog have no Git delta from dedff1c2. The preceding PUBLIC receipt differs only in its earlier original collection test teardown, with application/package bytes identical. Those bounded PG and public-wheel results are reused rather than rerun. The new combined frontend build is separately verified.

A standalone camera typecheck was killed with exit 137 before Vite ran; cause is unverified and that receipt remains an unfinished build. Sparse-checkout missing-contract diagnostics and their corrected checks are retained. Root integration serializes production validation. No actual browser, Windows, model quality, external editor or whole-product acceptance is claimed.

## Archive and remaining work

Previous source 26354565 is verified in public archive fc629c8e3296e6c8652af12d6d4d5c33066ff007, parent 5776531b: 14 artifacts / 5,565,571 bytes. These prerequisite-bound bundles do not advance main/PR source heads or create a release.

Broader Comic geometry/typography/layer painting/generation, real browser interaction and complete original/differentiated V2 scope remain incomplete. Manual camera-field reuse does not complete model-led Director analysis or graph-wide proposal execution.
