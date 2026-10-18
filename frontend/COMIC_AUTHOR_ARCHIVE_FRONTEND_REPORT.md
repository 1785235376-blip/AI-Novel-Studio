# Native Comic author archive frontend

## Scope

Added private editable author ZIP controls beneath the existing Comic collection owner. The native owner selects the restored book and first page; edits and saves use the existing Comic page editor and optimistic version API. Public reading export controls are unchanged.

Export is explicit preview → hidden author content acknowledgement → bounded download with exact export digest and SHA-256 validation. Import is bounded local file read/hash → server read-only inspection → explicit new-draft acknowledgement → restore. Unsupported dependencies are rejected by the native server; this surface does not flatten or silently drop content.

Recovery persists only a bounded inspection digest/request key/status map. No archive bytes, author text, session token or source title is persisted. Restore requires Web Locks, holds an archive lock plus shared metadata-map lock through the request, rereads identity under lock, and verifies durable storage readback before dispatch. Unknown outcomes retain the same key across close/reopen, file reselect and explicit inspect/retry. Server completed-attempt discovery supports recovery after local identity loss and at receipt capacity. A new independent import is explicit and disabled while the previous outcome is unknown. No automatic retry is performed.

## Verification

- 212 tests passed across author controls/client, existing collection tree, CBZ/PDF, EPUB and JPEG/WebP publication suites.
- Final author-specific suite after concurrency review: 17 tests (13 mounted React native-owner tests and 4 lock-admission contract tests).
- Mounted tests cover inspection without creation, restore selection, editing/saving hidden text and image briefs through the native API, reopen recovery using exact request key, completed receipt recovery at capacity, explicit export and content hash rejection, oversized-file early rejection, scope retirement, unavailable Web Locks, quota/readback failures, unknown-result new-copy blocking, and a stale explicit-new intent queued behind another tab's lost acknowledgement. The latter verifies lock-time comparison against the expected prior completed key, no extra dispatch, and preservation of the other tab's pending identity. A changed completed predecessor is also rejected. Delayed restore and validated download responses after client retirement neither select old book/page nor save stale export.
- TypeScript `tsc --noEmit`: passed after materializing existing contracts in the sparse checkout.
- UI token guard: PASS (52 files).
- `git diff --check`: passed.

Tests use real React components and native HTTP client routing with synthetic mocked HTTP responses; they are not a browser or live-backend roundtrip acceptance claim. Web Locks tests model lock serialization; no real multi-tab browser acceptance was run.

Browser visual regression and geometry screenshots: NOT_RUN under the task's no-browser/no-service restrictions. The implementation adds no CSS, colors, layout tokens, shell changes or system-level components.

## Files

- src/experimental/ComicAuthorArchivePanel.tsx
- src/experimental/comicAuthorArchiveClient.ts
- src/experimental/ComicCollectionTree.tsx
- src/experimental/ComicAuthorArchivePanel.test.tsx
- src/experimental/comicAuthorArchiveClient.test.ts
