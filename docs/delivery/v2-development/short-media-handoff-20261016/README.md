# Exact short-media handoff through the original Timeline owner

Local source follows integrated CPU checkpoint `1278e4f95affb1e33d8b7676c2930226ad7b49e0`. The separate offline packaging commit `2ad62dcfb1ff5695b3720462b4f6ca28340491ec` does not change application owners. This slice changes only frontend handoff/range handling plus dedicated tests; no backend API, duration probe, store, execution engine, permission or provider behavior is added.

## Actual failure before the fix

`../short-media-handoff-red.json` and its log retain the unchanged-source **1 failed / 1 PostgreSQL deselected**, exit 1 reproduction. A real original audio trim creates and approves an 800 ms FLAC Asset. The mounted original reference handoff inserts that exact ID/version/digest with a fabricated 1000 ms out-point. Original Timeline native rendering refuses the request and the original expected-SUCCEEDED assertion fails. `red-exact-handoff.json` retains the exact source proof and actual mounted clip; the failure is not a direct helper-only demonstration.

The separate `../short-media-handoff-first-green.json` retains the first **1 passed / 1 PostgreSQL deselected** development result, with unchanged sources. The expanded current-source development selection is **4 passed / 4 PostgreSQL deselected** in `../short-media-handoff-expanded.json`, also unchanged sources. Final selection is recorded below separately.

## Bounded behavior

- Provenance `source_task_id` is only an original-receipt lookup hint. The existing guarded production GET must return an APPROVED known `m8.audio.trim` or `m9.timeline.multitrack` output, bound to the same project/branch, output ID, approved Asset version, digest and kind, with finite positive measured duration and the original producer's measurement profile. Requested duration and arbitrary Asset metadata never supply a default.
- A verified output gets the existing up-to-one-second default, bounded by its actual duration. The explicit reference handoff rereads both exact Asset and receipt before acceptance. Missing, changed, unapproved or mismatched proof cannot silently preserve an automatic default.
- Imported or otherwise unknown audio/video requires explicit source start/end. Partial authored input is preserved on reread. The helper neither invents a duration nor truncates an explicit range to fit remaining Timeline space. Existing image insertion is unchanged.
- The ordinary Asset picker uses the same proof/range contract. Its receipt read happens only on explicit Add. Late identity/selection/draft-generation reads are retired, and existing permission/current/busy guards still own access.
- Acceptance changes only the existing local Timeline draft. Save, original source validation, native render, human output review and reopen remain explicit original-owner operations.

## Tests and evidence

The independent four-file frontend selection passes **87/87**: `studioTimelineAssetRange.test.tsx`, `StudioTimelineShortMedia.bridge.test.tsx`, `StudioTimelineAssetHandoff.test.tsx`, and `IndependentStudioWorkspace.test.tsx`. It includes mismatched receipt identity/status/output/measurement fields, invalid durations and ranges, missing proof, authored partial input, late identity/selection/unmount/draft generation, and existing original handoff/workspace guards. `ui-independent.log` is retained; the reviewer checked the exact runtime and test blobs in `reviewed-source-hashes.json` and found no scoped blocker.

Adjacent unchanged frontend selection passes **116/116** across `ProductionTimeline.test.tsx`, `TimelineSourceEditing.phase6.test.tsx`, `TimelineTransferReview.test.tsx`, `creativeProductionClient.test.ts`, `nle/nlePanels.test.tsx`, and `nle/timelineOps.test.ts`. Exact command: `node node_modules/vitest/vitest.mjs run <the six src-relative paths> --no-cache --maxWorkers=1 --minWorkers=1`, from `frontend/`; output is `ui-adjacent.log`.

The initial existing UI run failed 13 cases because unknown audio/video fixtures had relied on the old invented duration. `ui-contract-transition.log` preserves that result. Existing assertions were retained; those fixtures now explicitly supply their source range and assert the added range callback argument. The corrected owner run is **64/64** in `ui-r2.log`. The first typecheck found an optional measurement typing error; `type-initial.log` preserves it and `type-r2.log` records the corrected check. These are development failures, distinct from the actual native RED.

## Final current-source real media matrix

`../short-media-handoff-final.json` records **12 passed / 9 PostgreSQL deselected**, exit 0, `sources_changed_during_check=false`, at source HEAD `2ad62dcfb1ff5695b3720462b4f6ca28340491ec` plus the exact handoff blobs listed in `reviewed-source-hashes.json`. Its complete command, isolated paths, all captured source SHA256s and log hash are retained. The final selection consists of:

1. Four new File cases in `test_v2_timeline_short_media_handoff.py`: approved 800 ms FLAC; approved 700 ms gapless MP3; approved 400 ms original Timeline video; and imported 400 ms video with an explicit unknown-source range. Each supplies real original Asset/receipt data to the mounted handoff, persists that exact resulting draft through original Timeline Save, renders actual CPU MP4, independently decodes picture and audible PCM, explicitly approves the output, and reopens through fresh original File service instances.
2. Both render/export parameters of `test_v2_audio_editing_pipeline.py::test_real_flac_formal_asset_atomic_edit_cpu_render_review_bytes_and_reopen`.
3. `test_v2_audio_flac.py::test_actual_flac_original_private_review_reopen_and_pcm_proof` and `test_v2_audio_mp3.py::test_actual_mp3_private_review_reopen_and_lossy_pcm`.
4. `test_v2_timeline_asset_handoff.py::test_exact_asset_draft_save_reopen_and_cas` and the three original `test_v2_nle_review.py` cases.

`actual-media-probes.json` records successful independent ffprobe commands for each exact formal source blob and each rendered output, byte counts, SHA256s, original measured receipt, actual mounted source range, and decoded PCM/RGB hashes. The four outputs were independently decoded to ten 64×64 frames and audible 48000 Hz stereo PCM. MP3 source timing uses the original validated gapless PCM measurement; an MP3 container probe can include encoder padding and is not substituted for that measured duration. Pytest's convenience `current` symlinks are excluded from the four unique artifact records.

Final `tsc --noEmit -p tsconfig.json`, `vite build`, and `check_ui_design_tokens.mjs` all exit 0; logs are retained as `type-final.log`, `build.log`, and `tokens.log`. The existing large-bundle warning and existing Starlette/httpx deprecation warning remain visible; dependencies and warning thresholds were not changed.

## Acceptance limits

Only local authored synthetic media, installed Node/Python dependencies, and installed CPU ffmpeg/ffprobe are used. The frontend bridge is a mounted jsdom component test, not a browser session. PostgreSQL is deselected, not counted as passed. No model/provider, GPU, external NLE application, download, paid operation, blocked lifecycle/security test, browser retry, push or release is part of this evidence. Production adoption remains disabled.
