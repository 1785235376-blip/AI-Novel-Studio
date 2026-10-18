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

## Remaining work

The reviewed-PNG UI save action and client receipt decoder are not implemented in this slice. No browser acceptance, real model/GPU run, full build, cross-module Storyboard/Image/Video adoption, or V2 release readiness is claimed. Existing exported PNG previews remain read-only until the next UI slice is wired and checked.
