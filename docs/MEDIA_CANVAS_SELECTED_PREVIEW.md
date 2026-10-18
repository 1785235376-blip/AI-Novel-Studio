# Selected media preview through the original Asset owner

2026-10-18. An explicit selected-card action now opens the original AssetInspector after checking the exact asset id, version, kind, SHA256, non-deleted state, bounded size and media type. The loader performs original metadata read → original download → actual byte SHA256 → fresh metadata read. Every awaited step checks the current selection/owner. There is no bulk preloading, new binary repository or provider invocation.

Only supported raster images (PNG/JPEG/WebP/GIF), MP4/WebM and listed common audio types are admitted. SVG/HTML and unrecognized MIME types are not previewed here. A single original asset must be at most 32 MiB; blob size and media type must match the metadata. If WebCrypto is unavailable, verification stops. This cap is a UI preview budget, not a change to the original Asset storage/import limits.

AssetInspector's existing Blob URL creation/revocation and image/video/audio elements are reused. Its download callback rechecks original metadata and current owner before returning the already verified blob. Selection, owner or disabled transitions remove the visible preview and suppress late results. A failed or stale read does not automatically rebind the saved card to newer media.

Evidence:
- Actual byte digest/metadata-order tests, prior AssetInspector tests and display-panel regression: 20 passed.
- Additional selected-preview lifecycle plus byte-loader checks: 17 passed; media-canvas-preview-lifetime receipt.
- TypeScript and production build passed; original shared UI token guard passed.
- Test byte fixtures validate integrity and admission, not image/video decoding or perceptual quality. Lifecycle tests isolate AssetInspector rendering; its existing tests remain unchanged.

No browser end-to-end playback or visual acceptance is claimed. The current canvas has selected, explicit preview, not automatically loaded in-card thumbnails. Full responsive UI, browser FPS, reusable groups/subgraphs and whole-product acceptance remain open.
