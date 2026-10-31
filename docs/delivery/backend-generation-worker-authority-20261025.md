# Backend generation: live ordinary-worker authority and publication

Date: 2026-10-25. Base: `e9830fc4c24fe8b0b08f2fbba03d3f4dbf35a86e`.
Scope: consume the existing live `request_authorization` callback throughout an ordinary Author worker. API admission/idempotency receipt changes are a separate slice.

## Confirmed baseline and scope expansion

The keyed ordinary local API supplied a transient revalidation closure, but the original worker invoked it only for registered branch or expected-digest Author sessions. Its ordinary context preparation, post-assembly guard and original adapter-facing guard ignored the closure.

An immutable baseline probe used real File repositories, the production API/JobManager/TextModelNode/LegacyTextProviderAdapter, and a controlled MockProvider. After HTTP 202, it archived the real source without a version change or deleted/recreated the project and initial chapter with the same slug/chapter ID/version but a different existing incarnation. Both mutations were exercised before initial context and before the adapter guard, with both snapshot modes. All eight counterexamples completed with callback=0, context=1, snapshot-call=1, adapter=1. The original closure independently rejected archive with CHAPTER_NOT_FOUND and replacement with IDEMPOTENCY_OWNER_CHANGED.

The initial three-checkpoint repair passed its intermediate 122-test run, but independent review found four further real File/Mock counterexamples: required-snapshot jobs could publish COMPLETED after end-of-stream revocation, and both snapshot modes could retain late deltas after revocation. Those four cases were rerun red against the frozen intermediate source before extending the same worker-only slice. The partial repair was not treated as ready to publish. Its logs remain unchanged.

These are local synthetic behavior observations, not external disclosure or real-provider/model execution evidence. Network attempts were zero. Required snapshots precede dispatch; default writer snapshots are deferred until provider completion.

## Implemented boundaries

An already-callable ordinary transient closure is now checked:

1. Before initial route/request/source/context preparation.
2. At entry to the original Author guard, including its original adapter-facing use.
3. Before either original required/deferred snapshot write.
4. Before accepting each new delta and before accepting completion for publication.
5. After deterministic review, around a potentially slow terminal hook, and before publishing the final successful result.

A private ModelRuntimeError subtype converts callback exceptions to a fixed safe error and prevents authority refusal from falling through to another local route. Valid authorization still permits the original provider-preflight fallback. Exception text, HTTP details, repository roots and tokens are not copied into the Job error.

TextModelNode converts runtime exceptions into failed events and otherwise loses the exception subtype. A private in-memory boolean records that this live request was refused so a later callback recovery cannot make that failed stream's partial buffer reviewable. This boolean contains no exception data, is not a Job dataclass/public/persisted field, and is not reconstructed after restart.

On observed refusal, the worker stops accepting late output and clears the failed task's output buffer and derived review issues before publishing failure. Already delivered lawful chunks cannot be recalled from a user's screen or external consumer. Clearing the current failed result does not erase previously authorized snapshots, source files, usage or dispatch/settlement evidence. These checkpoints are not an owner lease or an atomic compare-and-swap spanning source validation and a subsequent write.

## Execution is not publication

A provider may complete successfully while publication is no longer authorized. In that case:

- Observed response usage, execution mode, provider/reference metadata and completed-route evidence are retained.
- The known provider execution outcome remains COMPLETED even though the public result is FAILED.
- Dispatch and terminal hooks are not repeated. A successfully completed settlement is not relabeled as failed merely because publication was denied; a failed or uncertain settlement keeps its existing reconciliation status.
- A dispatched stream stopped before completion is not represented as never dispatched. Existing dispatch/accounting evidence and unknown usage semantics remain intact.

Only ordinary jobs with actual terminal hooks use the existing non-adoptable SETTLING phase during settlement. A post-hook live check must succeed before COMPLETED is published. Hook-free jobs stay GENERATING until the final check, avoiding new settlement-recovery requirements for ordinary no-hook jobs. A failed settlement persistence cannot be promoted back into COMPLETED. Cancellation while publication is pending preserves an already observed completed execution outcome.

Existing committed terminal states are checked before late event processing. Late events/refusals do not resurrect or clear an already accepted/rejected/cancelled task. Controlled terminal fixtures verify that behavior; they do not claim a running task can be adopted through the normal accept API.

## Compatibility and deliberate limits

- There is no second owner, persistent grant, new Job schema, recovery protocol or alternative adapter dispatch.
- Registered branch and reviewed Author sessions retain their original callback, flag and digest requirements. Real Author preview→digest→prepare→start and real Graph preparation/execution compatibility are tested.
- Graph, Creative Director, Image and OCR retain their dedicated worker paths. The Creative/Image/OCR checks here prove rejection without their private capability and no ordinary fallback, not full successful execution certification for those domains.
- Jobs without a callable callback retain their existing legacy behavior. Callback absence is not evidence that an old job is authorized or safe to resume.
- Interrupted-job recovery still marks interrupted jobs FAILED and does not reconstruct a closure or its private refusal state. This increment does not protect arbitrary historical GET/retry/adoption through a newly invented global permission system.
- A callback can release its own authority lease before returning. Validation and subsequent context/snapshot/output persistence are not atomic owner isolation. No universal check-to-write race, multi-worker recovery, power-loss recovery or post-restart authorization claim is made.
- Real models, cloud providers, PostgreSQL, Windows/desktop Host, packaging and external CI are not verified here.

## Verification and evidence

All tests use the existing shared `.venv` interpreter but actual cwd/PYTHONPATH/PROJECT_ROOT point to this separate worktree. HOME, host data, application data and temporary fixtures are isolated under `.runtime`. The runner verifies `app.jobs.__file__` and its SHA-256 before testing and rejects socket connections. No installation or external provider/database action occurred.

- Initial fixed-base red: 14 failed / 1 passed, including all eight pre-context/adapter counterexamples. Baseline jobs.py SHA-256: `5a5803f53173752b31471e3649fb134a76d1267b6e45418157634db8a8553ba9`.
- Intermediate partial repair: 122 passed / 2 PostgreSQL-only skipped. Original logs and freeze record are retained, not presented as the final publication-fence result.
- Genuine late-publication red: 4 failed on the frozen intermediate source `b08cf671897cc4209373e46ff67929800c3bf9e0578257a2accd5b50ae42c9bc`.
- Final combined seven-suite run: **159 passed / 2 PostgreSQL-only skipped**, exit 0, zero network attempts. The new worker file contributes 69 passing cases.
- Four warnings: three existing dependency/Pydantic warnings and one assertion-rewrite warning from the source-verifying wrapper importing app.jobs before pytest.

The final matrix includes required/deferred snapshots and non-writer operations; archive/owner replacement at initial, stream and final-publication boundaries; usage/receipt preservation; transient and stable refusals normalized by TextModelNode; no refusal fallback; valid provider fallback; once-only hooks; settlement failures; no-hook recovery behavior; cancellation and already persisted terminal controls; and the original branch/Author/Graph requirements.

Final source hashes:

- `app/jobs.py`: `71b6d2d20ce51df5cf1d52ca1d51562e1ae1326c1dbadb8164e733395de44c34`.
- `tests/test_generation_worker_authority.py`: `9b03821ad7dd30172f4dcd070bc84925e71f16cd1ac6ca5682e0066716cd9406`.

Evidence under `.runtime/worker-authority-fence-20261025/`:

- `red.log`, `red.xml`, `red-exit.txt`: immutable-base failures.
- `final.log`, `final.xml`, `freeze.json`: unchanged intermediate three-checkpoint evidence.
- `publication/red.log`, `publication/red.xml`: four genuine late-publication failures.
- `publication/final.log`, `publication/final.xml`, `publication/final-exit.txt`, `publication/freeze.json`: final expanded result and file hashes.

An auxiliary run that omitted required broker fixture flags was rejected as a fixture run; its failures are not used as revocation evidence. `git diff --check` passed. No commit or push is included; the worktree remains for parent review and integration.

## Primary integration with RESERVED admission

Integrated on primary base `4fd956e461d3632b55a3b7e84a7ab344b8abc91f` after verifying a clean checkout, unchanged `app/jobs.py` relative to `e9830fc4c24fe8b0b08f2fbba03d3f4dbf35a86e`, and all three reviewed input hashes. The production worker and tracked worker test were copied byte-for-byte; only this delivery document was extended. The previously published admission implementation is unchanged. Its older document's statement that the worker lacks an ordinary live callback fence describes that admission-only slice, not this integrated worker.

Independent worker review before integration recorded **186 passed / 2 PostgreSQL-only skipped**, no unresolved P1/P2 in its stated scope. That result was not treated as combination proof. Against actual primary imports, the new integration verification separately recorded:

- Nine tracked suites: **216 passed / 2 PostgreSQL-only skipped**, no failures, exit 0, 75.77 seconds. Includes worker authority, RESERVED admission, existing idempotency contracts, variants, restart, multiprocess store isolation, snapshots, original Jobs and model runtime.
- Existing independent admission fault and worker checkpoint/publication probes: **52 passed**, no failures/skips, exit 0, 33.59 seconds. These are existing review cases rerun against primary, not newly discovered vulnerabilities.
- Both runs verified actual primary paths and SHA-256 for `app.jobs`, `app.api`, `app.idempotency`, and `app.services.generation_admission_receipt`. Frozen production and tracked test hashes were unchanged after each run. Each run had zero socket connection attempts and four warnings (three existing dependency/Pydantic warnings plus source-verification import assertion rewriting).

Exact shell commands, the verifying Python wrapper, sanitized logs, source hashes, reviewer-probe hashes and per-suite counts are in [evidence/generation-worker-authority-20261025](evidence/generation-worker-authority-20261025/). Logs replace checkout paths with placeholders. Command records are the actual local invocations, not a self-contained test distribution: they require the existing `.venv`, `.runtime/activate-backend.sh`, and the referenced existing review probe files. The nine tracked suites are available in the repository. HOME/XDG/appdata/data/tmp were separate per run; existing runtime activation removed provider/database credentials. No packages were installed. `git diff --check` passed.

No combination run failed or needed a fixture retry. Prior genuine red and invalid-fixture observations remain distinguished above and in the independent review; neither is silently recounted as integrated verification. These focused passes are not a full repository/backend suite pass. The original live-callback, non-atomic validation, historical/restart, multiworker, provider, PostgreSQL and platform limitations still apply. No commit, push, merge or deployment is part of this integration step.

## Final independent integration review

A separate reviewer inspected the integrated 4fd956e admission/worker composition and executed two additional restored-authority replay probes: **2 passed**, zero socket attempts. A one-time worker pre-dispatch refusal remains non-redispatchable when authority later becomes valid: recorded v2 returns the original job, and retained RESERVED returns ADMISSION_UNCONFIRMED. Both keep the failed original job and zero context/adapter calls. No new P1/P2 was found within the reviewed File/Mock scope. This is not a PostgreSQL, provider or cross-resource atomicity certification.

Portable evidence includes the exact 52-case probe sources and separate final two-case review source/logs under `evidence/generation-worker-authority-20261025/`. The counts are distinct runs, not a summed project completion score.
