# File-bound memory prerequisite for ordinary manual review

Base: `f4ed62a1d2d8c7cce876745d92e0ec95b4b15ec7`.

## Delivered boundary

This is a prerequisite in the **original MemoryAgentRunner and original
GenerationRepository**, not completed ordinary bound acceptance. All original
ordinary accept/reject/cancel/start/retry mutation gates remain closed. No API
admission, emitter capture, bound writer dispatch, branch mutation or PostgreSQL
bound memory execution is enabled. No new queue, owner, registry, table, migration,
legacy record deletion or historical identity backfill is introduced.

A trusted internal caller may supply keyword-only `project_incarnation` to the
existing `enqueue`/`extract` ports. It is server-only identity, not permission.
The only supported new composition is original local File novel/chapter/Lore/
generation owners at the pinned original data root. Repository/service instances,
backend instances and their active paths must still match. A different root or
replacement service facade fails before a receipt, source read or provider call.
Unknown custom ports, PostgreSQL and branch stores are unsupported in this path.
Legacy calls without the keyword retain the original behavior.

## Distinct persisted memory identity

`memory_project_binding` is a strict, disjoint internal discriminator containing
exactly schema version 1, original File project incarnation, project ID, accepted
chapter ID/version and memory job ID. Its canonical UUID5 derives from a distinct
bound-memory domain and the full incarnation/source tuple. The original memory
operation remains `MEMORY_EXTRACTION`; it is not relabeled as Graph or ordinary
writer work. The binding is immutable and preserved on every queued, generating,
completed or failed receipt. Mixed binding/evidence families, malformed versions,
outer identity mismatches and upgrade/downgrade attempts fail closed.

Bound proposal/evidence identities also derive from that memory operation ID.
They cannot inherit legacy effect IDs, or effects from another incarnation.
The original runner verifies explicit payload/provenance fields before reusing
existing bound evidence/proposals. If an earlier attempt created a proposal but
failed while linking evidence, the bound retry repairs/verifies those original
relations before reporting completion. Legacy seeds and retry behavior are unchanged.

File repository reads check original owner and basename identity. Missing markers
are not provisioned. Retained records from a deleted/recreated project are hidden,
not erased. JobManager does not restore a bound independent memory operation as
a writer Job, which would discard the distinct binding. There is no new restart
execution or automatic replay. PostgreSQL explicitly rejects this discriminator;
no URL equality or second database connection is used as ownership proof.

## Lock and callback composition

The original File project lifecycle/owner lease encloses each initial receipt and
source read. Source construction can itself create legacy document/Lore packages,
so it is protected, not treated as a pure read. Before local dispatch the original
runtime guard rechecks identity and store composition. No project lease spans
prompt construction, model inference or the asynchronous thread wait.

After inference, one original owner lease encloses the final source comparison,
all original evidence/proposal/relation mutations and the terminal generation
receipt. Failure receipts also require that original owner. The original
GenerationRepository retains project-before-generation-leaf lock order; no
job-leaf-to-project acquisition is added. Runtime-event publication is deferred
using the existing transaction helper until after the owner lease releases, so
observer callbacks do not run under that project lock.

This lease prevents participating project deletion from slipping between the final
source check and any of the original writes. It does not make multiple files a
transaction, ensure exactly-once inference, coordinate arbitrary direct filesystem
writers, or introduce a source incarnation for a same-project chapter replacement.
Concurrent callers may still perform duplicate model inference, as in the original
runner. Deterministic effects and verified repair are not a new execution queue.

## Why ordinary bound review remains closed

The original `accept` takes a generation-review lock, enters the Job condition,
checks durable status/source/accounting, persists ACCEPTING, then invokes original
chapter create/save, summary write, pending Canon write, ACCEPTED persistence and
memory enqueue. Each chapter/summary/Canon port has its own project guard, but the
complete original review has no common original-incarnation lease. Per-port
existence and version checks do not establish owner continuity between ports.
The original `reject` only changes the generation record but shares legacy review
locking/content checks; it has not been selectively reopened in this slice.

Executable legacy counterexamples replace the real File owner before the review
lock, before chapter creation, and between summary and Canon. These intentionally
show **replacement writes on unbound legacy jobs**. They are not passing safety
claims or a change to legacy policy. Bound gate controls replace the owner after
the initial read and verify zero replacement bytes, zero memory calls and an
unchanged original record. Original MockProvider writer/retry/accept remains a
positive compatibility control in the selected regression.

The new memory prerequisite removes one concrete downstream blocker. A subsequent
review slice still must compose a single original File owner lease across all
synchronous review ports and all error/terminal paths; pin actual chapter, Canon
and memory owners; perform authorization callbacks outside that lease; preserve
original accounting/version/conflict checks; forward the original incarnation to
the memory port; and prove interleavings without review/job lock inversion.
It must not bypass current gates or suppress Canon/memory side effects to claim
completion. Branch and PostgreSQL review remain explicitly unsupported.

## Evidence

See `../delivery/evidence/bound-review-port-blockers-20261025/README.md` for exact
commands, source hashes and raw stdout/XML. Tests import this worktree using the
existing dependency environment, with isolated HOME/XDG/data/tmp and blocked
network sockets. MockProvider is synthetic; no paid provider, real local model,
live PostgreSQL, installation, frontend change or push was performed.
