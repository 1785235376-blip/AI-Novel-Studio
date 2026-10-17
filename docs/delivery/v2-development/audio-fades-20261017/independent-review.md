# Independent bounded review

Baseline: `fb372d85f67dd32620ee20221e1aaa2b1e65bfba`.

Verdict: no new blocking finding in the standalone fade changes. This is bounded File-profile review, not an all-suite or product-acceptance pass.

## Contract and source review

- New fade controls reject explicit null, boolean, float and string values, accept strict integer 0–120000, and reject sums exceeding the selected trim duration. Equality is allowed.
- Absence is omitted from legacy serialization; explicit zero is retained in command, body and recipe identity. Frozen pre-edit fixture SHA256 remains `1aa9100e0d3622b6d5a99019b5a7f33aa60e94173a9c962dce0a500c3a63c2d5`.
- Baseline capture used unchanged production serializers, preview/recipe/body/binding/hash functions with synthetic source hooks and a constructed receipt input. It was not an executed or owner-created receipt. Tests consume frozen bytes, not newly generated expected values.
- Any fade key in body, command or recipe triggers exact cross-layer binding. Existing MP3 marker checks remain; omitted-fade legacy WAV/FLAC/Graph paths retain their identities.
- Positive filters apply gain, reset timestamps and use linear output-relative fades. Existing source seek and bounded duration remain unchanged. Zero-only/absent helper argv is exactly legacy empty/gain-only argv; surrounding native invocation is unchanged.
- Existing Audio owner, private candidate, source pins, explicit review, Asset promotion, reopen and UNKNOWN/cancellation paths remain the owners. No second engine is introduced.
- Frontend rejects null fades even in projected commands, retains explicit zero, omits blanks, checks sum bounds and uses the unchanged controller consent/stale-response machinery.
- CPU reference math uses output-relative envelopes with distinct discarded source regions and fixed pre-run 8-LSB lossless / 12% MP3 RMS tolerances. Exact sample counts are required without manual codec-delay shifts. Tests cover private candidate, explicit review, idempotent promotion and durable reopen.

## Independent execution

Serialized through unchanged `scripts/run_v2_checks.py`, using the approved clean interpreter, natural-startup check, before/after runner-child origin proofs, owned profiles/basetemp, offline settings and File-only selection:

- `audio-fades-review-backend`: 217 passed, 97 PostgreSQL-only deselected. New contract/API/CPU tests plus old WAV/FLAC/MP3/compatibility tests.
- `audio-fades-review-ui`: 29 passed, one worker, cache disabled.
- Both origin probes passed. All four receipts have 2559 unchanged source hashes, independently checked against final files.

Receipts and logs are retained in `docs/delivery/v2-development/` with the above stems. `audio-fades-review-natural.json` retains the normal interpreter startup check. No product/test source was edited by the reviewer.

## Primary evidence audit

Verified primary frontend 337 tests across 14 files, TypeScript, Vite and 52-file UI token guard: exit 0, unchanged sources and matching retained log hashes. The existing Vite large-chunk warning remains.

Verified all 15 durable CPU evidence copies against their index hashes, including 12 acoustic/lifecycle observation JSON files. Primary CPU suite passed 13 File cases with 13 PostgreSQL-only cases deselected; no tolerance changes were made after results.

Protected existing tests, dependency manifest/lock and runner are unchanged. Whitespace diff check passed.

## Unresolved baseline failures and limits

The primary prior-audio regression has 228 passes and five failures. All five reproduce identically on the untouched baseline worktree, with verified exact baseline HEAD, unchanged source bracket and matching copied log hash:

1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

All are in `tests/test_v2_studio_audio_listing.py`. The unchanged raw immutable-request hash check raises `STUDIO_AUDIO_JOB_BINDING_CHANGED` before the tests' expected deeper shape/Graph/source error. They remain unresolved; no protected assertion was weakened or excluded from the reported primary result.

No PostgreSQL, browser, desktop, live model/provider, remote push or subjective audio-quality acceptance was performed. Approval is limited to the reviewed implementation and evidence above.

## Packaging follow-through

Primary packaging gate passed 87 tests with unchanged sources. Independently opened all four actual archive files read-only (two wheels, two source distributions), verified each archive SHA256 and every member's size/SHA256 against its persisted full inventory, and checked the three changed backend modules byte-for-byte against reviewed source. Wheels contain 511 file payloads each; source distributions contain 515 each. No `.runtime`, `node_modules`, `__pycache__` or `.git` path was present. No archive was installed or extracted. Evidence index: `packaging-evidence/index.json`.
