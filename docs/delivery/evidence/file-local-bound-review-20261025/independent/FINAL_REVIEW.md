# Independent review: File-local bound manual adoption

Verdict: no remaining reproduced blocker in this bounded slice, against the exact frozen source below. This is not a full-project-green claim.

## Frozen source and execution evidence

- Target: `/workspace/scratch/20a0022d2b33/studio-file-local-bound-review`, base `5eb983fd620ef905aa4dc1afae80b756ee7e7078`; implementation was uncommitted during verification.
- `target-final-freeze.sha256` matches the implementer's final-frozen-input manifest, all 9 source/test entries verified before and after execution.
- Manifest SHA256: `dd2bcb6a0510b618b9106d60bac7b751125c8f783438ed89f558c0605061e459`.
- jobs.py: `dc00af014e93ae1f9c43ecab1d7ff086e3a3c6b43c066447a134e2f0e23705d4`.
- file_generation_review.py: `d8f6fab2379d7f0dbc2d876320514445f4bede2937f21adad39e3a0e92f3bc8b`.
- All app Python hashes stable: `20261025T100946059787929-source-before.sha256` exactly equals its source-after companion. Corresponding source tarball and patch retained.
- Final raw stdout/XML: `final-frozen.stdout`, `final-frozen.xml`. Result: 365 passed, 3 ordinary warnings, 37.07 seconds. Breakdown: 33 independent runtime probes, 33 implementer-focused tests, 299 compatibility tests including 43 offline PostgreSQL protocol tests.
- Exact command printed at beginning of final-frozen.stdout; runner source is run.sh/run.py. Existing main-worktree venv, isolated HOME/XDG/data/tmp, network socket connections denied. No live PostgreSQL, paid provider, real model, install, frontend edit, or push. Reviewer made no production-source edits.

## What was actually established

- Accept/reject for already internally bound, ordinary, local, unscoped File records; original chapter/summary/Canon/generation/memory ports and original owner lease remain in use.
- Independent fixture first runs original legacy JobManager.create('rewrite') through genuine local MockProvider. It then copies the record into a NEW UUID, constructs a synthetic trusted bound COMPLETED record for that new ID, persists and cold-restores it. No existing legacy record is upgraded. No bound writer gate is bypassed. This is real Mock text plus synthetic bound review-layer evidence, NOT an activated bound generate→accept end-to-end flow.
- Accepted rewrite durably updates original chapter, summary, pending Canon and ACCEPTED receipt, then original asynchronous bound MemoryAgentRunner reaches COMPLETED with proposal and evidence. Implementer-focused positive also covers continuation/create.
- Same-ID replacement before review lock, before original chapter save, and between summary/Canon produces no replacement-owner writes. Seams wrap the original port, perform original NovelService deletion/recreation, then invoke the original port with owner kwargs unchanged. No arbitrary atomic_write monkeypatch or impossible hostile-server-code guarantee.
- Participating concurrent deletion waits through chapter, Canon, and terminal-generation seams. Original-owner completion before deletion is allowed; replacement has no adopted chapter/Canon/memory effects. No recall of a lawful prior response is demanded.
- Facade/root/source/Canon/memory rotation is rejected. Mid-review Canon and memory facade rotation after chapter commit blocks later review effects and preserves nonreplayable ACCEPTING/UNCERTAIN state.
- Held review context and cross-thread use are rejected; claimed accept body is single-use. Authorization callback runs outside project/review locks. Runtime events run after locks release. On partial chapter+summary commit followed by Canon failure, CHAPTER/TASK notifications survive and ACCEPTANCE_UNCERTAIN is retained; no rollback is claimed.
- Stale load_all QUEUED snapshot with durable COMPLETED row acquires original project lease before review lock, rereads completed row, and does not write recovery state. Implementer contention probe also passes.
- ACCEPTING and ACCEPTANCE_UNCERTAIN are not replayed after cold restore. Actual Canon I/O failure is tested, not just seeded status.
- Existing HTTP `/api/generation/{id}/accept` and `/reject` both work for eligible preexisting internal bound drafts, with original response shape and no binding disclosure. Do not claim review HTTP is closed.
- Bound writer start/_run/cancel remain closed; existing passive compatibility tests cover retry gates and original unbound retry→Mock→accept. New API bound admission/emitter, bound PostgreSQL review and scoped/branch review remain unsupported. PostgreSQL evidence is recording-session protocol coverage, not live database isolation evidence.

## Assertion correction review

Inspected implementer's preserved expanded.log failures. VersionConflict is the original RuntimeError subclass with expected1/actual2, and authorization refusal is the original normalized _OrdinaryRequestAuthorizationFailed. Independent tests now assert those exact classes plus unchanged whole-root no-write checks. These are appropriate original-contract refusals, not broad exception catches masking a regression.

## Inherited failures explicitly retained

Earlier broader compatibility selection: 288 passed / 3 failed, preserved in compatibility.stdout/XML. Canonical base reproduction: baseline-adaptation.stdout/XML, 5 passed / the exact same 3 failed:

- tests/test_phase7_adaptation_authorization.py::test_team_adaptation_capability_matrix_and_cross_workspace_rejection
- tests/test_phase7_adaptation_authorization.py::test_team_adaptation_audit_is_content_free
- tests/test_phase7_adaptation_authorization.py::test_team_adaptation_materializes_scoped_project_and_is_idempotent

First is 404 versus expected403; the latter two have missing created.id. Canonical command is printed in baseline-adaptation.stdout; REVIEW_TARGET points to unchanged main worktree at the stated base. Fixture/route setup is a provisional hypothesis only; not diagnosed or repaired in this slice. Final green selection intentionally excludes these already reproduced baseline failures and must not replace this disclosure.

## Review history

Pre-freeze legacy NameError from overbroad _review substitutions was independently reproduced and fixed. Same-thread lifecycle replacement risk was identified and fixed with expected-incarnation enforcement at original guard seams plus the common lease. Implementer found and fixed restore lock-order and unsupported-PG sentinel metadata regressions; final tests cover both. Preflight/provisional raw failures and source snapshots remain, including reviewer harness corrections (method name, required internal discriminator field, canonical trailing-newline assertion). None is concealed as final-source behavior.
