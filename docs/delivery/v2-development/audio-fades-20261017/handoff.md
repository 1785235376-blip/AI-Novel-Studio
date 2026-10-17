# Standalone Audio fades — bounded implementation handoff

Status: implementation and primary backend gates complete; Scoped implementation, CPU, frontend, independent rerun, public packaging and independent archive inspection complete. Five verified pre-existing failures remain unresolved. This is not an all-suite pass.

## Scope and contract

Extends the original standalone `m8.audio.trim` command, production preview/recipe and `StudioAudioExecution._trim`. No new queue, provider, engine, NLE owner or Graph feature.

- Optional `parameters.fade_in_ms` and `fade_out_ms`: strict integers from 0 through 120000 ms; explicit null, bool, float and string rejected.
- Durations are relative to the trimmed output. Their sum must not exceed `out_ms - in_ms`; invalid values are rejected, never clamped.
- Blank UI fields/absent API fields remain omitted. Explicit zero remains present and bound into original command, recipe and request hashes.
- Gain precedes PTS reset and positive linear (`tri`) fades; original output rate/channel conversion and codecs follow. No positive fade preserves the previous empty or gain-only filter argv exactly.
- Graph trim stays in/out-only. Fade presence in body, command or recipe triggers exact existing-layer binding checks; omitted-fade historical paths keep their previous serialization and hashes.
- Existing private candidate, explicit Review, formal Asset, reopen, cancellation, UNKNOWN, source pins and capacity owners remain in place. Measurements retain their existing schema.

## Provenance

Worktree baseline: `fb372d85f67dd32620ee20221e1aaa2b1e65bfba`.

The pre-edit golden fixture `tests/fixtures/studio_audio_fade_omission_v1.json` has SHA256 `1aa9100e0d3622b6d5a99019b5a7f33aa60e94173a9c962dce0a500c3a63c2d5`. It captures real original serialization/preview/recipe/body/binding/hash functions with fixed synthetic scope/source hooks and constructed receipt input. It is not an owner-created receipt, native processing result or lifecycle execution. See `baseline-provenance.md` and the untouched capture script/log/receipt.

Existing omitted-control WAV historical command/request/preview/recipe/owner hash constants matched; Graph in/out-only, controlled WAV, FLAC and versioned MP3 serializations were also frozen before edits. Explicit-zero identity tests are separate from omitted-field compatibility.

## Primary verification (File profile; neutral tests retained)

All launches used the unchanged original `scripts/run_v2_checks.py`, owned profile/basetemp, approved existing interpreter, offline/memory configuration, and before/after origin probes. Primary run source snapshots were unchanged. PostgreSQL-only cases were explicitly deselected, not claimed passing.

| Gate | Result | Evidence stem |
|---|---|---|
| New contract/API r3 | 68 passed, 18 PostgreSQL-only deselected | `audio-fades-contract-r3` |
| Protected prior audio | 228 passed, 5 failed, 119 PostgreSQL-only deselected | `audio-fades-audio-regression` |
| Exact five failures on unchanged baseline | 5 failed identically | `audio-fades-baseline-listing` |
| Model/media/Graph owners | 327 passed, 23 PostgreSQL-only deselected | `audio-fades-owner-regression` |
| New fade CPU envelope/lifecycle | 13 passed, 13 PostgreSQL-only deselected | `standalone-audio-fades-cpu-r1` |
| Frontend | 337 tests passed in 14 suites, including 29 new fade tests; forced TypeScript, build, token guard passed (52 files) | `audio-fades-frontend-{tests,typecheck,build,tokens}-r1` |
| Independent rerun | 217 backend passed, 97 PostgreSQL-only deselected; 29 UI passed (overlap with primary, not additional unique cases) | `audio-fades-review-{backend,ui}` |
| Public offline packaging | 87 passed; four actual wheel/sdist archives fully inspected | `audio-fades-packaging-r1`, `packaging-evidence/index.json` |

The first two new-test attempts are retained honestly: `audio-fades-contract` had 50 passes and 9 setup errors from missing imported `mounted`; `audio-fades-contract-r2` had 50 passes, 9 PostgreSQL-only deselections and 9 setup errors from missing imported `prefix`. Only those fixture imports in the new API test were corrected, with parent authorization. No assertions, product logic or old tests were changed to address those errors.

## Pre-existing scoped failure, still open

The following five nodes in `tests/test_v2_studio_audio_listing.py` fail identically both with fades and in untouched `studio-director-review` at the exact baseline commit:

1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

The unchanged raw request hash check in `_validated_job` raises `STUDIO_AUDIO_JOB_BINDING_CHANGED` (409) before the malformed body, Graph or source-specific validation expected by those tests. Expectations are respectively operation-unsupported (400), prompt-invalid (400), source-invalid (400), Graph-binding ValueError, and source-binding-mismatch (409). Read-only history assessment identifies raw-hash-first validation introduced in `14ced102` to protect historical MP3 admission, while tests introduced in `2fda20f` expected shape-first errors. This is an unresolved contract-precedence decision, not an assumption that the tests are obsolete. No valid-job regression was identified by that assessment. This slice does not change validation precedence or the old tests. Baseline reproduction used the existing baseline worktree without checkout/reset/source edits; source brackets were unchanged, and copied receipt/log bytes are retained.

## Remaining acceptance

Actual CPU fade tests passed with real WAV/FLAC/MP3 bytes, nonzero source trim location, gain/resampling/channel conversion, private candidate, reopen and explicit Review. Reported worst lossless per-sample deviation was 0.542 LSB against a fixed 8 LSB bound; worst MP3 normalized window-envelope RMS shape relative deviation was 0.0505% against a fixed 12% bound, with exact 1000 ms / 22050 decoded frames. Omitted versus explicit-zero decoded PCM matched in all three formats. The MP3 absolute gain plateau was 4030.14 versus expected 4242.64, separately within the fixed 12% lossy tolerance. Durable raw observations and binary provenance are indexed at `../audio-fades-cpu-evidence/evidence-index.json`. These are synthetic-fixture CPU tests, not subjective quality or provider/model acceptance.

Independent review opened all four actual archives, verified every member size/hash and the three changed backend modules, and found no runtime/cache/dependency directories in the payload. Wheels contain 511 payload files each; source distributions contain 515 each. No archive was installed or extracted. The final runtime/test source closure has 2559 file hashes; raw receipts preserve both before/after maps. The final `evidence-index.json` supersedes the retained draft index. No PostgreSQL, browser, model/provider or full-suite success is implied by the current results. The parent may scope the existing listing precedence mismatch separately.
