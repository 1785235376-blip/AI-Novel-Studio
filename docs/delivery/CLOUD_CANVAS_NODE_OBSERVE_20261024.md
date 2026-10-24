# Read original node-task metadata after its queued phase

Starting point: `ef65454344709d98f891f246e8c56e3e1d15d647`. The preceding exact task-center continuation accepted only QUEUED Jobs. The original task selector could list a RUNNING, UNKNOWN or CANCELLED node Job, but could not open its fixed node-bound details after browser associations were lost.

This slice adds an immutable read-only continuation mode for those three initial states. It reuses the existing task selector, exact queue-request resolver, Job GET and original CanvasView/history reads. It adds no API, queue, owner, graph database or task-center layout. The existing QUEUED continuation and ordinary panels keep their prior defaults.

## Pure metadata observation

An explicit selection captures one exact original Job and reads its current original project/incarnation, request identity, source-free local text-to-image capsule, prompt digest and unchanged empty Canvas target. The full selected Job must still match the resolver and final GET. Changed source, ambiguity, loss of read authority, scope/incarnation/version mismatch or timeout refuses the handoff; no latest-task substitution occurs. These separate observations are not a cross-owner transaction or an execution reservation.

Read-only continuation does not require write capability. It does require successful current original-owner reads under the existing Host/domain.read boundary. There is no invented `can_read` flag. A readable trusted-loopback Canvas alone cannot authorize a Production Job. The workspace forces mutation/review capabilities off for the destination even when the actor otherwise has write permission.

After opening, only an explicit GET of the same Job and download of its already-read JSON metadata are available in this panel. Provider/configuration loading, including mount-time loading, is blocked. Preview, impact confirmation, editing, task-list switching, new queueing, execute, refresh, reconcile, cancel, candidate media, review and adoption are blocked both in presentation and controller dispatch. There is no automatic Job polling or action replay. Existing unrelated workspace navigation/projections retain their separate contracts.

The original GET reads queue metadata, validates original ownership/body/context/binding and projects public JSON. The exact resolver additionally checks request identity and the recorded receipt digest when present or required. Later GETs are metadata observations, not a new content-integrity proof. Neither path enters candidate publication or media recovery based on RUNNING/UNKNOWN status. Reconcile is deliberately unavailable: its existing internal publication/review branches may read Asset content. It cannot be treated as a metadata-only recovery operation.

The mode is fixed for the controller lifetime. Authoritative read denial or Host/source identity retirement blocks that session; returning through mode/client/source A/B/A does not revive old callbacks. Changes to write capability never upgrade this observer to an action panel, and read-only observation can remain available under current read authority. Same-source observations cannot roll back version or return to QUEUED to unlock execution; a changed public projection at the same version is rejected. Captured observations and callback values are cloned in this mode so a caller cannot mutate the accepted comparison in place. Observed terminal CANCELLED/FAILED/APPROVED states cannot be replaced with another state in that instance. These are conservative display checks over the original owner's facts, not a new complete state machine. Candidate/status progression never enables media actions. Old dirty-navigation and source-ticket protections remain in place.

## Evidence limits

The real File/API fixture is prepared in a synthetic temporary project through original preview/create, then an original metadata cancellation. Fresh original File owners are reconstructed in the same process before original overview/list/get/resolve/Canvas/history reads. The observation is CANCELLED with attempt zero, no second queue and no provider execution. Setup mutations are separate from the read-only observation phase; sentinels prevent replay, media and task operations during observation.

The committed fixture is the actual HTTP capture, 22,719 bytes, SHA256 `464904a245c4eee0a87e720cc1a9859290c100a8a31d920470c2b2fe34c8ac65`. It contains synthetic metadata and no credentials, private paths, generated content or approval. RUNNING and UNKNOWN frontend cases are explicit software projections; no actual inference or execution outcome was manufactured to produce them.

Fixed-source verification results and independent review are recorded after integration. The preceding bounded regression had 33 unchanged baseline failures in four older workspace files; this slice does not claim to repair them or to establish an overall green suite.

Real model/GPU/provider execution, formal media approval → generated-result save → cold-reopen positive, PostgreSQL, native Windows and browser/geometry acceptance remain NOT_RUN. Prior restricted media operations and browser-sandbox restrictions are preserved. The Grok unified-workspace branch remains unmerged; this is the existing ordinary Studio entry.
