# File-local ordinary bound manual review

Base: `5eb983fd620ef905aa4dc1afae80b756ee7e7078`.

## Supported outcome

The original JobManager can now accept or reject a **pre-existing, internally
bound, local unscoped File draft**, including one restored cold from the original
GenerationRepository. The binding is not created or upgraded by this operation.
The existing review HTTP routes can reach this narrow manual-review path; their
request and response schemas are unchanged.

This does not activate API admission/emitter capture, bound start/worker execution,
retry, cancel, staged variants, PostgreSQL review, branch review or collaborative
review. Those gates remain explicit unsupported outcomes. No new task store,
owner marker, execution queue, schema or migration is introduced. Genuinely
unbound jobs retain their original behavior, including the limitations documented
by the previous legacy replacement-owner counterexamples.

## Original owner and ports

At manager construction, a private composition snapshot pins the actual original
GenerationService, ChapterService, CanonService and MemoryAgentRunner plus their
original File repositories/backends. Unknown service types are not introspected:
passive PostgreSQL managers still do not touch unsupported downstream ports.
Review eligibility requires exact supported types, original instances and data
paths, local nullable identity fields, no caller actor/scope, and no collaborative
or added-source/preview callbacks. Existing content, accounting, completed-status,
expected-version and original generation-base checks still apply.

Live request authorization runs before acquiring project/review/Job locks. The
review context then takes the existing runtime-event transaction, original
CreativeProjectStore owner/lifecycle lease, original generation-review lock and
Job condition in that order. The original durable record is required and reread
inside these locks; a missing row never falls back to an injected cached draft.
The job identity is checked against the original persisted binding throughout.

The common original acceptance body still performs:

1. Durable ACCEPTING claim before source effects.
2. Original chapter create or versioned save, including existing history behavior.
3. Original summary write and accepted-revision Canon extraction.
4. Original pending Canon write and ACCEPTED persistence.
5. Original memory enqueue, with the original incarnation forwarded to the
   previously reviewed bound memory path.

Actual original method references are captured for this invocation. Each effect
rechecks pins, the physical owner marker and the complete original memory
composition. Private optional root/incarnation parameters reach the existing File
chapter/read/history/summary/Canon mutation guards and original generation save.
They are validated inside the original lifecycle mutation boundary. Thus a facade
wrapper that replaces the owner or reroutes a repository after an earlier check
cannot write into a replacement merely because an outer RLock is reentrant.
These parameters are internal; no API body or historical record gains them.

The common lifecycle lease remains held across all synchronous effects, not merely
at the last check. Participating deletion from another thread/process must wait.
The final-port checks additionally fence same-thread reentrant replacement at
chapter and summary/Canon seams. No source/model work is performed under this
lease; memory extraction's independently started thread waits for owner release
and uses its own original asynchronous identity fences, without a parent join.

File-bound interrupted restore now takes original owner before generation-review
lock too. This avoids inverse lock order when a stale load_all snapshot says
QUEUED while its durable row is already COMPLETED and another manager is reviewing.
Legacy/PostgreSQL restore ordering is unchanged; no second database connection or
URL-derived composition is introduced.

## Scope and failure behavior

The internal acceptance helper requires its live original manager/job context,
entering thread and single-use acceptance claim. A retained callback cannot use
that context after exit, from another thread or a second time. This is a narrow
internal execution context, not a serialized grant or a general mutation-enabled
boolean. Other ordinary mutation gates do not consult it.

Original uncertain-acceptance behavior is preserved. After a durable claim, a
source, summary, Canon or terminal failure attempts to persist
ACCEPTANCE_UNCERTAIN; if that cannot be persisted safely, the original ACCEPTING
claim remains non-replayable. A failed initial claim with no durable change has no
source effects. No multi-file rollback is claimed. Original independent memory
failure behavior remains: enqueue is attempted with the captured incarnation, but
failure does not undo an already accepted manuscript or silently requeue writer
work. Store-composition loss before terminal acceptance is not treated as an
ordinary independent memory failure.

Existing runtime-event buffering defers observer callbacks until all owner/review/
condition locks release. On a partial acceptance failure, the exception is held
until buffered notifications for actual committed effects and the uncertain
receipt have flushed, then rethrown. This does not pretend that partial writes
rolled back, nor run authorization/observer callbacks under a project lock.

This is protection for cooperating original File owners, not a filesystem sandbox,
exactly-once model inference, general multi-file crash atomicity, chapter-incarnation
reconciliation within an unchanged project, or historical unbound repair. PostgreSQL
and scoped/branch mutation need their own original-owner composition and remain
closed. Trusted new ordinary admission/dispatch remains a later separate slice.

## Evidence boundary

New positive manual-review tests use explicitly synthetic trusted persisted
COMPLETED bound drafts, then actual cold restore and original File acceptance,
chapter/summary/Canon and bound memory effects. A nonempty synthetic Mock memory
response traverses the real local runtime/adapter chain and creates original
Lore evidence/proposal/relations. Independent fixtures also use fresh internal
bound records carrying output from a separately generated original unbound Mock
writer. No existing unbound record is upgraded and no bound start guard is bypassed.
This is not genuine end-to-end bound generate-to-adopt evidence.

Original unbound MockProvider worker/retry/accept and specialized persistence remain
separate compatibility controls. All runs use the existing dependency environment,
actual worktree imports, isolated HOME/XDG/data/tmp and blocked network sockets.
Live PostgreSQL, real external/local models, frontend changes and service installation
are NOT_RUN. See the portable evidence manifest under
`../delivery/evidence/file-local-bound-review-20261025/README.md` for commands,
raw failures/final stdout/XML, frozen hashes and independent review.
