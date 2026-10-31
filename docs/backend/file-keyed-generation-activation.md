# Experimental opt-in keyed File-local writer activation

Original activation base: local reviewed composition `e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459`.
Integration base: canonical M5 `18c8744b4c2f208cbfe5607ad1d672b7dcb8e58c`,
including the final v1 manual/memory receipt fences. The integration retains
those original root, leaf and physical-owner checks alongside the new writer
source/state checks; admission scope is unchanged.
This document supplements, rather than changes, the historical passive manager,
File manual review and corrective memory reports. Those earlier tests did not
establish a generated bound candidate.

## Default-off experimental admission

`ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION` defaults to `false`, following the
existing Settings/environment feature mechanism. No live setting is changed by
this implementation. Without explicit opt-in, existing LOCAL_ONLY keyed requests
retain their original unbound generation, cancel and retry behavior. This is an
implemented opt-in vertical slice, not default-wide security activation.

The switch is read only for NEW admission. Turning it off does not strip existing
bindings, weaken their final-port checks, upgrade old records, or restore any
execution capability. Already captured admissions keep their pinned contract.
Opt-in bound cancel/retry remain unsupported (409); users requiring those
operations must keep the experimental switch off for new requests.

## Deliberately bounded admission

Only a NEW keyed ordinary `continue` or `rewrite` request can enter this slice.
It requires non-collaboration, unscoped File mode, `LOCAL_ONLY`, no selected or
explicit source, no creation-workbench records, and narrative context disabled.
The actual original API and manager Chapter/Novel/Generation/Context/Lore/Canon/
Memory owners must compose at the captured original File root.

The supported route families are the registered original `LocalTextAdapter`
with its existing verified-local external OLLAMA/LLAMA_CPP bridge evidence, and
the actual development Mock adapter under the existing Mock/non-packaged flags.
A provider label or loopback URL alone is not locality proof. Recognized legacy
adapter families remain outside this activation. Missing/invalid registration,
or changed original adapter/model/node/bridge after classification, refuses;
there is no eligible-request fallback to an unbound task or alternate model.
Real external/local model execution is not established by Mock evidence.

No-key requests, variants, other operations, PostgreSQL, branch/collaboration,
preview/character/selection, specialized origins, accounting hooks and narrative
context are not activated. Their original contracts remain separate. Bound retry,
cancel and staged variants stay closed, including for newly generated candidates.

## Admission and identity

The existing idempotency coordinator and namespace are retained. The original
capture authority supplies the project incarnation. Trusted private preparation
checks final source ports, prepares the exact Job, attaches its private binding,
then durably records RESERVED. Live revalidation precedes starting that exact
instance. Its first Job save is already bound QUEUED and completes before the
worker thread starts. The existing full-v2 response receipt and HTTP response
shape are unchanged.

Old full-v2 unbound records are returned as their original receipts, not upgraded.
RESERVED replay remains unconfirmed and does not redispatch. Owner replacement,
expiry and request conflicts retain their original refusal behavior. No new
queue, owner marker, table, alternate idempotency key or recovery dispatcher is
introduced.

The additive private binding schema v2 preserves the original identity fields
and includes the exact base chapter version and digest. Its required private
record projection is strict. Version1 remains the exact passive contract;
unknown versions and v1/v2 upgrades or downgrades are rejected. Public Job fields
are unchanged. Restored interrupted rows fail/reconcile without execution, while
an eligible restored completed candidate can use existing manual review.

## Live execution and final ports

A single-use transient capability pins the exact manager, Job, authorization
closure, original route/model/adapter/node and original source/store objects.
Start and the issued worker thread claim it separately. Binding data, passive
read verification, a copied Job or a restored closure cannot grant execution.
The exact original worker and durable GENERATING row are required at final
adapter dispatch. Model execution and streaming waits hold no project lease.

Writer-owned immutable port expectations reach actual original File source,
ContextService, Lore and snapshot guards. They do not counterfeit a memory
binding. Original lifecycle leases fence lazy chapter/ledger/Lore initialization;
source version/digest and original object/root identities are rechecked at
context, final dispatch, snapshot and publication. After source capture, missing
chapter packages or identity ledgers cannot be silently recreated. Narrative's
separate owner is deliberately excluded. Continue/rewrite's deferred snapshot is
preserved rather than disabled.

Job writes follow owner → review lock → condition, inside existing event buffering.
The original final generation write also rechecks expectations after nested owner/leaf
entry and immediately before changing retained Job bytes; v2 manual and original
bound-memory receipts share this final protection using their own expectations.
Authorization callbacks and observer delivery run outside those locks. Durable
state is reread so a cold recovery receipt cannot be overwritten by a late
worker. Partial actual effects are notified after lease release even when an
operation raises; this is not multi-file rollback. Observed model completion and
usage facts are kept distinct from permission to publish its draft.

Existing manual adoption still claims ACCEPTING before manuscript effects, then
writes the original chapter/history, summary, pending Canon, ACCEPTED and bound
memory enqueue. New v2 candidates also require the immutable original source
digest, including on cold adoption and at the original final chapter save. A
separate owner-only expected-port projection allows that source-changing write
to finish without pretending the new manuscript still equals the old base.
It grants no writer execution authority. Existing uncertain-adoption semantics
remain unchanged.

## Evidence boundary

The activation suite uses mounted original HTTP endpoints, original File stores,
actual Mock adapter streaming and actual existing manual adoption plus bound
memory effects. It does not seed a synthetic completed row for the positive
vertical result. Older synthetic manual review tests remain compatibility tests.
Independent adversarial review and frozen regression evidence are recorded in the
[opt-in delivery report](../delivery/evidence/file-keyed-optin-20261025/README.md). Live PostgreSQL, real model calls, Windows and frontend
work are NOT_RUN. No public upload is part of this local implementation.
