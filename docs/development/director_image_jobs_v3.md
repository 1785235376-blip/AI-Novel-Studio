# Director IMAGE V3: unmounted Job / Broker / pending-review slice

Baseline: isolated checkpoint `c8e18e00c9595ecf3af3e328bee797aaf9d5b292`.
This extends the reviewed local vision runtime. It is an internal host seam, not
an executable public Director API or UI. No real model inference was performed.

## Existing owners and prerequisites

The target is an existing `CreativeService` DIRECTOR DRAFT and an existing,
human-selected scene. `CreativeMode` already supports DIRECTOR. Its existing
Graph `director_plan` node reads the same document. An independent draft is
valid; no screenplay, chapter, synthetic scene or new document mode is invented.

`DirectorImageCoordinator.preview` captures the original bounded Asset and exact
target version/digest/scene. The original `creative_director_proposals_v2`
collection holds V3 proposal/pending records under its existing incarnation and
quota rules. Legacy proposal access rejects V3 records rather than treating an
Asset as a screenplay/storyboard source. Original `JobManager` owns preparation,
queue/thread, status, terminal hook and persistence. Broker uses its original
preview decisions, reservation ledger and project budgets. Original generation
repositories own terminal output and V3 terminal history.

## Separate versioned identities

- `CREATIVE_DIRECTOR_IMAGE_REQUEST_V3`
- Job operation `creative_director_image_v3`, origin `creative_director_image_model_v3`
- `DIRECTOR_IMAGE_PROPOSAL_V3`
- `DIRECTOR_IMAGE_ADVICE_V3`
- `DIRECTOR_IMAGE_TERMINAL_V3`
- `DIRECTOR_IMAGE_PENDING_V3`

V1/V2 text binding schemas, text terminal envelopes and their discriminators are
unchanged. Generic author/text dispatch and acceptance cannot execute IMAGE
records. Persisted evidence never reconstructs either execution or Broker
capability. Private capability identity pins manager/repository, Host guard,
request, provider instance, registry route, cancellation event and dispatch hooks.

## Byte handling and authority

The foundation remains the only source reader: exact PNG/JPEG Asset pins,
transient bounded bytes, real decoder, private-candidate rejection and no
persisted image/base64/remote locator. The queued job retains no image bytes.
Execution reopens the source, releases leases before I/O, and uses the reviewed
vision runtime's cancellable bounded transport.

Source and target checks run at admission, reservation/dispatch, transport
checkpoints, publication and pending preparation. Original ordering is raw scope
then Asset then project, with context-local evidence of that held owner phase.
Terminal publication rechecks under those leases and saves through the original
File/PostgreSQL generation repository. Its semantics are explicitly authority
and bounds sampled before commit, not a power-loss durability guarantee.

## Accounting and recovery

Unknown price remains unknown. The original default known-estimate budget blocks
dispatch. A trusted caller must explicitly configure the original budget policy
before unpriced work can be admitted. No fee estimate, usage, invoice or hardware
measurement is invented. Before possible dispatch, cancellation releases the
original reservation. After possible dispatch, finalization preserves
`UNKNOWN_UPSTREAM` with `actual_microusd=null`, even for a successful response.

This slice does not add a trusted IMAGE accounting-reconciliation action. Generic
reconciliation cannot claim an IMAGE bill. Consequently an unresolved hold can
block later work under the original budget rules; resolving it remains a future
original-owner reconciliation change, not a direct ledger edit or automatic retry.

Interrupted jobs become passive failed/reconciliation-required records. Existing
reservations remain conservative. Completed exact durable terminal evidence may
be reopened with fresh Host/source/target authority to prepare pending review.
A lost terminal write acknowledgement marks the live result UNKNOWN without
rewriting potentially committed history. Re-dispatch of that proposal is denied.
No automatic replay or upstream-stop guarantee is claimed.

## Pending review and provenance

Strict bounded advice distinguishes uncertain model observations from hypothetical
directing suggestions. These are not measured geometry or verified visual facts.
Pending records retain exact server-captured Asset/source, target draft/scene,
terminal digest and original accounting state. Both pending and direct adoption
entrypoints report `DIRECTOR_IMAGE_ADOPTION_NOT_INTEGRATED`.

No document mutation/adoption is implemented. A future authorized adoption must
use `CreativeService.revise_in_state` and append a server-derived proof to its
existing proof/history mechanism, with the exact pending source, target,
terminal and reviewed advice identities. Client-provided provenance is never a
substitute. That future revision must preserve unrelated authored draft content.

## Verification scope

`tests/test_director_image_jobs_additive.py` uses original Asset/document/Job/
Broker/repository owners and injected HTTP transport only. Its shared original
fixture parametrizes File and PostgreSQL. This worker executes File cases only;
PostgreSQL cases are explicitly deselected for root integration verification.
Coverage includes conservative accounting, passive restart, missing execution
capabilities, generic route rejection, source/target changes, cancellation,
forged terminal records, lost acknowledgements, and retry denial.
