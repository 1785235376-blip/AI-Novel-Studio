# File/local semantic-import cursor: stable-slice implementation

This is a bounded backend slice, not completion of the full lifecycle programme.
It extends fixed commit `63636958e48ad12f6416194272781c9e3bf8ae71` (tree
`31eb13e7d781b68fdeecb8b53e84d1865cde4381`). The previous M0 executor-blocked
checkpoint remains a historical report; it is not rewritten as a successful run.

## Supported mode

The original HTTP authorizer and semantic-import reader still run. Cursor mode
requires explicit `authority=semantic_import`, actual matching File repository
owners, non-packaged/non-collaboration local-author mode, no session or branch
header, an existing valid original project marker, and a source document whose
original owner committed its project binding. No query creates a marker,
initializes a document, migrates history, changes permissions or executes jobs.

The original ExperimentalStore maintains reserved metadata inside its existing
atomic scope-file commit. Only the first actual write to a physically missing
scope document can establish a binding, and only when the existing original
marker was available at transaction start and is revalidated under the original
scope-to-project lock order through commit. Existing unbound documents stay
unbound even after ordinary business writes. No same-slug ownership assumption
or automatic migration is made.

Original participating writes maintain random lifecycle nonces for live
semantic-import rows. Changed rows and recreated IDs receive fresh nonces;
deleted IDs are removed, avoiding an unbounded tombstone registry. A static
scope-document incarnation distinguishes physically recreated documents. Exact
physical-byte/existence CAS before every File transaction exit, including
no-op leases, prevents reentrant cross-instance stale overwrites. The old
same-instance nested-write refusal is unchanged. PostgreSQL is not enabled for
cursor mode and its transaction branch is not changed.

Cross-instance CAS rejects the stale outer transaction; it does not roll back a
separately committed inner transaction. A source lease detects that conflict
instead of silently claiming the source stayed unchanged. This is not a new
multi-transaction rollback coordinator.

## Precise consistency boundary

The guarantee is **observed authorized row lifecycles plus the current bounded
safe projection**, not every intermediate membership event in collection history.
The adapter compares pure committed observations around the real reader and
again after cursor-engine work. It retains the original first-200 reader window,
scope fence, filters, safe projection, truncation and coverage semantics. Only
matching visible rows' lifecycle evidence is bound. Unselected collections and
unobserved tail-row content do not contribute lifecycle invalidation.

A previously observed row's persistent A→B→A or deletion/recreation is detected.
A new row which was absent from the signed observation, is inserted and then
removed entirely between observations, may leave the same current projection
and observed-row evidence and therefore not invalidate the cursor. This is an
explicit limitation, not complete collection-membership ABA protection. Adding
a whole-collection epoch to mask this limitation would leak unrelated activity
and is deliberately not done.

The final original authorization, actual-owner and source checks establish a
last checked observation boundary. They are not a cross-owner transaction and
cannot prevent a mutation after the final check. The cursor is process-local
metadata, not an authorization token or cached business result. Expiry, eviction,
worker changes and changed bindings require an explicit restart; no automatic
retry or offset fallback is introduced.

This is not database pagination or a cheaper source query. The original File
reader and each committed capture parse the whole scope document; the adapter
currently uses three captures around one real aggregate read. The 200-row bound
limits the safe observation window, not the size or I/O cost of the underlying
scope document. No latency or full-history performance improvement is claimed.

## Preserved behavior and refusals

Legacy offset behavior, including old same-slug scope rows, is preserved. This
slice does not reassign or erase that legacy history. A project deletion and
same-ID recreation therefore makes the protected old cursor fail and refuses a
new first cursor page over the old source binding, without claiming to repair
all legacy offset reads or writes.

Unproven first-page modes return 501. Invalid new query/token shape returns a
fixed 422; changed supported continuation evidence returns a fixed 409. Original
authorization refusals retain their status and payload. Exact TaskCenter GET
opt-ins receive no-store even when the original loopback/session middleware
rejects before routing. Other endpoints and legacy requests retain their cache
contract. New opt-in validation errors do not echo input.

## Explicit exclusions

No frontend, SDK, audio owner, execution state machine, generation/adoption
chain, dependency lock, schema migration, PUBLIC surface, real provider call or
paid service was changed. Collaboration, packaged sessions, other authorities,
PostgreSQL, Windows, full history, general migration and arbitrary administrative
backup-replay protection remain unsupported or unverified. A byte-for-byte
administrator rollback of both metadata and owner marker is not distinguishable
without an external trusted history anchor and is not claimed.

POSIX SIGKILL tests at the existing atomic-write replace boundary test process
failure only. They are not power-loss or filesystem durability proofs; the
original atomic writer still does not fsync the parent directory.

## Verification

Execution uses an isolated native cloud checkout and synthetic File data, with
memory credentials and mock providers. The original verification groups and
new owner/HTTP/process probes must be reported separately because groups can
overlap. Exact final commit/tree, commands, raw logs and final results accompany
the delivery; interim passing runs are not a frozen-tree attestation.
