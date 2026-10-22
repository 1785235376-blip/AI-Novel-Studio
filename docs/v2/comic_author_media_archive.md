# Comic author media archive (PAGE + PNG)

Contract `comic-author-media-page/1`. This is an editable private author interchange, not a reading copy. It carries independent PAGE structure plus PNG panel assets. It reuses the original Comic page/book owner and Asset owner; no second asset library. Asset and Comic commits are separate (not cross-owner atomic).

## Limits
- max archive 48,000,000 bytes; max 10 pages; max 32 assets; max 8,000,000 bytes per PNG; max 32,000,000 total PNG bytes; max 20,000,000 pixels per image; JSON 180,000 per page and 1,800,000 total JSON.
- only `INDEPENDENT` `PAGE`; panel `asset_id`/`expected_asset_version` allowed only together. RASTER layer items are explicitly unsupported and rejected. No WEBTOON, screenplay, character, shot or appearance dependency.

## Archive
ZIP_STORED only: `manifest.json`, `pages/NNN.json`, `assets/NNN.png`; no directories, traversal, duplicate names, symlinks, extra fields/comments, compression or oversized inflate. Each entry has byte length and SHA-256; PNG is decoded/verified and dimensions bounded. Pages are portable: panel/bubble IDs are positional aliases, asset IDs are `asset_NNN` aliases and expected version is normalized to 1; no source IDs, approvals, actors, histories or project IDs.

## Import
Explicit `inspect` returns `archive_sha256`, `inspection_digest`, counts, `restore_status=READY_FOR_EXPLICIT_IMPORT_AS_UNREVIEWED_DRAFT`, `asset_approvals_copied=false`. Explicit restore with acknowledge creates new project assets under deterministic idempotency keys in the original asset owner, then one original Comic raw transaction creates new DRAFT pages and book and a durable receipt. New assets have no approval; pages have `status=DRAFT`, `approval=None`, `_author_media_import=true`, and no copied approval/Canon. Retry after partial asset staging reuses idempotent assets; no page/book/receipt is returned before the Comic transaction commits. Existing imported pages remain editable through the original service (unapproved assets are accepted only for this server-marked imported page).

## API
Routes under `/novels/{nid}/experimental/comic-layouts`:
- `POST /books/{rid}/author-media-archive-preview`
- `POST /books/{rid}/export-author-media-archive`
- `POST /author-media-archive/inspect`
- `POST /author-media-archive/restore`

The shared router mount is supplied separately (`integration/comic_author_media_archive_entry.patch`) and is not committed here. All route responses use `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`; errors are bounded and never return partial rows.

## Shared minimal dependency
`app/experimental/comic_layouts.py` gains a server-only `_author_media_import` row flag and an `allow_unapproved_assets` path. This is required so newly imported unapproved assets can be reopened/edited without copying approval. It is applied only when that flag exists or when a save of such an imported page is requested; normal pages/asset approval behavior is unchanged. Old assetless archive remains compatible and untouched.
