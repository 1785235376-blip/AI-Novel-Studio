# Read-only Creative scene and shot navigation

Source inspection found that the original scene and shot selection buttons were inside the disabled authoring fieldset. A read-only viewer could see the document but could not use those native controls to switch the selected scene/shot.

The existing CreativeCanvas now places local scene and shot navigators outside the authoring fieldset. They use the original selection callbacks only; authoring, save, reorder, derive and other mutating controls remain under their existing edit permissions. Busy operations still disable navigation. Shot selection also selects its existing scene, matching the original card behavior.

Each navigator provides bounded local text search over the already-visible original draft. Matching does not change data, order or selection; a nonmatching current scene/shot remains displayed below. Document replacement invalidates old callbacks and query text. Busy changes and unmount invalidate retained callbacks. No request, model, source refresh, new permission or persistence owner is introduced.

## Evidence

- creative-scene-navigation-ui-r1: 9 tests, TypeScript and production build PASS (initial scene path).
- creative-scene-shot-navigation-ui-r1: 11 tests, TypeScript and production build PASS (scene and shot paths).
- creative-scene-shot-navigation-ui-r2: 12 tests, TypeScript and production build PASS, adding query lifetime coverage. Six new checks plus six unchanged original CreativeProductionCanvas and DirectorNoteActions checks. Existing large-chunk warning remains.

DOM checks confirm navigation is outside the disabled editing fieldset while authoring fields remain disabled. Other checks cover local content filtering, no automatic selection or mutation, exact shot/scene selection, stale callbacks and replaced-document query clearing. This is not a browser/visual/accessibility audit or a new Graph execution capability; full product acceptance remains separate.
