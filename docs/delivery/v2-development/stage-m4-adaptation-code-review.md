# Source-aware adaptation: same-round engineering review

Date: 2026-10-10 UTC

## Result

The two concrete findings from the initial review are addressed in the current
`app/creative/adaptation_generation.py`. No remaining blocking defect was found
in the inspected fixes. This is a scoped engineering review, not an independent
security audit or a release certification. The historical independent audit
remains **BLOCKED**. TEXT-13 remains **PARTIAL** because AssetLibrary archival is
not implemented in this slice.

## Scope and verification limits

Read AGENTS.md, the new adaptation service/models/coordinator, their tests, and
the current changes to Creative routes/store/composition, JobManager, generation
repositories, generic generation routes and Broker job projection. Followed the
original author, model, broker, storage and terminal-publication contracts where
needed. The reviewer did not modify source code or run tests, builds or scans.
Only this review file was written outside the checkout.

The implementing parent reported deterministic reproduction before the fixes:
four terminal-publication failures across two API aliases and two persistence
boundaries, plus two admission-cancellation failures. It reported all six passing
after the fixes. These are parent-reported results, not independently executed
verification by this reviewer; broader verification was still running.

## Findings and resolution

### P1: Adoption before terminal publication completed

Previously, refresh and review trusted live `COMPLETED` and a completed terminal
hook while the worker was still persisting either its settlement receipt or its
final notification. A later write failure could invalidate output after a
screenplay had already been adopted.

The fix uses strictly nonblocking acquisition of the original Job condition and
checks the exact durable terminal fields. The worker holds that condition across
both persistence boundaries and their failure handling. A busy condition cannot
therefore expose the intermediate completion state. The second validation within
the Creative transaction returns unchanged pending state before `change_row`,
preserving both the output boundary and the finite history budget. Nonblocking
acquisition avoids waiting for a worker that needs the held scope transaction.

### P2: Cancellation stranded an undispatched reservation

Previously, cancellation after reserve committed but before its ID reached the
proposal left a RESERVED ledger, no registered Job and no proposal reservation
pointer.

The fix retains the known reservation pointer and permits cleanup only when this
fresh Job is absent from the original manager and the ledger matches its actor
and job ID and is undispatched. This dispatch is the sole starter of that Job;
the manager removes it after a pre-launch persistence failure, before any worker
starts. Cleanup calls the existing Broker finalizer under the captured project
incarnation lease. Unknown reserve outcomes and registered Jobs do not enter the
release path. Finalization failure preserves the recovery pointer and does not
permit inference replay.

## Remaining boundaries

- No automatic replay or replacement executor was introduced by these fixes.
- Source and project authority, live callback authority, and durable terminal
  agreement remain required before adoption.
- Model output quality and real-model inference are outside this review.
- AssetLibrary archival and restart recovery remain follow-on work through the
  original tagged asset owner, without fabricated Graph provenance.

## Additional captured-Host boundary (2026-10-10 20:39 UTC)

The initial repeated token-validity check did not capture the registry binding
 epoch. Same-token revoke/re-registration therefore revived an older callback.
Six deterministic new mounted API cases reproduced the gap before correction:
same-session ABA, replacement session, and rotation after Author preparation,
across both route aliases. The first two incorrectly completed; the preparation
case incorrectly admitted a job. Original red JUnit/log/source receipts are
`stage-m4-adaptation-host-aba-red.*`.

The correction reuses Graph's original `resolve_discovery_authority` through the
same composition callback: capture its nonempty principal and retain its guard
in the new adaptation operation/worker closures. Local actor ownership and
Director behavior are unchanged. This also inherits Origin/direct-loopback and
nonpackaged-collaboration rejection; fixtures must not bypass those boundaries.
The new branch-owner test separately verifies private actor/scope data access
and HTTP Host denial, without claiming packaged collaboration inference.

This remains ordinary same-round code verification. It does not close the
historical independent security-review BLOCKED item.
