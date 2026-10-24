# Explicit recovery of an uncertain empty-canvas creation

Starting point: `5770b940f268bcfd71c3669e95fd599750690163`. This bounded slice addresses an empty CanvasView create whose acknowledgement is lost before a formal image Job exists. It reuses the original CanvasView request ID, idempotency and actor/scope/incarnation ownership. It does not create another canvas database or execute a production task.

## Implemented contract

The existing create body optionally carries `image_node_intent`, contract `studio-canvas-image-node-create/1`: project, scope, incarnation, node ID, title, position and prompt digest. It permits only the canonical empty definition for that title. The original row stores this intent beside its original request ID/digest. Requests without the new field retain their original serialization and behavior. A new-intent replay against an edited view is refused.

`POST /api/projects/{nid}/studio/canvas-views/resolve-create` is an explicit **read-only observation**, despite using a JSON POST. Its closed body contains the original request ID, expected incarnation and exact intent. The original `domain.read` invoker supplies current identity and authorization. The response contract `studio-canvas-image-node-resolve/1` returns that identity and the original CanvasView only when exactly one current actor/scope/incarnation-owned row matches its original request digest and stored intent, remains v1 with no history and still has the exact empty definition/digest.

The request is capped at 16 KiB and the original collection at eight records. Lookup reads an original detached snapshot; it neither opens an asset phase nor creates a missing project identity or raw scope record. It cannot inspect other actors' definitions or use the latest view as a guess. Duplicate/corrupt matching records, an altered intent, an edited view or a changed project incarnation fail closed. Formal task preparation also compares a stored new creation intent with its node capsule; old views without that intent keep their existing contract.

**404 means absent at that snapshot, not proof that an earlier in-flight create cannot still commit.** It never permits a blind create replay. A later explicit observation may find the original result. The recovered snapshot is not a reservation against future edits; original queue and dispatch CAS checks still apply.

## Browser behavior

Before the first create POST, the component writes and reads back a bounded recovery hint for the verified owner and node. It contains only original request ID, owner IDs, title/position and prompt digest; no prompt bytes, token, provider response, approval or execution authority. Failed/inaccessible storage prevents dispatch. Corrupt, foreign or old-format records remain intact and block a new create.

A cold remount sends no request automatically. A valid pending hint keeps creation and queueing disabled until the user explicitly selects **重新核对此次空白位置创建**. Before lookup the UI freshly reads the owner/incarnation and its advisory write capability, then compares the exact current node intent and local hint. Source/owner and hint fences remain current through return; the read-only server lookup continuously enforces original read authority. Future queueing still needs its original current write authorization. Only the unique, unchanged original result restores a production target. Recovery itself does not create, queue, execute, approve or adopt anything. The hint remains until a verified original Job gives the existing task-recovery path an authoritative task ID.

Creation and lookup are bounded to 15 seconds and abort their captured request on retirement. An abort does not assert that server work rolled back. Synchronous pending/unknown guards, request generations, source/owner fences and exact hint checks retire old callbacks, including late create replies after a timeout and a not-found lookup. Parent-deferred dispatch, A/B/A, unmount, repeated clicks and marker replacement cannot publish a different result or silently retry. A storage readback failure cannot substitute another window's request ID.

## Scope and verification limits

This supports **new creations that stored the new intent and retained their browser recovery hint**. Older intentless unknown creates cannot gain node provenance from a browser marker, matching title or copied request ID. Losing the browser hint is not cross-device recovery. Browser storage comparisons/readback are advisory and are not an atomic multi-tab transaction or a global exactly-once guarantee. No cleanup or deletion is performed.

Real File/API evidence covers committing through the original create route, injecting a post-commit 503, constructing fresh original File/Graph/Asset service instances and explicitly resolving the exact original empty view. It also covers idempotency, snapshot-not-found followed by a late original commit, version ABA, ambiguity, authority changes and no scope/identity write on lookup. Frontend lifecycle and HTTP tests are software projections and are reported separately.

The real **formal media approval → generated-result save → cold reopen** positive remains NOT_RUN. No media review, ingestion, inspection, provider execution, paid/GPU operation or browser sandbox bypass is part of this slice. PostgreSQL, native Windows and browser/geometry acceptance also remain NOT_RUN. These tests prove empty-position recovery, not model output or approval.

Fixed application/test source: `52ca9e442948e91a8a6b6054e72ef07f37716fd4`, tree `0dd32fed146b93eaad95f0b1479c302d47047633`. The following delivery edit changes documentation only.

| Verification | Actual evidence |
| --- | --- |
| Real File/API | **42 passed**, 3 existing warnings, 15.14s: 19 new empty-create recovery cases and 23 related original formal-queue/manual-card cases. The new positive uses an actual original-owner commit, post-commit 503 injection and fresh File service instances in the same test process. This is not a real model or approval run. |
| Related frontend | **121 passed**, 12 files, one worker, 27.00s. Includes 14 new component lifecycle cases, 20 hint/resolver-client cases and 5 additional create/response HTTP cases; these groups overlap the total and are not added again. |
| Standard type/build | **PASS** `corepack pnpm build` (`tsc -b && vite build`), process 54.864s; Vite 8.71s, 2631 modules. Existing chunk warning only; package manifests and frozen lock unchanged. |
| Independent review | Contract, authority, lifecycle and public-diff review separate from test execution; final delivery reviewed before publication. |

Frontend recovery cases cover lost acknowledgement and cold remount, 403/404/409 staying unknown, partial persistence/readback conflict, corrupt/inaccessible storage, permission/client ABA, unmount, repeated retained callbacks, StrictMode, node mismatch and a timed-out create whose late acknowledgement arrives after a not-found lookup. New File cases cover definition/version ABA, duplicate matching records, actor/project/branch/incarnation mismatch, revoked or mid-return read authority and missing identity without provisioning. Original metadata preview refuses a different node or correctly rehashed different prompt on an intent-bound view, without queueing or executing it.

An initial File precheck had seven passes and nine test failures because assertions ignored the application's standard error wrapper. The assertions were corrected to check the actual safe `detail`, retaining status/code and non-mutation checks. That 16-case selection passed, followed by bounded guard additions; final 42-case verification above passed at one fixed source. Original precheck logs are retained cloud-only. No runtime failure is concealed as a passing run.

GitHub CI is checked after normal work-branch push; local results never imply Actions execution. Exact commands, source/dependency hashes, raw logs and remote/CI readback remain in the cloud handoff records.
