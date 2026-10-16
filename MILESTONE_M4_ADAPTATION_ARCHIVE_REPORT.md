# TEXT-13 — private adaptation result archives and restart-safe review projection

Baseline: `e29e4329c895e72a79c7c1c2a40a8efcbb90f4d6` on
`feature/v2-narrative-platform`, existing Draft PR #47.

Status: **SELECTED VERIFICATION COMPLETE / PARTIAL — new SHA hosted CI pending**.

## Actual scope

This bounded follow-on completes the missing original AssetLibrary integration
for the preceding single-chapter/source-selection adaptation slice. The existing
AuthorPreparer, ModelRouter, ModelBroker, JobManager, Creative proposal/document
transaction and AssetLibrary remain the only owners. There is no extra queue,
asset store, model replay, automatic manuscript/Canon edit or Image/Video runtime.

New dispatches include a mandatory private-archive contract in the existing
proposal and original Job binding. The existing dispatch consent describes this
storage. An authorized existing read/refresh archives exact completed raw UTF-8
output as one actor-private DRAFT TextAsset v1 before valid parsed scenes/report
become reviewable. Invalid JSON can be retained as raw private execution evidence;
it is never presented as an adoptable screenplay. Explicit human adoption still
creates one independent screenplay through the original Creative transaction.
The same original asset then records APPROVED v2 without rewriting its bytes.

The archive receipt includes the complete actual Author adapter payload (including
nullable native parameters), original request digest, model/route identity,
source/version/selection, bounded execution deadline, original settled ledger
revision and the final Job publication marker. Generic asset and generation
routes continue concealing these private fields. Real-model quality is NOT_RUN.

## Publication and recovery boundaries

The original executor adds a passive adaptation marker only after terminal
accounting and its last live authority guard, at the final durable notification
write. Its earlier completed-accounting write has no marker. Original JobManager
restart only restores data; it never rebuilds callbacks, dispatches, requests or
model invocations. Missing/mismatched final publication remains fail-closed.

Phase A uses the existing scope → asset → project leases. Phase B releases those
leases before the normal Creative CAS transaction. Job publication checks acquire
the existing condition nonblocking. A write failure after either owner commits is
reconciled using the same immutable identity, not a second model call or asset.
The original human decision commits before its asset-review projection. Reads can
recover that projection without another user review or a duplicate screenplay.

Retry suppression is transient, bounded to 100 keys and two seconds after a
failed attempt. Each list request can converge at most one eligible item; already
archived items cannot starve later completed jobs. Permissions, Host binding,
source/privacy/version, incarnation, exact provenance and byte integrity are
rechecked before projection/commit. Failure/pending states hide unverified output,
Prompt-bearing provenance and review affordances together.

## Explicit byte limits

All limits use actual UTF-8/JSON serialization, without truncation:

- Raw and normalized generated adaptation output: 128,000 bytes each.
- Actual Prompt: 128,000 bytes; full Author request JSON: 256,000 bytes.
- Private execution receipt: 384,000 bytes.
- Complete initial provenance metadata container: 400,000 bytes. This is the
  original owner's logical metadata encoder, not a claim about final indented
  on-disk file size including system fields.
- Existing proposal history: unchanged 40 snapshots / 8,000,000 bytes, with
  encoded future headroom checked before preparation, reservation or inference.

The original Graph 32,000-byte output / 64,000-byte receipt behavior, assertions
and error contracts are unchanged.

## Original hosted browser failure retained

At e29, both Creative browser jobs reached 11 passed / 1 failed. The remaining
failure was the generic Script reload journey's unchanged exact-label check at
`v2-creative-live.spec.ts:490`, within its original 15-second expectation.
Original trace/API/DOM evidence shows the saved SCRIPT/PODCAST document and exact
body were present after reload; the textarea existed, but its implicit enclosing
label included the restored initial text node under the installed Playwright
1.62.1 label algorithm. No lost document or denied Creative request is inferred.

One additive saved-value accessibility contract test failed before adding an
explicit `aria-label` to that product textarea. The original browser assertion,
journey and timeout are unchanged. This local contract does not substitute for a
new SHA's hosted browser acceptance.

## Development evidence (not final-tree aggregate)

- Original-owner slice: 130 focused File tests passed, followed by separately
  sourced UTF-8/escaped-request, actual chapter-identity and ledger-version cases.
- First composed API test: 2 failed / 2 profile skips. The new pure receipt had
  incorrectly treated original `novel:chapter` references as asset filesystem
  identifiers. A chapter-reference-only validator corrected the incompatibility;
  asset/path identifiers remain strict. Original failures are retained.
- Second composed File group: 10 passed / 10 profile skips (23.15 seconds), including
  real original-manager restart and before/after metadata-write faults.
- Third composed group: 16 passed / 16 profile skips (32.52 seconds), including
  phase-B rollback, approved-decision projection failure and genuine observation
  of the original first completed save versus final-marker save.

Final selected-tree results and source identity are recorded below; prior-source
results are retained separately.

## Boundaries retained

The preceding e29 hosted run remains independently classified from this source.
Historical File 20-minute cancellations, incomplete PG/strict joins, and the
observed original PG settling failed call are not converted into passes. Full
strict V2 coverage, Windows interactive/GPU acceptance, real-model adaptation and
quality validation remain distinct. Historical independent security review is
still BLOCKED; implementation-time code review is not that review.

## Additional boundary correction evidence

The first selected eight-module File run completed 419 passed / 300 original
profile skips (255.80 s), before the final passive-route/privacy corrections.
It is preserved as prior-source evidence, not reused as final-tree validation.

A new generic-owner corruption test reproduced three failures: removing private
owner/required flags, or setting a boolean asset version, could still admit an
adaptation-tagged asset through generic reads. The original owner's `_in_scope`
now rejects these damaged new-contract records intrinsically; legacy/Graph
contracts retain their existing rules. Another new test re-created the adapter
with an unchanged durable fingerprint and genuinely reopened JobManager. Both
API mounts incorrectly reported MODEL_UNAVAILABLE because a passive read compared
the old process address. Passive recovery now compares durable route identity
and captures fresh in-call registration, while original dispatch checks remain.

The first combined red run also contained two new fixture mistakes: it read the
intentionally masked public preview instead of the durable original collection.
Those 5-failure logs remain. Correcting only that fixture reproduced 2 actual
route-recovery failures. The same targeted production cases then passed 5 / 5
profile skips. No old wait, assertion or timeout was changed.

The next nine-module File run retained **556 passed / 6 failed / 305 profile
skips** (256.48 s). All six failures were the newly added corruption integration
case's existing rejection-status assertion: intrinsic generic privacy correctly
returned 404, but the already-authorized proposal route had not translated its
unavailable private archive into the original 409 conflict model. A narrow
coordinator translation now preserves generic asset 404 and proposal conflict;
the tests' rejection assertions remain unchanged. This failed run is not counted
as final-source success.

## Opt-in real CPU adaptation attempt records

The original verified official llama.cpp b11429/MIT runtime and Qwen2.5-0.5B
Q4_K_M/Apache-2.0 GGUF are reused, with unchanged pinned model SHA256
`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
No download, private credential, paid API or GPU is used. The owned loopback host
is CPU-only/two threads with an explicit 8192-token adaptation context; the
original Graph harness default remains 2048. Product execution remains 180 s.

Attempt 1 failed before inference: the new acceptance scenario incorrectly read
`version` from the original chapter-create response, which does not expose that
field. The actual subsequent GET response contains saved version 1. The harness
now takes its version from that actual saved GET, with a regression test. Native
host startup succeeded (1.70 s), normal shutdown returned 0, source stayed stable,
and the receipt correctly reports `real_inference: NOT_RUN`. No generated result
or structured/quality success is claimed for that attempt.

Attempt 2 performed **one genuine model inference**: the native host recorded
1,256 input / 78 output tokens, 10.720 s total prompt+generation processing, no
truncation, and normal shutdown. The original Job is COMPLETED with its final
publication marker. The original AssetLibrary contains one exact **241-byte
private DRAFT v1**, SHA256
`7b6f76124f3bfc15b2a7282659e8526a0caab47a3629bb2fd3e5b80ab582e324`.
The actual output is a lone change object, not the required scenes/report object;
the original validator correctly marked the proposal DISCARDED. The original
Creative store contains no screenplay, and its source binding matches the saved
GET. Valid structured adaptation and asset v2 adoption are therefore **not
accepted for this real model**. Quality verification remains NOT_RUN.

The attempt's overall harness receipt remains **FAIL**: after successful raw
archival it incorrectly tried the generic Job's unset actor/scope rather than the
original adaptation binding. A new narrow harness helper uses the typed binding
and verifies it against the authorized proposal; its contract test covers absent
generic fields and mismatches. The original output was then checked **read-only**
against original metadata/bin/Job/Creative files in a separate observation receipt.
No model was rerun to improve the result, no output was repaired, and no failed
receipt was overwritten. Real executor/private-archive evidence is distinct from
the failed structured-quality scenario and from the final mock/contract suite.

The pure receipt/original AssetLibrary extension was developed in a separate
worktree and serially integrated from local commits
`86fe30140aee186b3f794149473b46e3746ec101`,
`029cd87e1288e3b3d73e6121170c59dd32d74e7d`,
`c2ea6ab2b90742ed9beaa45b69eae58f91ff9cd3`,
`750da17123ae901d3a328ab80a4ef9720566eed1`,
`070902d19ae16a908f7c44dda898b4fb61472c2a`, and
`51b91a4a17b57bc607f0ea7e3fddfe5771e29d6e`.
Its original 14 per-slice receipt/log files are retained under
`docs/delivery/v2-development/adaptation-owner-slices/`. These are distinct
source snapshots, not an independent security audit or a combined final pass.
The final integrated source additionally includes the corruption privacy gate
and passive-route/coordinator corrections described above.

## Final candidate layered verification

- Nine selected File modules: **564 passed / 305 original profile skips**,
  246.06 seconds, normal exit 0. Source map has 1,771 inputs and SHA256
  `95bf93cfffd8d77f93bfcf08f5a51d530cb7445a7fd3b119d702390b750cd6a4`.
- Fresh PostgreSQL, same nine modules: **564 passed / 305 original profile skips**,
  566.51 seconds. The original 20 migrations applied to a proven empty database;
  the original process exited 0 and shut down normally at 22:10:49 UTC.
- Complete frontend: **2,442 passed / 8 original skips**, 285 files passed / two
  skipped, 78.63 seconds.
- Original TypeScript/Vite build and 52-file design-token guard: PASS.
- Complete infrastructure suite: **352 passed**, 11.82 seconds. Official
  actionlint 1.7.12 default validation: exit 0.
- Two independent complete collection inventories: **11,901 ordered nodes**
  each, no collection errors, identical ordering. Collection is not execution.
- Real attempt 2 differs from this final candidate only in the new acceptance
  scenario script and its harness regression test; all application/frontend
  production source hashes are identical. The failed original real acceptance
  receipt remains authoritative and is not promoted to a full scenario pass.

## Original e29 hosted CI terminal facts

All five original attempt-1 runs finished naturally before this stage's next
publication. Both Cloud events failed. Push PG0 **3,848 passed / 1,920 skipped**
and PG1 **3,777 passed / 1,988 skipped** are both complete; their observed sum is
7,625 passed / 3,908 skipped, but no official joined coverage proof was produced.
PR PG1 has the same complete 3,777/1,988 result; PR PG0 was cancelled at 55 minutes
with 3,796 passed call phases / 1,898 skipped setup phases, not final test totals.
Both File jobs were cancelled at 20 minutes. All four strict joins correctly
failed their original prerequisite checks. No frozen budget/gate was relaxed.

Creative browser each retains **11 passed / 1 failed**, geometry 8 passed;
independent browser and other bounded suites retain their exact terminal receipts.
No backend failed phase was observed across this e29 run's six execution records;
that does not erase older e6ff/899 failed calls. Legacy frontend each passed
2,439 / 8 original skips; Windows remains bounded package smoke only. Both Interop
runs passed their original File/PostgreSQL 345/68 checks; R123 success is historical
RED reproduction. All eight backend/TCP cache restores HIT and actual installs
and checks still ran; causally improved speed is not claimed.

The compact committed evidence under
`docs/delivery/v2-development/ci-e29-source-adaptation/` retains 29 original job
logs, authoritative terminal/identity/integrity receipts and losslessly compressed
original coverage/JUnit bytes (decompressed SHA256 recorded). All 23 original ZIPs,
43,731,483 bytes, remain preserved in the sole cloud archive and verified GitHub
artifact URLs. Full browser trace packages/Windows executables are not duplicated
inside this compact copy; their artifact/member hashes remain indexed. This
publication is still **FAILED_OBSERVED plus INCOMPLETE_HOSTED_CI**, not all-green.
