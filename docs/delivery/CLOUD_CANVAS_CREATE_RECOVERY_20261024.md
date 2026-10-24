# Explicit recovery of an uncertain empty-canvas creation

Starting point: `5770b940f268bcfd71c3669e95fd599750690163`. This bounded slice addresses an empty CanvasView create whose acknowledgement is lost before a formal image Job exists. It reuses the original CanvasView request ID, idempotency and actor/scope/incarnation ownership. It does not create another canvas database or execute a production task.

## Implemented contract

The existing create body optionally carries `image_node_intent`, contract `studio-canvas-image-node-create/1`: project, scope, incarnation, node ID, title, position and prompt digest. It permits only the canonical empty definition for that title. The original row stores this intent beside its original request ID/digest. Requests without the new field retain their original serialization and behavior. A new-intent replay against an edited view is refused.

`POST /api/projects/{nid}/studio/canvas-views/resolve-create` is an explicit **read-only observation**, despite using a JSON POST. Its closed body contains the original request ID, expected incarnation and exact intent. The original `domain.read` invoker supplies current identity and authorization. The response contract `studio-canvas-image-node-resolve/1` returns that identity and the original CanvasView only when exactly one current actor/scope/incarnation-owned row matches its original request digest and stored intent, remains v1 with no history and still has the exact empty definition/digest.

The request is capped at 16 KiB and the original collection at eight records. Lookup reads an original detached snapshot; it neither opens an asset phase nor creates a missing project identity or raw scope record. It cannot inspect other actors' definitions or use the latest view as a guess. Duplicate/corrupt matching records, an altered intent, an edited view or a changed project incarnation fail closed. Formal task preparation also compares a stored new creation intent with its node capsule; old views without that intent keep their existing contract.

**404 means absent at that snapshot, not proof that an earlier in-flight create cannot still commit.** It never permits a blind create replay. A later explicit observation may find the original result. The recovered snapshot is not a reservation against future edits; original queue and dispatch CAS checks still apply.

## Browser behavior

Before the first create POST, the component writes and reads back a bounded recovery hint for the verified owner and node. It contains only original request ID, owner IDs, title/position and prompt digest; no prompt bytes, token, provider response, approval or execution authority. Failed/inaccessible storage prevents dispatch. Corrupt, foreign or old-format records remain intact and block a new create.

A cold remount sends no request automatically. A valid pending hint keeps creation and queueing disabled until the user explicitly selects **重新核对此次空白位置创建**. Fresh owner/incarnation, current write capability, exact current node intent and an unchanged local hint are checked before and after the original resolve call. Only the unique, unchanged original result restores a production target. Recovery itself does not create, queue, execute, approve or adopt anything. The hint remains until a verified original Job gives the existing task-recovery path an authoritative task ID.

Creation and lookup are bounded to 15 seconds and abort their captured request on retirement. An abort does not assert that server work rolled back. Synchronous pending/unknown guards, request generations, source/owner fences and exact hint checks retire old callbacks, including late create replies after a timeout and a not-found lookup. Parent-deferred dispatch, A/B/A, unmount, repeated clicks and marker replacement cannot publish a different result or silently retry. A storage readback failure cannot substitute another window's request ID.

## Scope and verification limits

This supports **new creations that stored the new intent and retained their browser recovery hint**. Older intentless unknown creates cannot gain node provenance from a browser marker, matching title or copied request ID. Losing the browser hint is not cross-device recovery. Browser storage comparisons/readback are advisory and are not an atomic multi-tab transaction or a global exactly-once guarantee. No cleanup or deletion is performed.

Real File/API evidence covers committing through the original create route, injecting a post-commit 503, constructing fresh original File/Graph/Asset service instances and explicitly resolving the exact original empty view. It also covers idempotency, snapshot-not-found followed by a late original commit, version ABA, ambiguity, authority changes and no scope/identity write on lookup. Frontend lifecycle and HTTP tests are software projections and are reported separately.

The real **formal media approval → generated-result save → cold reopen** positive remains NOT_RUN. No media review, ingestion, inspection, provider execution, paid/GPU operation or browser sandbox bypass is part of this slice. PostgreSQL, native Windows and browser/geometry acceptance also remain NOT_RUN. These tests prove empty-position recovery, not model output or approval.

Fixed source, directed test counts, standard type/build and independent publication review are recorded below after verification. GitHub CI is checked after normal work-branch push; local results never imply Actions execution.
