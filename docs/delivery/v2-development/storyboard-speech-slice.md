# Storyboard → Audio speech request slice

Base: `ce3ac098`. Isolated sparse worktree; no push, paid APIs, runtime startup, or user-machine use.

## Delivered

- Explicit read-only `audio-request` preparation on an approved saved Storyboard, with exact document/shot pins, one selected dialogue index, configured provider/model, explicit voice and rate.
- Separate `storyboard_speech` provenance. Existing video validator and Graph schema are unchanged. Preparation creates no job and calls no model.
- Original Production preview, queue, Audio execute, private candidate, explicit review, and original formal Audio Asset retain and validate the speech provenance. No timeline placement or second owner/store.
- Exact authored dialogue is the speech prompt. Forged prompt/index/pins, stale sources, altered owner bindings and candidate provenance fail closed.
- Existing Storyboard production UI prepares speech into the existing media execution panel. Authority/selection changes invalidate pending preparation and stale handlers.

## Verification

- `storyboard-speech-backend-reviewed`: 199 File tests passed, including original Storyboard/video and Audio WAV/MP3 compatibility/listing regressions.
- `storyboard-speech-authority-file`: 34 speech File tests passed, including late authority revocation at provider resolution, pre-send and promotion; recreated project incarnation and wrong-actor no-private-read sentinels.
- `storyboard-speech-legacy-baseline`: exact canonical bytes and SHA256 from the actual `ce3ac098` MediaCommand serializer preserved for synthetic speech and video commands. Fixture records commit, path and synthetic provenance.
- Expanded mounted tests exercise both `/api` and `/api/v1`, trusted Host failures and denied collaboration scope, original private→reviewed Audio Asset, and no automatic timeline.
- PostgreSQL variants are prepared for the parent's serialized shared slot. This worktree did not run PostgreSQL.
- Frontend focused suite and independent review reported separately in retained receipts. Browser/visual rendering and real-model acceptance: **NOT_RUN**. Test speech is a synthetic WAV transport fixture, not synthesized dialogue or quality acceptance.

## Review correction retained

The first final backend regression caught an undefined `jid` in the new candidate-origin comparison (4 failed, 195 passed). `storyboard-speech-backend-final` preserves the failure. The fix binds expected origin to the original Audio owner's server-built review `source_job_id`, never the candidate's self-asserted identity. The corrected full selection passed 199 tests, including successful review/promotion and forged candidate rejection. Independent frontend review also required generation-fenced late responses and choice reset after accepted re-read; those regressions now pass.

## Cross-layer compatibility

Actual mounted `/api` and `/api/v1` preparation, queued, private-ready and approved receipts are retained as explicitly synthetic frontend fixtures. Decoder tests consume these actual response shapes. Original owner receipts legitimately emit null `needs_reconciliation` and `execution_state`; the frontend type now truthfully permits those nulls and the decoder preserves them. This changes no backend serialization and does not replace null with a false certainty.

Frontend final expanded regression: 279 tests across 12 files passed, covering captured speech responses, lifecycle/stale handlers, original media provider choice, image/video handoffs and MP3/FLAC/fades. Design token guard passed. Independent frontend review separately ran 87 focused tests. The retained visual attempt failed at missing bundled Chromium before any page ran; browser/geometry acceptance remains NOT_RUN.
