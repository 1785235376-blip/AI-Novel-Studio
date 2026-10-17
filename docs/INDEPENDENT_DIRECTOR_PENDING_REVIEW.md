# Independent Director private durable pending review

Status: primary and independent scoped verification passed. This is not public
activation or full product/release acceptance.

## Bounded behavior

An explicit private `_prepare_independent_pending_review` action takes the
current proposal version and exact terminal-evidence digest. Fresh current Host
and actor/scope authority authorizes review of a historical finished artifact.
It does not restore, serialize, extend or invoke execution authority. The old
live result/candidate/review methods and execution deadlines are unchanged.

The historical checkpoint must precede its original generation deadline. The
new prepare action may occur after that deadline or after service restart. A
fresh valid Host session is required, but its ephemeral principal is deliberately
not compared with the historical preview's principal. Stable actor, complete
scope, project incarnation, source and execution identity remain exact.

Preparation requires the original retained completed Job output to match its
write-once historical digest and UTF-8 length, its exact request/preview/schema/
parameters/route/bounds and original zero-settled ledger. The current source,
route, local verification, license, zero-price and budget policy are checked
again. Default free-text output remains ineligible, even if it resembles JSON.
The original strict storyboard parser validates scene evidence and exact authored
shot association. No semantic or geometric correctness is implied.

## Original owners and atomicity

Parsed notes are published into the existing proposal's `director_notes` and
`output_digest`, together with one private pending receipt and whitelisted
provenance. There is one original proposal version/history transition to
`INTERNAL_MODEL_PENDING_REVIEW`. Original preview/execution fields retain their
historical meaning. No raw-output duplicate, new candidate store, scheduler,
engine, model request, reservation, settlement or automatic replay is created.

Lock order is the original generation-accept coordinator, optional existing Job
condition, raw scope, original project owner, then generation-write leaf. The
outer ExitStack retains owner and leaf through the inner raw transaction's
atomic replacement. Every authority/source/policy/parsing/capacity callback
finishes before leaf entry. Under the leaf, the exact detached durable snapshot
is compared; no authority callback is acquired. Existing File coordinator
flock/RLock waits remain blocking, so no global operation-timeout guarantee is
claimed. The existing Job-condition wait has an operational bound independent
of the expired execution deadline.

Current authority is sampled at the last checked precommit boundary, not
asserted to be synchronized with physical replacement. Original source/project
leases and the generation leaf protect participating File owners. Hostile
filesystem modification and power-loss durability are not claimed.

If output clearing wins before publication, prepare fails. If pending publication
wins, subsequent Job-output clearing does not erase the original proposal's
parsed candidates. Exceptions before replacement roll back the scope. Exceptions
after replacement or during lock unwind return uncertainty, without destructive
cleanup or an automatic write retry. A repeated explicit prepare first reads and
validates the exact original pending identity; a matching already-committed
publication is returned without another mutation. A conflicting version or
terminal digest does not replace pending candidates.

## Read, human review and reopen

Private pending reads revalidate strict saved candidate schema, associations,
candidate digest, whitelisted provenance, historical identity/accounting and
fresh current authority/source/policy. They do not require the original raw
output or old execution capability to remain available. The immutable terminal
envelope must still be present in the original Job record; no new retention or
reconstruction policy is introduced.

Private human review consumes the existing DirectorProposalReview, rechecks the
exact proposal version and reviewed candidate digest, and invokes the original
`_adopt_review_locked` owner. Human-edited notes retain original shot identity and
order. The original atomic transaction creates a separate DIRECTOR DRAFT with
real storyboard ancestry and reviewer/provenance evidence, and approves the
original proposal. Original document reopening remains the persistence path.
The old admitted-version execution guard is never invoked after promotion or
approval intentionally advances that version.

## Public isolation and compatibility

The new pending field's presence, including null, malformed data and historical
snapshots, independently marks a proposal private. Public projections strip the
pending field and private provenance, notes and model fields before copying.
Private CAS failures contain only current version/status. Public preview,
dispatch, refresh, review, cancel and generic generation-content paths remain
closed. There is no new public endpoint or advertised capability.

Runtime changes are confined to the original Director coordinator/proposal/
binding/evidence helper and original File generation repository. Existing tests,
golden fixtures, default request contract and PUBLIC manifest are unchanged.

## Verification and limits

New tests are in `tests/test_director_durable_pending_review.py` and
`tests/test_director_pending_file_races.py`. They cover exact identity and output,
restart/fresh Host/expiry, output clearing, current-authority invalidation,
proposal CAS and concurrent review, public marker/history isolation, final
callbacks, File leaf/commit order, uncertain replacement/unwind and real separate
File writers. Both files passed together: **99 tests, zero skips**. Original backend regression
coverage passed **536 tests**, with **120 PostgreSQL-marked cases deselected**.
The actual offline PUBLIC artifact/profile gate passed **87 tests**; two wheels
and two sdists were built and every receipt-listed source payload hash-matched.
The six original Director/Graph UI suites passed **100 tests**. Forced TypeScript,
production Vite, the 52-file UI token guard and before/after natural/original-runner
origin checks passed. All **2,611** runner-tracked source hashes match all nine
primary receipts and current files. No primary failure or repair rerun occurred.
Independent verification reran the same **99 new/process-race tests** and
**536 original regressions**, with **120 PostgreSQL-marked deselections** and
zero skips. These overlap primary tests and are not additional unique coverage.
Its own natural/original-runner origin proofs and actual four-archive audit
passed; all **2,611** source hashes match primary, independent and current files.
See [complete report and evidence](delivery/v2-development/director-pending-20261017/report.md).

This is private File protocol/state-machine work. Public activation, live-model
quality, PostgreSQL, actual browser/canvas placement, geometry, native Windows,
installed-package execution and complete script-to-canvas product acceptance
remain outside this slice. No provider, network, paid resource, install, push,
merge, tag or release is part of this implementation.
