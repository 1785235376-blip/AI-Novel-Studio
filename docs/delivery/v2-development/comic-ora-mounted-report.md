# Original Comic ORA mounted workflow

Baseline: `7a9e7457d360d2c3f2379b0767a94def458f408d`.
Backend commit: `78585dbffff448d1e3d0bb1d3791c8706d04df9c`.
Frontend commits: `c212e401f25349aea421cde55cb849d252c656a2` and guard fix `b9b0493ad8ceb4369eec665dc0164915f36f50f2`.
Worktree: isolated `studio-comic-ora-mounted`, branch `work/mount-comic-ora`.

## Delivered

- Original Comic route composition after IndependentWorkspaceService; no Director/Host changes.
- Read-only bounded thumbnail preview; explicit exact-SHA/request-key preparation, at-most-eight-step stage/resume, exact manifest, receipt-bound private candidate PNG, explicit reviewed-license/raster-loss approval, and existing independent-page CAS attachment.
- All uploads authenticate and capture existing project incarnation before streaming. A bytearray bounds actual streamed bytes before parsing/base64 decoding; raw archive cap is 16 MiB. No synchronous lease spans asynchronous receive. Mutations retain the original authority lease through original-owner commits, with reauthorization and incarnation checks before/after processing.
- Actor/scope/incarnation receipt recovery list and status. No upload cache, alternate owner, workflow store, legacy candidate image bypass, or automatic replay. Thumbnail resize work is charged to the existing parser budget.
- Original Comic editor includes transient-file ORA panel, explicit recovery/reselection, actual candidate pixel-load gates, license/loss acknowledgment, and explicit attachment. Attachment remains DRAFT; normal page save/preflight/approval/export remain separate.
- Native RASTER union, preserved pins through reconciliation and native copy, unique IDs, visibility/opacity/order/bounded offsets, immutable dimensions, and independent-only restriction. Native dialogue remains canonical. UI labels distinguish controls from saved server-rendered pixels.

## Verification

Backend owned File run: **108 passed, 57 PostgreSQL deselected**. Command:

```sh
python scripts/run_v2_checks.py comic-ora-api-file -- python -m pytest tests/test_comic_ora_api.py tests/test_comic_ora_mounted_authority.py tests/test_comic_ora_import.py tests/test_comic_ora_staging.py tests/test_comic_ora_review_attach.py -m 'not postgres_backend_only' -q --basetemp .runtime/pytest-comic-api
```

Python used the existing recovered environment at the primary checkout, without installing dependencies. File evidence: `comic-ora-api-file.json` and `.log` beside this report.

Tests include genuine production `/api` and `/api/v1` composition and original trusted-session/role/scope authorization; direct multi-chunk ASGI reads with absent/false Content-Length, authority/incarnation drift and no lease over await; private foreign receipt/PNG denial; real owner retirement and same-ID recreation; explicit lost-ack recovery and CAS; exact archive/manifest checks; thumbnail bounds and charged work.

Frontend final: **140 tests passed across 13 files**:

```sh
node_modules/.bin/vitest run src/experimental/ComicOraImportPanel.test.tsx src/experimental/comicOraClient.test.ts src/experimental/ComicLayoutsPanel*.test.tsx src/experimental/comicLayers.test.ts src/experimental/comicRasterLayers.test.ts src/experimental/ComicCollectionTree.test.tsx src/experimental/ComicReadingOrder.additive.test.tsx tests/uiContracts.test.ts src/creative/IndependentStudioWorkspace.comic.test.tsx
node_modules/.bin/tsc --noEmit
node ../scripts/check_ui_design_tokens.mjs
```

TypeScript exited 0. UI token guard passed 52 checks. Existing node_modules were reused by untracked symlink. New tests cover failed candidate image reads, immutable partial-review license recovery, exact-file reselection, stale owner/onLoad and late unmount fences, explicit idempotent prepare retry, double-click review, dirty/unsaved/wrong-dimension targets, native structural edits/copy and raster pin preservation. Actual mounted workspace tests protect selected files and unsaved license text through close/cancel/page-save; standalone dirty RASTER pages protect New/Open/Source/restore/refresh without requiring book membership. Receipt/file replacement requires explicit reset. ORA bytes remain mounted through catalog reload; mandatory authorization/context retirement is unchanged.

## Remaining acceptance and boundaries

- Parent-coordinated genuine PostgreSQL verification: **57 passed, 58 deselected**; all fourteen before/after table hashes equal, including authorization tables, and the owned PostgreSQL process stopped. Parent receipts: `ora-mounted-integration-postgres.json`, `.log`, `ora-mounted-integration-cleanup.json` and `ora-mounted-integration-postgres-runtime.json`. Parent File API/authority run: **26 passed**.
- Browser geometry/visual and external ORA application acceptance: **NOT_RUN**. Known browser EPERM was not retried. No compatibility claim for untested third-party applications.
- No model/provider execution, paid APIs, dependency installation, service startup, remote push, release, merge, reset, force push, or primary-worktree source edits.

## PostgreSQL fixture cleanup

The production authority fixture uses generated workspace, project, two users, membership, role and permission rows. Its teardown removes only that exact workspace's role/permission/audit rows; exact workspace/user membership pairs; exact workspace/project storyline and branch rows; and exact project/workspace link. It restores only its disposable novel's workspace foreign key to the preexisting default workspace before deleting its generated workspace and two users. The enclosing original mounted fixture then deletes its disposable novel/content/scope state. Sessions are process-local. The parent compares full before/after table snapshots independently.
