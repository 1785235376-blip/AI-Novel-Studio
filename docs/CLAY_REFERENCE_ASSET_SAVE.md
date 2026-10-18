# Reviewed static GLB clay reference: original Asset save

This backend slice adds POST `/api/projects/{nid}/studio/assets/{aid}/model-reference/clay-save` under the original `domain.write` authority. It does not add a model, scheduler, render engine, or workflow owner.

The caller must provide the exact source version and SHA-256, current camera, reviewed PNG SHA-256, explicit `confirm_reference: true`, and a stable idempotency key. The server re-renders the existing bounded 256 x 192 CPU diagnostic, checks the reviewed bytes, and publishes through the original Asset Library. The first metadata commit contains the source-pinned MANUAL_EDIT lineage and private current-incarnation origin. Public output omits private identity. Author license annotations do not refresh the immutable source pin.

The output is a diagnostic image, not a material/lighting render. Existing project quota, disk admission, feature gates, scope locks and Asset metadata/binary persistence remain authoritative. A failed metadata write before commit leaves no unindexed image; an acknowledgement failure after commit reopens the original asset on the same key. Concurrent same-key operations converge. A retired or changed source, malformed prior receipt, or lost authority cannot silently create another image.

## Evidence, 2026-10-18

- `clay-reference-asset-file-r1`: FAIL, 42 failed / 6 passed. Actual free disk space was 46 MiB, below the unchanged original 64 MiB reserve. This also blocked unchanged manual-mask tests. The failed receipt/log are retained.
- Completed owned test fixtures were recoverably compressed, with every archived member hash/size or symlink target compared against the originals before removing only expanded duplicates. Free space recovered to 79 MiB. No storage threshold, test expectation, or admission guard was weakened.
- `clay-reference-asset-file-r2`: 48 passed, including the unchanged original manual-mask owner tests.
- `clay-reference-asset-boundary-file-r1`: 16 passed, adding pre/post metadata-commit errors, concurrent replay, changed/deleted/recreated source, damaged receipts, and original quota/admission rejection. Actual persisted metadata and binary counts are asserted.
- `clay-reference-asset-pg-r1`: the same 16 cases passed with real PostgreSQL 17.11 project owners and the original filesystem Asset owner. Reused owned database `v2_director_pending_green_20261018`, OID 31303; no fresh-database claim. Server stopped normally.

## Reviewed-preview UI followthrough

The existing static-scene clay preview now offers an explicit confirmation checkbox and save action only with original workspace write authority. Preview alone still creates no asset. Source, camera, scope and permission changes retire the reviewed preview. The client verifies the actual PNG before sending only the source pin, camera, reviewed hash, confirmation and stable caller key. It then checks the returned original image Asset, provenance parent and exact receipt contract; provider/model claims, wrong projects and inconsistent replay flags fail closed.

The original workspace mutation semaphore owns the write. Within the mounted workspace, an unknown outcome retains the same request key and blocks a different clay-save identity until the original is resolved. A visible warning instructs the user to inspect the existing library before reloading; request continuity across a full page reload is not claimed. The saved image joins the existing Asset list and storage invalidation, without automatic generation or workflow adoption.

- `clay-reference-save-wire-r1`: one original File save generated the committed synthetic client fixture; no provider or live user data.
- `clay-reference-save-ui-r1`: 14 UI/client tests and TypeScript PASS, including unchanged depth/clay export tests.
- `clay-reference-save-integration-build-r1`: 37 unchanged preview/workspace/identity/sequential-import tests, TypeScript and production Vite build PASS. Existing large-chunk warning remains. Build output is separate from previous build artifacts.

## Remaining boundaries

No product-browser acceptance, real model/GPU run, full-suite acceptance, cross-module Storyboard/Image/Video adoption, or V2 release readiness is claimed. This is a source-pinned diagnostic image save, not a finished 3D render pipeline.

Fixture generation followthrough `clay-reference-save-wire-r2` passed after explicitly limiting that generator test to the File fixture parameter; it cannot be counted as a PostgreSQL test that returned without exercising its body. The committed UI fixture is the original r1 real File result.
