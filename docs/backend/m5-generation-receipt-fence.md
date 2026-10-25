# M5 original generation receipt final boundary

Base: `e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459`. This is a minimal correction to
existing manual-review and bound-memory receipts, not generation admission.

## Reproduced inherited gap

A wrapper around the original GenerationRepository `_graph_owner` entered the
original owner lease, synchronously deleted/recreated the project through the
original lifecycle service, then yielded. The reentrant lock allowed this. The
original global job row could be overwritten with ACCEPTING, ACCEPTED, REJECTED
or memory COMPLETED before a later outer check refused. Replacement project
bytes stayed unchanged, so checking those bytes alone missed receipt corruption.
The retained red tests assert both the original job-row bytes and replacement
project bytes. Manual inputs are synthetic trusted persisted v1 completed drafts;
memory uses the existing real Mock adapter/runtime chain. They do not bypass
closed writer/API admission to claim end-to-end bound generation.

## Narrow correction

Only GenerationRepository production code changes. Opted-in `_expected_root`
manual saves and `_file_memory` receipts retain the original leaf-lock root and
recheck immediately before the original atomic write, after payload serialization.
Root rotation fails before any different-root owner lock can be acquired. Manual
review reuses the existing project lifecycle seam with the original binding's
incarnation and fixed root. Bound memory reuses its strict expected-port check,
which checks original composition and the physical marker. No authorization
callback, schema, queue, capability or API parameter is added.

Original no-expectation legacy/specialized saves keep their prior semantics. The
new final check is a no-op for them. Existing manual uncertain-acceptance,
independent memory failure and no-replay semantics remain unchanged. This is not
multi-file rollback, a hostile filesystem defense or exactly-once inference.
New API capture, bound writer/start/retry/cancel and unsupported PG/scoped mutation
remain closed. No M6 activation code is included.

## Evidence

See `docs/delivery/evidence/m5-generation-receipt-fence-20261025/` for the red
source, raw stdout/XML, frozen hashes, exact commands and independent review.
