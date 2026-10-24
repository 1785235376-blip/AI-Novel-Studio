# Resume one original queued image-node task from the existing task center

Starting point: `68291ec79b3be9c842c8d0e82f6f1ba4cb1a2b60`. The existing production task selector already re-read an exact selected Job, but the workspace forwarded it to an ordinary panel without its node binding. The original safety gate correctly refused node-bound actions there. Losing a browser node or its recovery hints therefore left no usable continuation through this selector.

This slice reuses that selector and the original production/CanvasView owners. It opens an ephemeral **仅续接原节点任务** panel for one explicitly selected, still-QUEUED, standalone local text-to-image node Job. It adds no backend API, database, task center, window registry or graph-storage format. It does not merge the separate Grok unified-workspace branch or connect its `?uw=1` preview.

## Exact source and navigation

Before discarding any current draft, the workspace captures the selected Job and explicitly reads the current project overview, the existing exact queue-request resolver, original CanvasView/history and original Job again. Full selected-record equality, request identity, prompt SHA, node capsule, project/scope/incarnation and current empty target version/digest must agree. Missing capabilities, a changed or ambiguous source, lost authority or a timed-out read refuse the handoff. A readable Canvas alone does not authorize a production task.

The existing task-center selection lease belongs to its mounted selector. After successful navigation, a separate workspace-owned source ticket binds the production panel to this exact source, client, module, selection generation and project identity. Reusing the old selector lease after leaving it would disable the destination. Navigating away, unmounting, changing authority or replacing an explicit Host credential retires the old session. Returning through A/B/A cannot revive its callbacks.

Dirty-draft confirmation is tied to the particular pending handoff ticket. A retained checked confirmation from an earlier selection cannot authorize a replacement task. Source validation completes before drafts are discarded; failure preserves them. Reads are bounded to 15 seconds and cancellation settles the handoff even if a deferred reader ignores its signal. Late replies cannot publish another source.

## Resume-only action boundary

The original production controller receives the validated node capsule and immutable original command. This mode hides new-task editing, queue creation, generic task switching and candidate-media/review/adoption controls. Those actions are also blocked in controller dispatch, including retained and deferred callbacks. Unrelated asset refresh and timeline editing are omitted from this source-free, single-task view. Ordinary panel behavior is retained outside this mode.

The panel can explicitly read the same Job and current provider configuration. Executing a still-QUEUED task requires a fresh original-command execution preview, current capability/route checks, a new impact confirmation and the existing conditional execute action. It does not replay old confirmation or automatically execute. Same-Job status/version progression is allowed. Changed source props retire the session; mismatching owner responses cannot substitute another request, command, provider, recipe or node source and are rejected. Failed or UNKNOWN actions retain the original owner recovery controls and do not create another task; using those controls is distinct from this slice's metadata-only File verification.

The handoff is memory-only. It does not reconstruct or write a Rebuild graph, prompt draft, queue hint, approval or browser-node association. Existing workspace navigation preferences remain separate. Closing this session requires another explicit task-center selection and fresh owner reads.

## Verification boundary

The File/API tests create a synthetic QUEUED node request using the actual original preview/create routes, reconstruct fresh original File owners within the same process and read the original overview/list/get/exact-resolver/Canvas/history tuple. The committed JSON fixture is the exact original HTTP capture: 16,672 bytes, SHA256 `3c719576610c35edc4337644cf1eeeeaebbb7fd968039802fd70d266c4e76259`. It contains synthetic metadata, not credentials, generated media or an approval. Cancellation used to exercise a version interleaving is an original metadata action, not model execution.

Frontend tests use that File-derived tuple with actual workspace, selector, controller and HTTP clients. Their explicitly confirmed execute response is a **software HTTP projection**, never an actual File execution, provider result or formal approval. Read-only authority/route checks do not establish inference availability or quality.

Fixed-source test, type/build and independent-review results are recorded after integration. Initial diagnostic failures and their corrections remain in the cloud evidence; they are not counted as passing acceptance.

Real provider/model/GPU execution, formal media approval → generated-result save → cold-reopen positive, PostgreSQL, native Windows and browser/geometry acceptance remain NOT_RUN. Prior media-operation and browser-sandbox restrictions are preserved. This QUEUED continuation does not implement first-time recovery of an already-running, UNKNOWN or completed task after all local associations are lost, nor server persistence of a Rebuild graph.
