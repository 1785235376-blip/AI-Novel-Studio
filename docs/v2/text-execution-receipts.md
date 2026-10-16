# M4-C persisted text-execution receipts

## Scope and owners

This is a bounded extension of the shipped local TextModelNode → ModelBroker →
original JobManager → WorkflowRun → AssetLibraryService path. It adds no model
registry, queue, workflow/review state machine, transport or persistence owner.
IMAGE/VIDEO and reserved API-provider execution remain outside this slice.

The existing `archive_result: true` dispatch opt-in now records
`creative-graph-text-execution/1`. The current Studio UI already opts in when the
server advertises result storage; there is no extra required user action.
The result remains actor-private, a proposal for the existing human review,
and is never automatically applied to a manuscript.

## Compatibility and durable binding

- The outer `creative-graph-text-asset/1` contract, exact source receipt, asset
  review projection and two-phase archival recovery remain unchanged.
- New opted-in dispatches add `execution_receipt_contract` to the existing
  `model_asset_intent`, and bind the same contract plus
  `execution_receipt_source_version` in the original `GraphRequestBinding`.
  Both participate in the original `Job.expected_request_digest`.
- The original generation repository already seals that binding and request
  digest against later updates. Removing the intent marker or changing its
  admission source version cannot downgrade a current run into legacy recovery.
- Both new binding fields are entirely omitted for old bindings. Their
  serializer does not introduce nulls into historical canonical request bytes.
- Persisted M4-B intents/jobs/assets without the marker retain the exact v1
  recovery path and omit the new receipt. No automatic migration/backfill occurs.
- API clients omitting `archive_result` still receive no asset-output contract.

## Immutable snapshot

The existing private text asset stores `_text_execution_receipt` in its first
metadata commit. It participates in the same existing idempotency identity as
the output bytes and original source receipt. Its bounded contents are:

- Exact UTF-8 prompt, with no trimming or truncation, and its SHA-256
- Exact adapter parameters: temperature, max-output tokens and stop sequences
- Actual provider/model IDs, original route ID and route fingerprint
- Full original persisted broker chosen identity, retained privately
- Explicit model-evidence kind, model/runtime metadata fingerprints and the
  runtime version if the original owner recorded one
- Original persisted request digest, actual execution mode, graph/workflow/run,
  node, job, admission source version, input/preview/graph/output digests
- Completed settlement ID and authoritative UTC terminal time
- `quality_verification: NOT_RUN`

Prompt size remains at most 32,000 UTF-8 bytes; original route-identity metadata
is capped at 16,000 canonical JSON bytes; the complete new receipt and containing
text-result metadata are capped at 64,000 bytes. Legacy metadata retains its
16,000-byte cap. A receipt is immutable across the existing draft-to-approved or
draft-to-rejected asset version transition.

### Admission byte budget

New receipt-bearing dispatches validate the actual JSON-encoded receipt and its
complete initial asset metadata after the existing route/permission policy and
before the original JobManager prepares a Job. Prompt UTF-8 length alone is not
sufficient: JSON escaping can increase the stored byte count a second time.
The same payload builders and original asset validators serve admission and
terminal archival, retaining both existing 64,000-byte limits and error codes.

The preview, prompt, node, route identity and source version are exact. Values
not yet emitted by their owners use proven maximum encoded forms solely for
sizing: the original UUID Job ID, SHA-256 digests/reservation key, and the longest
UTC `datetime.isoformat()` settlement timestamp. These transient values are
never persisted, exposed as successful evidence, or used to grant authority.
Actual execution replaces all of them with the original durable owner values.

An oversized receipt returns the original HTTP 422 `EXPERIMENTAL_INVALID` with
`TEXT_EXECUTION_RECEIPT_INVALID`; metadata-only overflow retains
`TEXT_RESULT_METADATA_LIMIT`. It creates no Job, reservation, generation or
asset and does not change the run. No prompt is truncated and no original input,
metadata, timeout or legacy opt-out limit is increased. Existing completed
oversized Jobs, if any, retain their output and INCOMPLETE state: this check does
not silently migrate, discard or replay them.

The terminal time is the once-only settled broker ledger's `updated_at`, not the
Job's notification timestamp. The original JobManager can legitimately emit a
later terminal notification without changing historical execution provenance.

## Verification and privacy

Before archival and every scoped projection, the graph coordinator checks:

1. Current feature, actor, project incarnation, branch, graph source and route
   authority using the existing owner leases and guards.
2. Agreement between original live/restored Job fields and original durable Job
   storage; completed status, completed outcome and completed terminal hook.
3. Exact preview/input binding and the canonical request-data digest against
   the original persisted `expected_request_digest`. The shared digest helper
   hashes passive data only; no invocation, adapter or callback is reconstructed.
4. Original broker preview ownership/version/chosen identity, route fingerprint,
   settled ledger ownership, route/model/job/preview links, dispatched state,
   successful completion and known-zero accounting.
5. Exact private snapshot and immutable outer model/parameter fields, plus
   verified asset bytes and output digest.

Commit guards repeat the relevant source/route/job/ledger checks. Asset review
also compares the expected sealed execution receipt at the original asset-owner
commit boundary. Corruption or a race masks the result and prevents a successful
review projection; a durable original workflow decision is never invented or
rolled back to compensate for a failed asset projection.

`AssetLibraryService.public()` recursively removes the complete private receipt,
including its prompt and original route identity. Generic metadata updates cannot
set the reserved field or alter sealed text-result provenance. Existing actor,
project-incarnation, branch and feature fences continue to govern the asset.
Only the revalidated actor-scoped graph DTO adds `asset_output.execution_receipt`;
that projection omits the full route identity. Incomplete/cancelled/failed results
do not expose a new execution receipt or private prompt.

The frontend validates the additive DTO's complete shape, bounds, workflow,
parameters, preview prompt where available, and honest mode/evidence labels.
It uses the existing receipt surface and primitives. Cryptographic verification
is performed on the server; the synchronous browser parser validates digest
syntax and consistency, not cryptographic authority.

## Inference versus evidence and quality

`mock_standin` requires the original synthetic route and is displayed as a test
stand-in. It cannot become `real` by changing an asset label. `real` requires the
original completed Job to report real execution and the original route to have
verified local Model Center identity and confirmed license evidence.

`MODEL_CENTER_METADATA` is a bounded metadata/artifact identity fingerprint.
It is **not the SHA-256 of the complete model file**. The original broker route
fingerprint is likewise a registered-identity fingerprint, not a model-file hash.
A real-host acceptance report may separately record a fully downloaded GGUF
file's SHA-256 and runtime argv, but must not substitute those claims for the
owner's original persisted identity or claim they were available in every route.

Successful runtime completion is distinct from output quality. No quality
evaluation is performed by this receipt path, and quality stays `NOT_RUN`.

## Recovery and verification

An authorized read/refresh makes at most one bounded archival convergence
attempt, retaining the existing cooldown, source lease and two-phase recovery.
Neither a missing receipt, failed asset write, process restart nor an uncertain
terminal hook schedules/replays inference or replaces the original Job.

Dedicated backend coverage: `tests/test_v2_text_execution_receipts.py` and
`tests/test_v2_text_execution_admission.py`.
This uses the real existing owners with built-in Mock execution explicitly
labelled synthetic. Its historical/corruption fixtures seed only owned test
storage; they do not bypass production save invariants. It covers exact/large
Unicode prompts, request/identity/ledger tampering, contract/source-version
downgrade, sealed review races, privacy, restart without authority reconstruction,
one asset/job, terminal timestamp stability and old v1 omission/recovery.

Dedicated frontend coverage: `studioGraphTextExecutionReceiptClient.test.ts`
and `GraphTextExecutionReceipt.test.tsx`; historical tests remain unchanged.
Real CPU inference is verified separately through the mounted API acceptance
exercise, never inferred from these synthetic/unit fixtures. PostgreSQL and
broader integration results belong to the combined acceptance report.
