# Bounded Video reference-frame preparation

Status: implemented and frozen for root integration; focused real CPU, original-owner File/PostgreSQL and frontend checks pass. Whole-product acceptance and target Windows/model quality remain separate. No provider/model calls, external media downloads, new queue, commits or pushes occurred in this lane. Browser launch remains blocked and was not retried.

## User journey and roadmap scope

The original roadmap §13.3 and §23.5 request reference-video inspection, keyframe selection/sampling and truthful alternate paths when a provider cannot accept video references. This slice delivers:

1. In the original VIDEO asset workspace, select a formal saved Video asset.
2. Explicitly request a bounded integer-millisecond half-open sampling window and 1–8 samples.
3. Inspect actual decoded frames, source frame indices and rational PTS timestamps.
4. Select one successfully displayed image and explicitly confirm saving it.
5. Save exactly those reviewed PNG bytes as one original derived Image asset with immutable provenance. Existing image-to-video handoff remains a separate explicit operation.

The interval is an observation window. It does not alter V2V dispatch, trim a Video asset, infer motion/pose/depth/camera, detect semantic keyframes or claim conditioned video reconstruction. Existing provider, Video execution, Graph, media-operation allowlists, Shell and design tokens remain unchanged.

## Declared supported subset

- Existing MP4/WebM formal sources, maximum 25 MiB, 60 seconds and 4,096 decoded video frames
- Exactly one video stream; strictly increasing decoded PTS starting at zero; actual rational source time base, including supported VFR material
- Constant dimensions and supported RGB-convertible pixel formats; source dimensions at most 4096 by 4096; square pixels; no display matrix/nonzero rotation
- Sampling window at most 10 seconds; each target resolves to the first actual source PTS at or after the target and strictly before the window endpoint; repeated selections may legitimately resolve to the same frame
- Conservative decoded-work admission: source width × height × source frame count × (1 + unique selected frames) ≤ 1,000,000,000 pixels
- Overall 30-second native preparation deadline, bounded individual probe/decode calls, original guarded subprocess capture/cancellation/termination/reaping owner
- Aspect-preserving low-resolution RGB PNGs with a maximum 320-pixel edge, without upscaling; exact reviewed image bytes persist at save

320 pixels is deliberate: a square 320×320 RGB frame is at most 307,200 raw bytes, comfortably under the frozen original runner's 1 MiB capture ceiling. A square 640×640 RGB capture would exceed that ceiling. The UI explicitly says the saved image is the same low-resolution reviewed reference, not a full-resolution extraction; no larger unreviewed save-time rendition is substituted.

## Original-owner and security boundaries

IndependentWorkspaceService invokes the preparation helper. Preview has no persistent job/cache/asset state. AssetLibraryService alone persists the selected image, provenance and idempotent identity in its first metadata commit. The immutable marker binds actor/scope/incarnation, exact parent version/hash, window, selected frame index/PTS/time base, reviewed preview digest and PNG digest. Source lifecycle changes become stale provenance rather than silently rebinding prior output.

Native work uses the existing `run_guarded_process` and private media inspection directory. Both probe and decoder select a fixed mov/matroska demuxer. MP4 explicitly disables external data references and absolute-path references. Only file/pipe protocols are permitted; children write output only to bounded captured stdout. Source bytes, provenance, authority, feature gates and incarnation are checked before native work, after it and before publication. Read-only users may preview but cannot save. Private generation candidates must first pass their existing review path. Existing project privacy and immutable parent-DAG egress checks continue to apply to later I2V use.

Requests have strict closed DTOs, bounded streamed bodies and sanitized errors. No private metadata, source paths or native stderr are exposed. The UI hashes PNG bytes and the canonical response, checks exact source/timestamp evidence, invalidates stale/ABA/permission/blocked responses, revokes preview blob URLs and reuses the same save key after an uncertain response.

## Retained real CPU evidence

`video-reference-cpu-evidence-20261018/` contains:

- `synthetic-source.mp4`: locally generated testsrc2 MPEG4, 64×48, 10 fps, two seconds, 7,428 bytes
- `sample-0.png`: source frame index 3, PTS 3072 at time base 1/10240, exactly 300 ms
- `sample-1.png`: source frame index 8, PTS 8192 at time base 1/10240, exactly 800 ms; this is the selected saved image
- `frame-timing.json`: exact source/output hashes, rational timing, pixel dimensions, sampling request and receipt linkage

These are real locally decoded fixture bytes. The frontend's `videoReferenceWire.testFixture.json` is the genuine original-owner source/preview/save wire response, not a fabricated server contract. Additional native tests compare actual decoded pixel buffers for CFR MP4/WebM, VFR, B-frames and fractional timestamps.

## Focused verification

- Native final: **42 passed**, `video-reference-frames.json` / `.log`
- File new owner/API plus original clay/manual-mask/video-runtime regressions: **145 passed**, `video-reference-file-r2.json` / `.log`
- Real PostgreSQL marked owner/API parity: **45 passed**, `video-reference-pg-r1.json` / `.log`; existing database OID 16384 reused, no migrations/new database; original harness confirms server stopped and cleanup completed in `video-reference-pg-r1-postgres-runtime.json`
- Frontend: **71 passed across five focused files**, `video-reference-frontend-final.json` / `.log`
- Owned-file whitespace checks passed

Receipt identity caveat: the shared tree had concurrent work. Native final changed only frontend files during its run; PostgreSQL changed only one frontend test and an unrelated model-transfer file; frontend final changed only unrelated modelcenter files. The File run also overlapped the sampler's final hardening. Root's detached/frozen source checks must bind aggregate acceptance; no all-product or clean-tree green claim is made from these shared-tree receipts.

### Expected isolated File check

Use the original runner and recovered Python, with an owned basetemp:

```sh
.runtime/recovered-python-20261018/bin/python scripts/run_v2_checks.py video-reference-isolated-file -- python -m pytest -q \
  tests/test_v2_video_reference_frames.py \
  tests/test_v2_video_reference_owner.py \
  tests/test_v2_video_reference_api.py \
  tests/test_v2_clay_reference_asset_additive.py \
  tests/test_v2_manual_mask_owner.py \
  tests/test_v2_video_runtime_foundation.py \
  -m 'not postgres_backend_only' \
  --basetemp .runtime/v2-checks/video-reference-isolated-file/pytest-temp
```

Expected selected count for this exact current set: 187 (42 native + 145 File/regression). The marked PG set is only `test_v2_video_reference_owner.py` and `test_v2_video_reference_api.py`, 45 selected cases.

### Exact frontend focused list

- `frontend/src/creative/studioVideoReferenceContract.additive.test.ts`
- `frontend/src/creative/StudioVideoReferencePanel.additive.test.tsx`
- `frontend/src/creative/StudioVideoReferenceWorkspace.additive.test.tsx`
- `frontend/src/creative/studioClient.test.ts`
- `frontend/src/creative/StudioModelClaySave.additive.test.tsx`

Use Node from `/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin` and the existing frontend Vitest configuration through the original check runner. Shared typecheck/build/public manifest checks belong to root; no blocked-browser retry is authorized.

## Product file ownership

New backend:
- `app/creative/video_reference.py`
- `app/services/studio_video_reference_frames.py`
- `app/services/studio_video_reference_origin.py`

Original-owner stitches:
- `app/creative/workspace.py`
- `app/creative/workspace_api.py`
- `app/services/asset_library_service.py`

New frontend and original stitches:
- `frontend/src/creative/studioVideoReferenceContract.ts`
- `frontend/src/creative/StudioVideoReferencePanel.tsx`
- `frontend/src/creative/studioClient.ts`
- `frontend/src/creative/IndependentStudioWorkspace.tsx`

Tests/fixtures:
- `tests/test_v2_video_reference_frames.py`
- `tests/test_v2_video_reference_owner.py`
- `tests/test_v2_video_reference_api.py`
- Three new frontend tests listed above
- `frontend/src/creative/studioVideoReference.testFixtures.ts`
- `frontend/src/creative/videoReferenceWire.testFixture.json`

Root owns public-build manifest/catalog updates and final integration. Unrelated model-transfer work is outside this slice.
