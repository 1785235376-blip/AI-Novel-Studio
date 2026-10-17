# Standalone Audio sample-peak normalization

Implementation and independent scoped review complete. No merge, release, public-package, model, paid-provider, or native-desktop acceptance claim.

## Bounded contract

The existing standalone `m8.audio.trim` owner accepts optional `target_peak_dbfs` (-24 to -1 inclusive). Explicit null, boolean, string and nonfinite values fail closed. Absence preserves the original command, recipe, request, receipt and native argv. The graph parameter owner remains closed.

This first slice supports only verified PCM16 WAV source to PCM16 WAV output, with effective output rate and channels matching source. Compressed normalization, resampling/remix and fractional-frame millisecond boundaries are rejected, not silently converted or rounded. Existing WAV/FLAC/MP3 trim/gain/fades remain unchanged without the target.

The source measurement is a shared all-channel maximum absolute signed PCM16 sample over exactly the selected frames. Negative full-scale is 32768. Only that interval determines correction; discarded regions cannot affect it. Digital silence and correction outside -60 to +12 dB are rejected without clamping.

The target is before manual gain and fades. Normalized execution uses an unseeked source and `atrim=start_sample=N:end_sample=M`, resets timestamps, applies normalization plus manual gain in one double-precision volume stage, then the original linear fades. Target plus manual gain must be at most -1 dBFS. Fades can lower the actual output peak. This is sample-peak normalization, never LUFS, true-peak, loudness mastering, or subjective quality assessment.

Actual final WAV bytes are decoded and scanned. Frame count must exactly equal the selected source count. The final sample peak must be within the theoretical ceiling plus one S16 LSB, and without fades within one LSB of expected peak. Proof contains selected-source PCM hash/frame count, source-asset hash, source peak, target, correction, manual gain, output PCM hash/frame count and actual output peak. The existing receipt hash and candidate output digest bind this conditional proof. Persisted reads validate exact types/fields, finite arithmetic, source identity, frames and ceiling; missing or inconsistent proof is rejected through original read/reopen/review/reconcile paths.

Original guards are observed during bounded PCM scanning, encoding and publication. Existing private candidate → explicit reviewAsset → formal Asset lifecycle remains the only path. UNKNOWN reconciliation does not re-encode.

## Evidence boundaries

Pre-edit fixture and actual-method capture details are in `baseline-provenance.md`. Fixed synthetic collaborators and constructed queued receipt make that a serialization proof only. Frontend fixtures are structural transport/UI proof, not native audio evidence. CPU tests use tiny synthetic signals with actual installed FFmpeg and the original File owner. PostgreSQL-only parametrizations are deselected, never counted as passing. No new dependencies or media fixture copies were installed.

Fixed CPU acceptance thresholds were written before execution: one S16 LSB peak/ratio tolerance, two S16 LSB fade envelope tolerance, exact frame counts and exact PCM hashes. They were not tuned after results.

## Completed primary gates

- New backend contract/API/native CPU: 95 passed; 48 PostgreSQL-only deselected.
- Original unmodified audio editing, WAV, FLAC, MP3 and fades suites: 268 passed; 148 PostgreSQL-only deselected.
- Frontend: 360 passed in 15 suites, including 23 new mounted sample-peak tests.
- Forced TypeScript, Vite production build and token guard: passed (52 token-guard files). Vite emitted its existing chunk-size advice; no runtime failure.
- Three primary origin checks and source/log closure: passed. All nine primary receipts bind the same 2590-path source snapshot. Before/after source hashes match each other and current files. `primary-evidence-index.json` retains every source hash and receipt/log digest.
- Five real final-byte CPU observations are retained as JSON under `observations/`, copied without editing from owned pytest basetemps. No media files were copied.

The five previously established audio-listing validation-precedence failures were not included in this regression request. They are neither fixed nor counted as passing. Browser visual/geometry, PostgreSQL, live-provider/model and native desktop testing have not run. Independent scoped rerun is complete as recorded below. Public wheel/sdist packaging has not run for this source; parent will run actual packaging on the integrated branch. The Vite frontend build is not a public-package build.

## Ownership and integration

Baseline/current HEAD remains `e1e66cedeb7a140b6894850bc21a1e5ac7e06c16` on `work/dot-audio-normalize-20261017`; implementation is uncommitted for parent-controlled integration. Exactly six runtime files were edited, with three additive backend tests, one additive mounted frontend test and one frozen fixture. Original tests were not edited. No canonical coverage inventory, main branch, remote, release or package manifest changed. Parent owns commit, merge and combined-source regressions. `frontend/node_modules` is the supplied untracked dependency symlink and must not be committed. `.runtime` is excluded working evidence, not source.


## Completed independent review

The separate reviewer approved this bounded feature after 171 backend passes (48 PostgreSQL-only deselected) and 170 UI passes in four suites. These overlap the primary runs and must not be summed as unique coverage. Fresh natural startup and original-runner origin checks passed. All 13 primary/reviewer receipts share the same unchanged 2590-path source map, with receipt and raw-log hashes independently audited against current source. Reviewer artifacts are under `../audio-peak-review-20261017/`, particularly `review.md` and `independent-evidence-index.json`.

`complete-evidence-index.json` binds the complete final handoff, reviewer report/index, all 13 execution/origin receipts and logs, pre-edit provenance, frozen fixture, six runtime files, additive tests and five actual CPU observations. The observation copies are byte-identical to their original owned pytest outputs. Every final-byte observation retains source, selected PCM and output PCM hashes and measured frame/peak values; none is a substituted prediction or synthesized frontend fixture.

## Known unresolved listing baseline

These five `tests/test_v2_studio_audio_listing.py` failures were previously reproduced on the unchanged pre-fade baseline, as recorded in `../audio-fades-20261017/independent-review.md`. They were not run for this peak feature, remain unresolved, and are not counted as passing:

1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

The original immutable-request hash fence raises `STUDIO_AUDIO_JOB_BINDING_CHANGED` before their expected deeper shape/Graph/source error. No assertion was weakened or relabelled to hide that baseline. This delivery is scoped sample-peak normalization acceptance, not a full repository/product pass.
