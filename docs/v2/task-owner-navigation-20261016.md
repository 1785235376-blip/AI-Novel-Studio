# Original task and candidate navigation; Storyboard handoff audit

Baseline: `b01c54106fcfc91e35553434654418a533d3bde0`. The containing local commit identifies delivery. Local-only work; no push or hosted CI because costs are not established.

## Audit and scope decision

**STORYBOARD asset-to-shot draft reference handoff: BLOCKED.** `CreativeShot` / `CreativeInput` in `frontend/src/creative/types.ts` have no asset-reference edit field. `useStoryboardWorkspace.ts` explicitly owns only reads, shot selection and temporary display ordering. Its client exposes GETs, not a draft attachment owner. The separate legitimate `studioStoryboardClient.storyboardBindImage` calls `POST .../shots/{id}/image-binding`; `app/creative/storyboard.py::bind_image` immediately advances the original document version, updates `storyboard_image_bindings`, and removes `storyboard_approval`. It is not an unsaved reference-draft edit. That owner remains entirely unchanged. No reference field, grant, substitute Prompt Adoption POST, automatic binding or decorative side-by-side completion was invented. Existing IMAGE/VIDEO/TIMELINE handoffs are preserved.

The next existing task navigation gap was audited read-only before edits. `IndependentStudioWorkspace` previously claimed a task/candidate was located after merely switching to PRODUCTION/ASSETS. `app/experimental/api.py` registers authority `media` to experimental `MediaService`, not to Studio ProductionJob. `ux.py::projected_task` supplies an exact feature/id/task_authority pointer. The original media router already offers `GET /media/tasks` and `GET /media/proposals`; `MediaService.proposals` excludes candidate bytes. Its review projection binds candidate `source` to `task_id`. No generic task ID can be inferred to be a Studio production job ID.

## Delivered bounded read-only behavior

- The existing TaskCenter locate action passes through the original workspace dirty-navigation guard. Recognized media task pointers read the original task list and select one exact ID. Media review candidates read the original proposal list and require exact ID, version and originating task ID.
- Opens show the original record and current status, with explicit read-only wording. No execute/retry/approve/save/export action is added. A mismatched candidate version is refused rather than substituted with latest.
- Unsupported owner/domain/pointer combinations remain on the task view with an honest unavailable message and zero substitute-owner reads. This is a bounded route consumer, not a second owner registry, queue or store.
- The original captured transport/read guard supplies scope and authorization. Repeated open of the same selection and repeated read clicks coalesce. Close, leaving TASKS, identity retirement, source/client/target/busy changes and ABA invalidate late reads. Abort is passed through the original read guard. Failures require explicit reread; no automatic replay.
- Exact selection also validates the original project and full native local/collaboration scope, surfaces owner stale warnings, and rejects missing, duplicate, invalid or over-bound records (500-list/64,000-character display bounds). Original tasks, candidate content, asset bindings and approval state are never mutated.

## Verification and limits

190 mocked UI/contract checks and 30 PUBLIC checks passed. Type/build/discovery/token and 487-file PUBLIC closure results, final commands, exit codes and source/log hashes are recorded in `task-owner-navigation-20261016.json`. Mocked UI/contract testing is not a real browser or original server acceptance claim. No backend owner or persisted contract changed, so no new File owner write test is required. Independent review found and fixed a StrictMode initial-read cancellation and missing returned-scope validation; regression coverage includes deferred StrictMode initial opens, foreign scopes and visible stale-source warnings. Initial test-only TypeScript tuple and localized label failures, and superseded checks, remain in delivery receipts.

Browser/visual/native input/performance, PostgreSQL/P0/security lifecycle, Windows/GPU/provider/user-machine/paid/hosted CI/full RC: NOT_RUN. P0: BLOCKED. R3-GATE: HOLD. Production Prompt Adoption writes remain disabled. PUBLIC closure remains required and unchanged.

## Remaining work

Task navigation remains PARTIAL: additional original owners require individually verified existing read/reopen routes; no unsupported task is declared opened. STORYBOARD draft reference editing requires an explicit original-owner contract decision and is BLOCKED. DeliveryCenter entitlement producer remains BLOCKED without synthetic grants. Independent parent review is required before the next tracked slice.
