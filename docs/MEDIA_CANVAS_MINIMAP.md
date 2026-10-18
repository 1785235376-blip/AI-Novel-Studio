# Media canvas minimap — 2026-10-18

The display viewport now includes a 200×120 bitmap overview of all saved/local card positions and the current camera. Drawing all at most 1000 bounded locations uses one canvas DOM node, not a second 1000-card DOM tree. Original full world bounds include the camera. Clicking maps the point back into the original clamped viewport; Enter/Space centers the whole overview. Save remains explicit.

Owner/source/disabled transitions retire captured navigation callbacks. An active pointer gesture prevents minimap navigation. Colors are read from existing design-system tokens. The main viewport still renders at most 128 intersecting cards.

Tests use a canvas drawing spy for call counts and coordinate mapping, not actual raster output. Adjacent interaction tests deliberately provide a null canvas context because jsdom has no canvas engine; they test owner and gesture behavior only. The initial run's jsdom missing-context warnings are retained. Final targeted checks: 25 passed; TypeScript and production build passed, recorded in media-canvas-minimap-final.

Browser image correctness, responsive geometry and FPS remain unverified because the bundled browser is unavailable. No screenshot baseline is approved here. This closes the first functional minimap implementation, not the professional canvas's remaining media thumbnails, grouping, subgraphs or full acceptance.
