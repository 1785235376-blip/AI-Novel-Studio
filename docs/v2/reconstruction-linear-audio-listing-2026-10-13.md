# Reconstructed linear Studio audio receipt listing

## Source and scope

This is a new, tested reconstruction against local integrated source
`587d9a4ce63796bfeea387eaf13fd5c4d7b889ac`, not recovery of missing implementation
bytes. The concrete baseline defect was in
`app/services/studio_audio_execution.py::StudioAudioExecution.list`: after loading
one original actor/branch audio queue, it called `AudiobookService.find` from the
start for every requested receipt.

A deterministic test over 180 actual persisted, owner-shaped receipts observed
16,470 job visits: the outer 180-row pass plus 180 progressively longer searches.
The revised normal string-ID path visits the same snapshot once, retaining the
original receipt order, complete history, and independent returned copies.

Only this original-owner service changes. The added test file does not modify
any original test, assertion, fixture, marker, or backend skip gate. There is no
new job queue, owner database, provider, model invocation, execution protocol,
HTTP route, stored-state migration, or automatic replay.

## Compatibility and fail-closed behavior

- Extract the existing receipt validator without changing its body, source,
  provider, request digest, branch, version, or graph-binding checks.
- Single-job reads and mutations still use the original authority check and
  `AudiobookService.find`; cancellation and version-conflict checks are unchanged.
- Listing keeps the original actor partition, scope/incarnation filtering,
  feature/V1 visibility, and guards before reading and before returning.
- Validate the entire matching history, including malformed tails beyond 600
  rows. Preserve the existing per-receipt prompt, source-count, and binding-byte
  limits. There is no existing listing limit or pagination contract to change.
- Preserve the existing `STUDIO_AUDIO_JOB_NOT_FOUND` denial when the first row
  with a requested ID belongs to a different owner/scope or to legacy audio.
- Reject a second requested receipt with the same ID using the existing
  `STUDIO_AUDIO_JOB_BINDING_CHANGED` error, including identical duplicates.
  Previously the first receipt was returned twice, hiding a malformed second
  receipt. This is deliberately fail-closed; no stored history is rewritten or
  silently deduplicated. Unrelated-owner duplicates and foreign tails stay
  filtered as before.
- Keep the original lookup fallback for malformed non-string legacy IDs and
  preceding missing-ID errors. This avoids adding ID validation or migration
  rules under an optimization change. The linear guarantee applies to the
  string IDs produced by the original queue owner; malformed non-string-ID
  histories retain the original lookup complexity.

This removes repeated queue scans, not the original whole-file load. It does
not introduce a new queue byte cap, claim constant memory, truncate history, or
claim bounded I/O for `AudioProductionStore.load`. Index memory is linear in the
number of visible string IDs; returned copies remain proportional to the
matching receipt content. Source-currentness refreshes remain the responsibility
of the unchanged execution/review guards, not historical receipt listing.

## Verification

All runs used the same pinned CI interpreter and installed dependency set:
Python 3.12.14, FastAPI 0.142.2, Pydantic 2.13.5, pytest 8.4.2. The original
`scripts/run_v2_checks.py` isolated runtime state and recorded before/after source
hashes. Raw logs, private paths, runtime configuration, and database evidence are
retained privately and are not part of this report.

| Check | Actual result |
| --- | --- |
| Initial additive suite on untouched baseline | 3 failed, 31 passed, 1 canonical PostgreSQL skip |
| Initial additive suite after the first patch | 34 passed, 1 canonical PostgreSQL skip |
| Final File/neutral checks and original audio/workspace regressions | 255 passed, 172 canonical backend skips |
| Final real PostgreSQL checks | 172 passed, 255 deselected |
| Independent read-only compatibility review | Approved after preserving malformed-ID lookup behavior |
| `git diff --check` | Passed |

The three original failures were the quadratic visit-count assertion and the
identical/malformed shadowed-duplicate rejection assertions. Foreign-first denial
already passed before the change and remains covered afterward. Later additive
checks cover original per-receipt limits, unrelated foreign tails, legacy ID
compatibility, and real File/PostgreSQL project deletion/recreation isolation.
The final suite also verifies reopened durable queues, original cancellation CAS,
actor/project/branch/scope/incarnation separation, legacy-reader isolation,
permission revocation, source-snapshot binding, and deep-copy behavior.

The final PostgreSQL run uses the unchanged
`scripts/run_v2_postgres_checks.py --fresh-database` harness and a distinct,
checkout-owned disposable cluster. It verifies live PostgreSQL 17.11, creates a
new database from `template0`, confirms zero application objects, and applies
all 20 unchanged migrations. All selected checks passed, and the harness stopped
its owned server cleanly. Both final runs recorded unchanged before/after source
hashes. Each reported one existing TestClient dependency deprecation warning.

### Reproduction commands

Use the pinned CI Python environment and existing trusted PostgreSQL binaries.
The variables are local operator inputs, not captured configuration.

```sh
TESTS="tests/test_v2_studio_audio_listing.py tests/test_audio_production_api.py \
tests/test_audio_provider_config.py tests/test_audio_providers.py \
tests/test_r3_audiobook_preparation.py tests/test_r5_pause_aware_audio.py \
tests/test_r5_voice_subtitles.py tests/test_r5_voice_subtitles_mounted.py \
tests/test_phase1_media_project_authorization.py \
tests/test_v2_independent_workspace.py tests/test_v2_independent_workspace_api.py"

"$PYTHON" -B scripts/run_v2_checks.py audio-listing-file-reviewed -- \
  python -m pytest $TESTS -q --tb=short -p no:cacheprovider \
  --basetemp .runtime/audio-listing/file-reviewed

"$PYTHON" -B scripts/run_v2_postgres_checks.py \
  --pg-bin "$PG_BIN" --data "$OWNED_PG_DATA" --port "$PG_PORT" --user "$PG_USER" \
  --fresh-database --database "$UNIQUE_V2_DATABASE" audio-listing-pg-reviewed -- \
  python -m pytest $TESTS -q --tb=short -p no:cacheprovider \
  -m postgres_backend_only --basetemp .runtime/audio-listing/pg-reviewed
```

### Verified final source hashes

- `app/services/studio_audio_execution.py`:
  `368c5025baa287186d3916d344c571ef483f3b37b182ab71bb18db4dbefd03de`
- `tests/test_v2_studio_audio_listing.py`:
  `2cb1bb46fd8e7ed520bbac10d8da930036558c46e42f844ebdcf5399e17bf76f`

## Remaining boundaries

No frontend/browser, full-repository suite, hosted CI, Windows, GPU, or real model
quality acceptance was run for this scoped change. Catalog regeneration belongs
to the final integrated tree and is not claimed here. Historical module
classifications are unchanged. This work was prepared as a local commit only;
pushes and external uploads are outside this task.
