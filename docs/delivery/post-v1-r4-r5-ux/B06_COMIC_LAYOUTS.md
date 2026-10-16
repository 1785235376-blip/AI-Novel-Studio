# B06: reviewed comic / Webtoon layout copies

## Scope and reuse

Status: IMPLEMENTED / INTEGRATED / CONTRACT_VERIFIED for the bounded deterministic
subset below. File-backed real raster rendering is REAL_RUNTIME_VERIFIED. The
real PostgreSQL cases and hosted browser journey are authored; execution evidence
must come from the exact published commit's hosted checks. Local Chromium was
already blocked by EPERM and was not retried. No real image model was invoked;
artistic quality and USER_ACCEPTED remain NOT_RUN.

- Entry: existing ExperimentalWorkbench → 漫画与 Webtoon. No shell, global design,
  asset store, screenplay/character IDs or execution system was replaced.
- Source authority: DirectorService screenplay/chapter/privacy evidence, original
  AssetLibraryService bytes and versions, A09 lineage, original character IDs.
- Flag: `comic_layouts_v2`, requiring explicit `asset_lineage_v2` and
  `ai_director_v2`. Default-OFF, wildcard refusal and V1 override are server-side.
- Renderer: lazy optional `comic` extra, Pillow 12.3.0 and fonttools 4.59.1. Official
  release verified at https://pypi.org/project/pillow/12.3.0/; isolated installed
  Pillow was 12.3.0. Import/startup while OFF does not require these libraries.
- Geometry reuses the original RefNode coordinate contract. The existing
  ImageInfiniteCanvas assumes fixed-size thumbnail nodes and cannot represent
  variable-size page panels/bubbles. This consumer therefore uses numeric manual
  geometry controls and exact server raster previews, without modifying that
  canvas or adding a second persistent canvas/asset owner.

## Supported closed loop

1. Select an existing screenplay's current shots. Page (800×1120) and vertical
   Webtoon (800×2400) presets produce draft panels. Presets initially include at
   most four/six shots, visibly labeled; remaining shots can be added manually.
2. Review original user-uploaded image pixels and explicitly approve their exact
   asset version when necessary. The action updates the original library's
   approval metadata, with original branch/current actor permissions. Generated,
   provider/model/feature/provenance-bearing or derived assets cannot use this
   shortcut and must follow their original review process.
3. Edit panel position/size, source shot/scene, linked character IDs, numbered
   order, contain/center-cover crop, page safe area, bubble/narration position,
   speaker, plain text and font size. Supported spatial reading order is top to
   bottom, and left to right for equal y coordinates. Local undo/redo is bounded.
4. Save a versioned DRAFT. All writes reset approval. Saved-version restore
   creates a new DRAFT and rechecks its original source and asset evidence.
5. Explicit preflight reports missing approved images, incorrect order, panel or
   bubble overlap, safe-area overflow, missing/unverified font, missing glyphs,
   real measured text overflow, resampling bounds, center crop, segment-cut
   bubbles, and small text at 320 px. No placeholder art is substituted.
6. The sole renderer composes actual approved asset pixels and measured text.
   Preview offers 320/360/768/800 px display widths with horizontal scrolling
   when the selected viewport exceeds available workspace width. Every preview
   segment must display successfully before review is enabled.
7. Review the exact digest-bound version and all warnings. Explicit approval
   changes only this isolated layout record. Export requires the same current
   approval and outputs deterministic stored ZIP entries: real PNG segments,
   `manifest.json` with geometry/checksums, and applicable complete `OFL.txt`.
   The PNG bytes are exactly those returned by the preview endpoints.
8. Existing source/asset/character/privacy changes invalidate old content and
   approval; stale projections hide layout/dialogue/asset references. Late
   frontend responses cannot revive output after an edit or scope switch.

All outputs start as drafts. A layout approval does not approve a model proposal,
write manuscript/Canon, create an asset, promote a media result, publish, or send
anything to an external service. A file already downloaded cannot be remotely
revoked; subsequent previews/downloads are fenced again.

## Font and deterministic output

Only Noto Sans SC is currently supported. Font size is editable; arbitrary font
upload, font fallback, rich text, SVG, HTML, scripts, animation, rotated/skewed
panels, custom speech-tail geometry and user-selected fonts are unsupported.

The renderer reuses `pdf_export._font_candidates` and existing build pins:

- Pinned upstream variable Noto Sans SC font from `prepare_pdf_font.py`:
  `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`.
- Fixed weight-400 regular build already pinned by the Windows packaging script:
  `eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461`.
- Complete OFL license:
  `1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9`.

Both regular-only packaged installations and prepared variable-font directories
are supported. The neighboring OFL file must match. Glyph coverage and measured
line bounds are checked; bounded CJK punctuation rules avoid dangling closing
marks at line starts and opening marks at line ends. A real PNG was visually
inspected locally for Chinese glyph readability and its synthetic-art label. Missing fonts/glyphs block text output instead of
claiming success with tofu. No font binary is embedded in the PNG/ZIP. Technical
pin/license checks do not independently establish the user's artwork rights.
Pillow/FreeType/JPEG/WebP versions participate in the review fingerprint.

## Boundaries and safety

24 panels, 80 bubbles, 10,000 total text characters, 1,000 per bubble, 16 million
page pixels, 20 million decoded/resampled image pixels, 64 MiB source/output
budgets and 100 historical revisions. PNG/JPEG/WebP single-frame images only;
bytes are decoded and EXIF orientation normalized, with metadata discarded.
Extremely distorted cover-resizes are blocked before large allocation.

Only integer page-pixel geometry and plain rasterized text are supported. Preview
and export share one `compose` implementation, including wrapping, font weight,
panel borders, bubble bounds and segmentation. Fixed-size segment boundaries can
cut a bubble; this is an explicit warning requiring review, not silently hidden.

All `/comic-layouts` routes reauthorize before returning results. Private success,
authorization failures, source/version errors and input errors use no-store and
nosniff. B06 additionally bounds validation errors in its own private response wrapper.
The separate shared HTTP compatibility fix preserves declared exception headers;
this consumer does not modify shared middleware.
File and PG persistence use the existing scope-atomic ExperimentalStore; no
migration or startup conversion is needed.

## Verification

- `tests/test_r5_comic_layouts.py`: deterministic real pixels/PNG parser checks,
  byte-identical preview/export, CJK glyph pixels and full OFL, bounds, revisions,
  crop acknowledgement, stale source/privacy/characters/assets, actor/branch,
  original image approval, malformed input and revocation fences.
- `tests/test_r5_comic_mounted.py`: actual app composition under `/api` and
  `/api/v1`, original library, trusted sessions/membership/roles, no-store success
  and errors, OFF/V1/dependency fences, mid-render flag/session revocation, and
  stale confidential dialogue suppression. No stub authorization.
- Local isolated File run: 38 passed, 38 PostgreSQL cases deselected. Real PG tests
  require `TEST_POSTGRES_DATABASE_URL`; no fake PG fallback or local PG pass.
- `ComicLayoutsPanel.test.tsx`: 8 React tests cover read-only mount, manual
  geometry, local undo/redo, explicit image review, failed preflight, exact review
  digest/version, displayed-pixel gate, approved-only download, duplicate clicks,
  409 draft retention, scope replacement and stale asynchronous responses.
- TypeScript and UI design-token checks passed. Existing AppShell is unchanged.
- `r4-comic-layouts.spec.ts`: authored real React/File API hosted journey covering
  original image approval, missing-image blocker, CJK bubble/undo, exact archive
  versus preview bytes, explicit layout review, overflow rejection and desktop
  geometry/screenshots at 1366×768, 1440×900 and 1920×1080. NOT_RUN locally.
- Fixture `r5-comic-SYNTHETIC-TEST-ASSET.png` contains a visible test label and
  synthetic line drawing. It is test data, never final artwork.

Local commands (isolated harness, prepared font external to the repository):

```sh
R2_TEST_FONT_FILE=<prepared regular font> ../r2-run.sh python -m pytest -q \
  tests/test_r5_comic_layouts.py tests/test_r5_comic_mounted.py \
  -m 'not postgres_backend_only'
pnpm --dir frontend exec vitest run src/experimental/ComicLayoutsPanel.test.tsx
pnpm --dir frontend exec tsc -b
node scripts/check_ui_design_tokens.mjs
```

Hosted browser startup needs the existing prepared font passed through the normal
runtime configuration `AI_NOVEL_STUDIO_PDF_FONT`. Tests do not cause runtime
installation or use paid models, real credentials or original manuscripts.
