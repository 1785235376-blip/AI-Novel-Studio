# Compare an original image-node target with its current saved CanvasView

Starting point: `9153bbcabd4d77f68859d61d1d635526fc636c69`. Existing node continuation correctly requires the original empty CanvasView version and digest. When that CanvasView is later edited, the original Job can remain readable while continuation fails. The task center previously offered no independent way to inspect the captured target alongside the currently saved version.

This slice adds an explicit **核对原保存位置** action to original formal image task rows. It stays in the existing task center, preserves drafts and shows a read-only metadata comparison. It does not open the Canvas editor, reconstruct a node, restore a historical version or authorize any task action. The original continuation and exact-empty resolver remain unchanged.

## Original-owner observation contract

`POST /api/projects/{nid}/studio/production/jobs/image/{jid}/target-observation` is a read-only observation. Its strict body is `{expected_version, expected_request_digest}`; the server obtains the Canvas target from the original owned Job, never from a client-supplied Canvas ID or scope.

The existing Production invoker retains Host identity, principal/scope binding and `domain.read`. The route covers both Production and Graph stores with their existing `existing_owner_only` context before the invoker runs. Missing File identity therefore refuses this observation rather than provisioning another identity. Ordinary overview/GET/list contracts are not changed and are not claimed to have this stronger property.

The server reads the original standalone source-free local text-to-image Job, checks the selected version/digest, command capsule, context and any required recorded receipt digest, then releases the Job read before original Canvas GET/history metadata phases. The current Canvas ID/scope/incarnation/version/digest must agree across those reads. Its original history must contain the captured version/digest with an empty definition and no adopted-node origin. A final original Job read must match the entire first public receipt and captured context.

The bounded response uses `studio-image-node-target-observation/1`, with the original Job and target capsule, current incarnation, small current-Canvas/history summaries, `comparison` and `automatic_actions:false`. `CURRENT_MATCH` requires both current version and digest to equal the captured target. A higher version is `CURRENT_CHANGED`, even if the definition digest later returns to its original value. Missing or inconsistent historical proof fails closed. These separate observations are not a cross-owner transaction or a reservation for later execution.

Requests are bounded to 4 KiB and responses to 256 KiB. Duplicate JSON keys and invalid/extra fields are rejected. Errors retain necessary HTTP authorization statuses with fixed safe codes, the existing application Problem JSON envelope, `no-store` and `nosniff`. A 404 is only an unavailable observation; it does not establish deletion. No candidate bytes, provider/configuration, model, Asset content, mutation, acceptance, approval or reconciliation path is called. Canvas reference checks remain original Asset metadata checks.

## Selection and display

The new task-row action captures only its currently displayed selection and a fresh selector ticket. It does **not** perform an ordinary Job GET first: such a read could provision a missing File identity before the protected observation. The single protected POST performs fresh authority/version checks, and the existing client receipt decoder compares the entire returned Job with the captured selected snapshot. A listed row alone grants no authority.

The decoded response is byte-bounded and checked against the exact project, branch, scope, capsule, history pin, current summary and comparison semantics. The helper has a 15-second bound, abort handling and actual deferred-dispatch currentness checks. Selection refresh/replacement, project/client/source/method/context changes, A/B/A and unmount retire old observations. Reactive selection retirement hides a sibling panel's old metadata immediately. Refresh is explicit; no polling or fallback to GET, overview, resolve, provider or content routes occurs.

The panel displays the Canvas ID, historical request node ID/title/coordinates, captured and current version/digest, current title/card count and matching historical target. These node facts are **historical request metadata**, not proof that a node card currently exists or that generated output has been saved. The displayed timestamp is the browser's read-completion time, not a server version token. 404/422 failures clear this observation and preserve unrelated inputs; only current 401/403 authority failures invoke the existing workspace denial path. Close or refresh cannot dispatch any task, save or restore action.

## Evidence boundary

Real File/API setup creates an original empty CanvasView and a QUEUED Job through their original metadata routes. A separate original Canvas PUT may update only its title before observation. Fresh original File owners are reconstructed in the same process; the new HTTP observation then proves unchanged or changed target state while original scope/queue/identity file bytes and metadata remain unchanged. The old exact resolver still rejects the changed target before the independent observation is tested. No approved Job or generated Asset is manufactured.

The committed frontend fixture is an exact actual HTTP capture of the changed-target case, 10,413 bytes, SHA256 `837dcd8ceacb010df5ae3678b8cd060f426ad1cdec9c129069f9588dfe845bce`. Its `baseline_commit` names the starting point, while `implementation_sha256` identifies the actual three backend files used during capture; it does not pretend the new route existed in that baseline commit. Fixed-source verification records the final implementation commit separately.

Negative cases include a higher version with the original digest, changed Job preconditions, inconsistent history/current reads, changed historical pin, a changed final Job projection, missing File identity, revoked Host and closed request limits. Injected inconsistent read projections are software counterexamples, not real concurrent commits. The missing-marker test only moves and preserves a newly created synthetic fixture marker; it does not touch user/source files. Mutation/content/provider sentinels remain active during observation.

Fixed-source frontend, File/API, type/build and independent-review results are recorded after integration. Earlier 33 known workspace test failures remain outside this bounded feature and are not repaired by it. Real model/GPU/paid execution, formal media approval → generated-result save → cold-reopen positive, PostgreSQL, native Windows and browser/geometry acceptance remain NOT_RUN. Prior media, sandbox and EACCES restrictions are not retried. Grok's window/view/keyboard work is untouched.
