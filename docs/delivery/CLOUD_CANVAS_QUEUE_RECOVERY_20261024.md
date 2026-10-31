# Exact recovery of an uncertain formal image-node queue request

Starting point: `afb3c8d718215ff184ae82145b3d0edcd8865f3f`. The existing formal panel already had same-mount request recovery, using an in-memory creation record and the first matching list row. This slice closes the durable identity and uniqueness gap for standalone, local, source-free `m5.image.t2i` node tasks. It does not introduce another queue or change legacy unbound workflows.

## Original-owner observation

`POST /api/projects/{nid}/studio/production/jobs/image/resolve-create` is a read-only original-owner observation. Its exact JSON body is `{request_id, request_digest, canvas_image_node}`. The original production invoker retains Host identity, principal binding and current `domain.read` scope. The original image owner takes one bounded queue snapshot and selects only its current actor/project/branch/scope/incarnation. It requires one request-ID match and one unambiguous selected Job ID before validating the original body/context/binding, request digest, command capsule and any current receipt.

The service returns the actual original ProductionJob, including its current status/version. It validates source-free local text-to-image, the exact original node target and current CanvasView incarnation/version/digest. It does not recompute a changed provider route, contact a provider, load an Asset or inspect candidate content. Future execution still needs its original current route/preview, target and Job CAS checks.

The new observation has a 16 KiB request and 256 KiB response limit, and bounds the original queue to 200 formal rows and a 64 MiB file. It does not write queue JSON or provision project identities. Old list/get and unbound create contracts remain unchanged. The new node-bound idempotent-create path rejects duplicate matching original records instead of taking the first.

404 means the request is absent at this snapshot. It cannot prove that an in-flight create will never commit and never permits resending. An exact later observation may find the old request even when a newer different task is present. Ambiguity, altered identity, changed node target or a stale CanvasView fail closed. Authorization failures retain their original status semantics and expose only the bounded new-route error contract.

## Node UI and durable identity

Before the real queue POST, the original panel invokes an owner-bound synchronous callback. It persists and reads back a bounded hint containing the verified owner IDs, original node/canvas capsule, request ID and request digest. No prompt bytes, provider credentials, command body, candidate or approval marker is persisted. Missing callbacks or unavailable storage block new node queue admission; ordinary unbound panels retain their existing behavior.

A pending queue hint survives cold remount and blocks a second empty-view create, another queue request and the generic matching-task chooser. The user explicitly selects **核对原图片任务入队结果**. The UI reads the exact original owner, then rechecks the Job, original CanvasView and history under the captured source/owner. Only that exact result restores the association. It does not replay preview consent or execution confirmation and does not execute, review or adopt anything.

Node queue creation is bounded to 15 seconds with a captured AbortSignal. Timeout retires late replies without asserting server rollback. Parent-deferred dispatch, request generations, monotonic source/owner fences, exact hint checks and synchronous pending guards prevent retained callbacks, duplicate clicks or A/B/A from applying another task. 403/404/409 and uncertain responses keep the original recovery identity and allow explicit read retry. Current-session input remains visible in memory; it is not copied into browser recovery storage.

After an exact owner result, cleanup confirms the older empty-create hint first and only then clears the queue hint. Failed or conflicting cleanup retains UNKNOWN and the captured identity in the current instance; it does not overwrite another pending marker. Local storage readback/compare is advisory, not an atomic cross-tab transaction or a global exactly-once guarantee. A removal followed by an unreadable store cannot guarantee durable retention. Lost browser hints and older untracked unknown queue requests cannot be reconstructed by guessing list order.

## Evidence boundary

Real File/API cases commit through original preview/create, inject a post-commit 503 and reconstruct fresh original File/Graph/Production/Asset service instances in the same process. They explicitly recover the exact original QUEUED Job with no second admission, attempt zero and no model execution. Other cases cover late commit after an absent observation, current CANCELLED status, duplicate request and Job IDs, newer unrelated tasks, changed target/version, actor/scope/incarnation and original Host/read revocation. Shared-mode direct-service authorization cases are distinguished from the unchanged shared HTTP Model Host restriction; they are not a shared HTTP positive.

Frontend tests use actual node container, original production panel and HTTP clients with declared software responses. They verify cold recovery and lifecycle behavior, not real File approval or inference. Provider, execute, review, accept, Asset content, media inspection and fetch calls remain excluded from this slice's new verification.

The real formal media approval → generated-result save → cold-reopen positive remains NOT_RUN. Real providers, paid/GPU calls, PostgreSQL, native Windows and browser/geometry acceptance also remain NOT_RUN; previous media and sandbox restrictions are not retried.

Fixed application/test source: `d739c50daa1d69366fb9f1e6fd00074d852f837c`, tree `3c2d568a4b9cc8c0df6828346b4894e7185697d8`. A following delivery edit changes documentation only.

| Verification | Actual result |
| --- | --- |
| Real File/API | **62 passed**, 3 existing warnings, 18.27s. Includes 20 new exact queue-recovery cases plus 42 related empty-create/formal-queue/manual-card cases. Service reconstruction is within the same test process. No model execution or actual approval. |
| Related frontend | **184 passed**, 17 files, one worker, 43.59s. Includes 11 new full node/container/panel/client lifecycle cases and 17 hint/client cases; these 28 are part of the total, not additional passes. |
| Standard type/build | **PASS** `corepack pnpm build` (`tsc -b && vite build`), process 58.846s; Vite 8.71s, 2632 modules. Frozen existing dependencies, unchanged manifests/lock; existing chunk-size warning only. |
| Independent review | Original-owner authority, uniqueness, lifecycle and public-diff review performed separately from tests; final source and delivery checked before publication. |

An initial File precheck retained 17 passes and one test failure because the original Host-binding ABA rejection was 401 rather than the assumed 403. The corrected assertion accepts the original 401/403 authorization rejection while retaining non-mutation and no-stale-publication checks. An initial frontend precheck retained 23 passes and three fixture failures from assuming automatic provider loading; the fixture now uses the existing explicit configuration-read action. Original precheck evidence is retained; the final fixed-source runs above all passed. No app behavior was weakened to accommodate those assumptions.

CI is separately read back after normal work-branch push. Source/dependency hashes, exact commands, raw logs and remote evidence remain in the cloud handoff.

## Next verified reuse point

The existing `StudioProductionTasksPanel` already selects and re-reads an exact original task under a selection lease. `IndependentStudioWorkspace` currently forwards that task to a plain production panel without a node task binding, so its existing safety gate refuses node-bound execution there. A next bounded continuation can reuse this selector and original Job/Canvas/history reads, then open an ephemeral **resume-only** node session: no browser-graph copy, no new queue, no new task center or registry. That continuation is not implemented by this source snapshot and is independent of media approval or inference acceptance.
