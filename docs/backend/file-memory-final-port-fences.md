# Corrective File memory final-port composition

Base: local manual-review snapshot `05682a860fbeb15d108ce6c518cd76c8ce5e9e18`,
which remains preserved unchanged. This correction must be composed before that
manual-review slice is published or treated as complete downstream protection.

## Confirmed defect, not a hypothetical limit

The earlier published memory prerequisite `5eb983f` protected tested cross-thread
owner deletion, but its entry-only `_bound_owner` check was insufficient at final
Lore ports. An independent supplemental review reproduced six counterexamples on
byte-identical published source:

- Same-thread original NovelService delete/recreate inside an evidence or proposal
  service/repository wrapper wrote evidence/proposals into the replacement owner
  before the generation terminal fence eventually refused.
- Replacing the original Lore repository/backend with another same-root instance
  bypassed the claimed original-object pins.
- Rotating the Lore facade to another valid File root wrote a complete
  evidence/proposal/relation set there while the original bound operation reported
  COMPLETED against the untouched original project.

Those six passing counterexample assertions mean **defects reproduced**, not safety
checks passed. Their raw report, exact published source hashes and stdout/XML are
retained separately. The prior narrow PASS did not establish these boundaries;
this correction does not retroactively claim otherwise. Manual-review publication
was held while repairing and independently reviewing this dependency.

## Corrective behavior

The original MemoryAgentRunner now carries private, frozen expected-port data
through each bound operation. It contains the existing original instance pins,
root and immutable project-incarnation/source binding. It is transient data,
not an authorization callback, persisted field, owner registry, execution grant,
queue, table or new binding schema.

The original LoreService and FileLoreRepository evidence/proposal/relation ports
receive that data explicitly. Final original guards validate the actual original
service/repository/backend/root and physical owner beneath the original project
lifecycle lock. Expectations survive a scheduling wrapper that performs a real
reentrant delete/recreate or swaps a facade before invoking the unchanged original
method. Source getters, existing evidence/proposal/relation reuse, snapshot reads
(which may create legacy directories) and original generation queued/generating/
terminal/error receipt ports receive the same expectations.

Each final boundary revalidates original pins, including same-root instance
identity. It cannot silently follow a rotated Lore facade. PostgreSQL remains
unsupported for the opt-in bound memory path. The existing outer owner lease still
spans final source comparison and all final writes; final checks complement that
lease, not replace it with read-then-write checks. Inference and queued waits remain
outside the lease. No caller-supplied callable is executed as an ownership check.

The existing GenerationService/GenerationRepository retains the strict persisted
memory binding and original leaf-lock ordering; expectation data is a separate
private Python argument, never serialized or accepted from API input. The
previous manual-review expected-root/incarnation guard is reused for original
File source ports. Original unbound callers omit the private argument and retain
their existing interface behavior and deterministic identities.

## Bound retry and failure semantics

The original bound-only retry logic still verifies existing evidence/proposal
payloads/provenance and repairs missing original relations. The new final guards
also cover those retry reads/writes, not only first creation. Partial files can
remain under the original owner after I/O failure; this is not multi-file rollback
or arbitrary crash recovery. A changed owner/port cannot receive a late FAILED or
COMPLETED receipt, and refusal does not erase retained historical records.

No broad manual or writer activation is added in this corrective slice. The
previous manual-review implementation is retested in composition, with its narrow
existing internal-record accept/reject scope. New API binding capture, bound
writer start/dispatch/retry/cancel and scoped/branch/PostgreSQL review remain closed.
Legacy delayed-adoption counterexamples intentionally remain legacy behavior,
not newly interpreted historical bindings.

## Verification limits

New tests wrap legitimate original source/service/repository ports, perform
original lifecycle operations or actual File port rotations, and forward every
new private keyword unchanged. A wrapper TypeError is not counted as safety.
Scheduling wrappers in the prior bound tests were adjusted only to accept/forward
that new argument; their original race, failure and output assertions remain.

The repaired suite uses genuine File owners and the real MemoryAgentRunner local
runtime/adapter chain with fixed synthetic Mock JSON. Manual-review tests remain
synthetic trusted internal COMPLETED drafts, not activated bound generation E2E.
No live PostgreSQL, paid provider, real model, service install or frontend change.
See `../delivery/evidence/memory-final-port-fences-20261025/README.md` for exact
commands, raw counterexamples and final results, frozen hashes and independent
review. This is protection of cooperating original ports, not hostile arbitrary
filesystem writes or server monkeypatches below the original mutation boundary.
