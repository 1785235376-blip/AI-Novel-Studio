# Four-slice merged-source integration verification

PASS for the scoped checks on full-root commit `39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a`, tree `adac601f4299c190507012e7dad984c2095c0ff5`. This is merged-source execution, not a sum of branch acceptance.

## Actual serial gates

- Clean natural startup and original-runner child PathFinder proof before and after: PASS. Product and pytest modules were not imported by the origin probes. Exact full-root origins and approved interpreter/dependency metadata verified.
- Combined affected File/installed-CPU backend: **811 passed, 303 PostgreSQL-only deselected**, 23 actual modules. Two Pydantic warnings retained.
- Combined frontend: **71 files, 1,076 tests passed**, explicit actual paths deduplicated in `scope.json`. One worker, no parallel files, no cache, original Vite config. Existing duplicate-key warning retained.
- Forced TypeScript (`tsc -b --force`), Vite production build and design-token guard: PASS. Existing build chunk-size warning retained; token guard checked 52 files.
- Actual offline PUBLIC four suites: **87 passed**, one warning retained. Two wheels and two sdists built using existing tools; each archive's complete included source bytes verified against the current checkout, including all five changed backend modules. No installation or extraction performed. Durable build/stage receipts, logs and archive payload inventories retained in `packaging-evidence/`.

Eight original-runner receipts share one identical **2600-path** source map, unchanged before/after each gate and equal to final files. Receipt/log hashes are reconciled in `evidence-index.json`.

## Preservation and provenance

All four feature commits' changed paths match their exact merged blobs, with full ancestry preserved: canvas `6ea323c`, Audio `918b816`, Prompt `f193bb4`, B05 `17d64dc`. Original tests unchanged: 1306; historical docs preserved: 8536. The complete 11773-file tracked tree is SHA256-frozen before/after; no tracked file changed. No protected Codex/runtime/runner overwrite. Full integration root retains historical documentation; sparse branch receipts alone did not prove that preservation.

The original runner SHA256 remains `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5`. Only the clean `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python` ran verification. The separate installed packaging build interpreter is pinned to SHA256 `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`. PUBLIC manifest SHA256 remains `c54c87073dbd7c09d4844c6b9884c1a466491b3a9e86064511fa1983acbc9178`, exact B05-reviewed addition only. No installs, provider/model calls, paid CI, PostgreSQL, browser/visual/native-Windows acceptance, push, release or main merge.

## Explicit unresolved baseline and limits

Five existing `tests/test_v2_studio_audio_listing.py` failures remain unresolved. Previously reproduced on the unchanged pre-fade baseline (see `../audio-fades-20261017/independent-review.md`), they are excluded from this scoped run and are not counted as passing:
1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

Their existing immutable-request hash fence yields `STUDIO_AUDIO_JOB_BINDING_CHANGED` before expected deeper validation. This task did not rerun or repair them. No full-green repository/product claim, translation quality claim, professional-canvas completion, R3-GATE/security relaxation or new live provider acceptance follows from these scoped passes. Parent owns final source/evidence commit and canonical inventory reconciliation.
