# Passive ordinary JobManager binding and read fencing

Base: `07d525a6220893109975ea984eaefc060dd61aac`.

The earlier [repository foundation](ordinary-project-binding-foundation.md) is
kept byte-identical as a historical delivery document. Its statement that manager
serialization/read fencing was still future work describes that earlier base;
this document records the subsequent manager layer, without retroactively
changing the earlier evidence or its remaining activation limitations.

This is the next passive layer over the original GenerationRepository contract.
It does **not** enable ordinary API admission/capture, retry, acceptance, restored
execution, a second owner, migrations, or historical binding backfill. Ordinary
new jobs remain unbound. Client payloads do not populate this internal field.

## Private records and restore

`Job.record()` is the separate internal persistence projection used by the
original manager `_persist`. Bound records carry the strict
`ordinary_project_binding` object and all required explicit nullable identity
fields. `Job.public()` and the existing HTTP response fields are unchanged.
An absent internal binding is legacy; explicit null or a malformed value is not.
The original repository retains its existing immutable binding/save validation.

Restore validates the original strict record, original repository read, and
source-store composition before changing interrupted state. It preserves passive
identity, not `request_authorization`, execution capabilities, dispatch hooks or
stored callbacks. A fresh transient read verifier calls the same original
repository; it is neither serialized nor execution authorization. Interrupted
jobs use the existing durable failed/reconciliation transition and never dispatch.

## Cached readers

Bound `get`, content availability, variants, SSE and diff require a valid durable
record from the pinned original GenerationRepository. Missing/corrupt rows,
removed/null/changed binding fields, invalid outer identities, missing owner
markers and same-ID replacement project incarnations fail closed. A cache is
never a missing-record fallback. Read failure does not delete retained records.
The original TaskCenter author reader already calls manager/content checks, so it
inherits these fences without another task store or projection authority.

The verifier calls the pinned repository directly, not a replaceable service
facade's `get`. Repository object and original File root / PostgreSQL Database
identity are pinned. Mainline ChapterRepository must use that File root or the
exact PostgreSQL Database instance. File branch reads additionally require the
registered original BranchManuscriptService, same-root ExperimentalStore and
novel owner, and the original mainline service. Unknown or mismatched composition
is unavailable. PostgreSQL bound branch reads are intentionally unavailable:
its registered ExperimentalStore owns a URL/independent connection rather than
that Database object. URL equality is not accepted as proof of composition.
Legacy branch behavior is unchanged.

A diff rechecks after source resolution. SSE checks the original owner before
reading and immediately before emitting each event, including after resumption.
Bound SSE never reads the repository under `job.condition`; no database session
or project lease spans a condition wait, external observer callback, or yield.
Variants snapshot under the manager lock and verify after releasing it. These are
point-in-time read fences, not a transaction held across delivery to a client.

## Mutations deliberately unavailable

Bound accept/reject/cancel, reviewed-variant staging, start and direct worker /
acceptance/cancellation entries refuse with HTTP 409:
`GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED`.
The guard runs before ACCEPTING, cancellation signals, review receipt/cache
changes, dispatch, callbacks or source/accounting/Canon/memory writes. Bound
retry cannot fall through to a new unbound generation. The only API change is
one eligibility call in the original retry path. Existing collaboration and
feature-origin `AUTHOR_PREVIEW_REQUIRED` precedence is retained.

This is an explicit unsupported eligibility outcome, not a successful
implementation of bound review or retry. Plain legacy jobs retain their original
read, no-callback generation, retry and review behavior. Graph, adaptation,
director, image and OCR branches keep their existing serializers and guards.

`_persist` remains the trusted private passive-record save path; it uses the
original repository's final write lease/transaction and introduces no nested
owner connection. Composition checks inspect metadata only. No full execution
source/authority check or chapter incarnation contract is implied.

## Still required before activation

Trusted admission must capture original identity, compose all execution/source
ports, and retain live request authorization. Mutation ports need a final original
owner fence in their existing transaction/lease, not a read-then-write owner check
or a second PostgreSQL connection. Canon, memory, context/accounting and other
write-port composition has not been implemented here because bound execution and
mutations remain unavailable. Chapter-source incarnation/row reconciliation and
historical unbound policy remain separate work. No historical IDs are guessed.

## Verification

Real File owners, same-ID replacement projects/chapters, cold managers, mounted
original generation endpoints, original TaskCenter reader and genuine
MockProvider execution test the implemented boundary. PostgreSQL coverage is
**OFFLINE PROTOCOL ONLY**, using original repository/ORM code and recording
sessions, not real transactions, isolation, constraints or concurrency.
Live PostgreSQL and external model/network calls: **NOT_RUN**.

See [portable evidence](../delivery/evidence/passive-manager-fences-20261025/README.md)
for exact commands, frozen hashes, stdout/XML and measured results. Tests use the
existing dependency environment with worktree cwd/PYTHONPATH/PROJECT_ROOT,
isolated HOME/XDG/data/tmp and blocked sockets. No runtime data is delivered.
