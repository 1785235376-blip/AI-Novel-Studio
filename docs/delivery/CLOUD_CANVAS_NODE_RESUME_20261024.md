# Resume one original queued image-node task from the existing task center

Starting point: `68291ec79b3be9c842c8d0e82f6f1ba4cb1a2b60`. The existing production task selector already re-read an exact selected Job, but the workspace forwarded it to an ordinary panel without its node binding. The original safety gate correctly refused node-bound actions there. Losing a browser node or its recovery hints therefore left no usable continuation through this selector.

This slice reuses that selector and the original production/CanvasView owners. It opens an ephemeral **仅续接原节点任务** panel for one explicitly selected, still-QUEUED, standalone local text-to-image node Job. It adds no backend API, database, task center, window registry or graph-storage format. It does not merge the separate Grok unified-workspace branch or connect its `?uw=1` preview.

## Exact source and navigation

Before discarding any current draft, the workspace captures the selected Job and explicitly reads the current project overview, the existing exact queue-request resolver, original CanvasView/history and original Job again. Full selected-record equality, request identity, prompt SHA, node capsule, project/scope/incarnation and current empty target version/digest must agree. Missing capabilities, a changed or ambiguous source, lost authority or a timed-out read refuse the handoff. A readable Canvas alone does not authorize a production task.

These separate reads are observations, not a transaction or a reservation across owners. The original execution owner still rechecks current authority, target, route and Job preconditions before any later explicit action.

The existing task-center selection lease belongs to its mounted selector. After successful navigation, a separate workspace-owned source ticket binds the production panel to this exact source, client, module, selection generation and project identity. Reusing the old selector lease after leaving it would disable the destination. Navigating away, unmounting, changing authority or replacing an explicit Host credential retires the old session. Returning through A/B/A cannot revive its callbacks.

Dirty-draft confirmation is tied to the particular pending handoff ticket. A retained checked confirmation from an earlier selection cannot authorize a replacement task. Source validation completes before drafts are discarded; failure preserves them. Reads are bounded to 15 seconds and cancellation settles the handoff even if a deferred reader ignores its signal. Late replies cannot publish another source.

## Resume-only action boundary

The original production controller receives the validated node capsule and immutable original command. This mode hides new-task editing, queue creation, generic task switching and candidate-media/review/adoption controls. Those actions are also blocked in controller dispatch, including retained and deferred callbacks. Unrelated asset refresh and timeline editing are omitted from this source-free, single-task view. Ordinary panel behavior is retained outside this mode.

The panel can explicitly read the same Job and current provider configuration. Executing a still-QUEUED task requires a fresh original-command execution preview, current capability/route checks, a new impact confirmation and the existing conditional execute action. It does not replay old confirmation or automatically execute. Same-Job status/version progression is allowed. Changed source props retire the session; mismatching owner responses cannot substitute another request, command, provider, recipe or node source and are rejected. Failed or UNKNOWN actions retain the original owner recovery controls and do not create another task; using those controls is distinct from this slice's metadata-only File verification.

The handoff is memory-only. It does not reconstruct or write a Rebuild graph, prompt draft, queue hint, approval or browser-node association. Existing workspace navigation preferences remain separate. Closing this session requires another explicit task-center selection and fresh owner reads.

## Verification boundary

The File/API tests create a synthetic QUEUED node request using the actual original preview/create routes, reconstruct fresh original File owners within the same process and read the original overview/list/get/exact-resolver/Canvas/history tuple. The committed JSON fixture is the exact original HTTP capture: 16,672 bytes, SHA256 `3c719576610c35edc4337644cf1eeeeaebbb7fd968039802fd70d266c4e76259`. It contains synthetic metadata, not credentials, generated media or an approval. Cancellation used to exercise a version interleaving is an original metadata action, not model execution.

Frontend tests use that File-derived tuple with actual workspace, selector, controller and HTTP clients. Their explicitly confirmed execute response is a **software HTTP projection**, never an actual File execution, provider result or formal approval. Read-only authority/route checks do not establish inference availability or quality.

Fixed application/test source: `bb4621332f1e2bca56c6bca0427fa34a1a4361e5`, tree `7d122a5cc09e49f0228f409da1209d5236ece4f9`. The following delivery edit changes documentation only.

| Verification | Actual result |
| --- | --- |
| Real File/API | **4 passed**, 3 existing warnings, 9.17s (process 13.636s). Original QUEUED tuple after new File owners, changed Job/Canvas versions and Production Host revocation. Same-process reconstruction; no actual execution or approval. |
| Related frontend selection | **187 passed, 33 failed**, 16 files, one worker, 72.90s. All 39 new cases passed: 30 helper/controller cases and 9 actual Workspace/task-selector/panel cases. They are part of 187, not additional passes. The 33 failures are in four older workspace test files; baseline comparison is recorded below. |
| Standard type/build | **PASS** `corepack pnpm build` (`tsc -b && vite build`), process 54.35s; Vite 10.14s, 2633 modules. Existing dependency environment; manifests/lock unchanged and worktree clean before/after. Existing chunk-size warning only. |
| Independent review | Separate source/public-diff and receipt review; final baseline-failure comparison and delivery audit recorded before publication. |

Baseline control at `68291ec79b3be9c842c8d0e82f6f1ba4cb1a2b60` reproduced **26 passed, 33 failed** in the four older files: `IndependentStudioHostExit.regression.test.tsx` (6 failures), `IndependentStudioIdentity.regression.test.tsx` (8), `IndependentStudioReadFences.test.tsx` (7) and `IndependentStudioWorkspace.navigation.additive.test.tsx` (12). Their test sources are unchanged. All 33 exact file/test names and first assertion-error texts match this source's failures; no current-only failure was found in this selection. The failures expect older workspace buttons and asset entry controls and remain unresolved. This control establishes their presence before this slice, not acceptance of those behaviors or a clean overall suite.

Initial diagnostic failures remain in the cloud evidence. They exposed a retained old navigation confirmation, an explicit Host-token session identity omission and stale destination busy state from unrelated asset/timeline auto-reads. These were fixed without weakening dispatch guards; the final unwrapped 39-case integration/contract selection passed. An initial File test assumed that Production Host revocation also denied trusted-loopback Canvas reads; it was corrected to preserve the original authority distinction. No app permission rule was weakened to fit the fixture.

CI is read separately after normal work-branch push. Raw receipts, exact commands, source/dependency hashes and baseline control remain in the cloud handoff. No overall frontend-suite green claim is made.

Real provider/model/GPU execution, formal media approval → generated-result save → cold-reopen positive, PostgreSQL, native Windows and browser/geometry acceptance remain NOT_RUN. Prior media-operation and browser-sandbox restrictions are preserved. This QUEUED continuation does not implement first-time recovery of an already-running, UNKNOWN or completed task after all local associations are lost, nor server persistence of a Rebuild graph.
