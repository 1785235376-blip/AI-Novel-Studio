# Media canvas pointer and keyboard interactions

2026-10-18. Adds pointer dragging of cards, blank-space panning, anchor-preserving Ctrl-wheel zoom, and keyboard card/viewport movement to the persisted display editor. Original Graph world/screen transforms and clamps are reused. Pointer movement remains a local preview; only an explicit valid pointer completion changes the parent draft, and the existing Save is still required. No graph runs, media fetches or backend mutations occur during gestures.

Source/owner/disabled transitions retire the gesture, including authority ABA. Escape, pointer cancellation, lost capture and unmount cancel without committing. Ctrl-wheel uses a non-passive listener only within the viewport; ordinary scrolling is not consumed. Arrow keys move by 16 world units for cards or screen units for viewport, Shift by 64. The viewport and card buttons are keyboard-focusable. The existing 128-card visible DOM bound remains.

Targeted checks: 22 passed across pointer interactions, original display editor, geometry and dirty-owner wiring; TypeScript and production Vite build passed. No new browser screenshots or FPS acceptance: the preceding browser launch remains blocked by absent bundled Chromium. Component pointer tests use a deterministic PointerEvent shim, not a physical pointing device. Existing large-bundle warnings retained.

Evidence: `docs/delivery/v2-development/media-canvas-gestures.json` and `.log`. This supersedes only the pointer-drag/pan gap in MEDIA_CANVAS_DISPLAY_EDITOR.md. Thumbnails, minimap, groups and reusable subgraphs remain pending.
