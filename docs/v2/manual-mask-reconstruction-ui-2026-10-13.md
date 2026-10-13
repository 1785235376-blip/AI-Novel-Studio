# Manual binary mask authoring: reconstructed frontend slice

Base: `4534bed9129bcf2a549b44a91f062c79a77e173b`.

## Implemented scope

The original independent IMAGE workspace offers an explicit editor for the selected original Asset. Loading verifies current source metadata, original-byte SHA-256, bounded PNG structure, browser decode dimensions, and a second metadata read. Supported sources are noninterlaced 8-bit gray/RGB/gray-alpha/RGBA PNGs, 64–1024 pixels per dimension in multiples of eight, at most 8 MiB and 1024 chunks. Only IHDR, contiguous IDAT and IEND are supported; ordinary PNGs with color profiles, textual metadata, orientation or animation chunks are deliberately unavailable. There is no silent conversion or resizing.

Pixels remain ephemeral MSB-first one-bit rows: white KEEP, black REMOVE. The existing canvas supports bounded hard-edge painting/erase, exact rectangular edits, keyboard cursor/paint/undo, pointer-cancel rollback, and up to 16 packed undo states (2 MiB at maximum dimensions). Canvas RGBA is only a display layer. The server encodes the saved grayscale PNG.

Saving is a separate consented action through the original Studio Asset owner. The client binds the exact source/version/digest, dimensions, bitplane digest/counts, returned PNG Asset digest/version and current MANUAL_EDIT parent proof. It neither uploads via the generic import flow nor creates a task or invokes a provider. CPU cutout is absent from this baseline and is **not connected by this slice**.

The original shell operation semaphore and dirty-navigation confirmation remain authoritative. Pixel edits invalidate consent synchronously. Project/actor/full-scope/Host changes, including same-turn ABA and same-token Host epoch rebinding, abort reads/writes and clear private pixels/URLs. Source selection has its own epoch. Saving an uncertain response permits only an explicit same-key, same-payload retry while the source remains current. Source drift disables retry; the UI offers a read of the original Asset list and does not claim that nothing was saved. Discarding an uncertain draft cannot generate another key in that editor lifetime.

## Verification

- **225 tests passed** in the 11-file focused union below: 156 additive tests, 60 unchanged original owner/client tests, and 9 unchanged geometry unit tests. This is not a full frontend or full legacy test claim.
- UI design-token guard: **PASS**, 52 files.
- Helper/canvas isolated TypeScript: **PASS**. Full frontend no-emit TypeScript remains **BLOCKED by 21 baseline diagnostics** in five pre-existing timeline/media files, owned by a separate baseline repair. Missing sparse-checkout fixtures/contracts were restored from the baseline before this final check; those checkout omissions are not product defects.
- Browser/visual/native-image decode/assistive-technology acceptance: **NOT_RUN**. Canvas and image-decode unit tests use explicit stubs. Geometry unit tests are not browser geometry acceptance.
- No backend, frozen test assertion, dependency, catalog, global matrix or remote repository changes are part of this frontend slice.

Reproduce the focused union from `frontend/`:

```sh
./node_modules/.bin/vitest run \
  src/creative/studioBinaryMask.test.ts \
  src/creative/StudioBinaryMaskCanvas.test.tsx \
  src/creative/studioManualMaskContract.test.ts \
  src/creative/StudioManualMaskAuthoring.test.tsx \
  src/creative/IndependentStudioManualMask.test.tsx \
  src/creative/IndependentStudioWorkspace.test.tsx \
  src/creative/IndependentStudioReadFences.test.tsx \
  src/creative/IndependentStudioRelationships.test.tsx \
  src/creative/IndependentStudioSequentialImport.test.tsx \
  src/creative/studioClient.test.ts \
  src/creative/graphCanvasGeometry.test.ts
./node_modules/.bin/tsc --noEmit --incremental false
node ../scripts/check_ui_design_tokens.mjs
```

Backend/native/mounted integration and any later baseline type repair need their own evidence on the combined commit. Historical receipts from the missing earlier implementation are not reused as proof of this reconstruction.
