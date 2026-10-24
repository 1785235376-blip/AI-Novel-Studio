# Read an exact original saved CanvasView record from its image task

Starting point: `7736423c9c261e2028d0b675935ca7b9b2482f7e`. The task center could compare the original target with a current saved summary, but could not display the actual saved cards at that observed version. Opening the existing editor would also activate its local recovery and catalog lifecycle. This slice instead adds an explicit **查看此版本关联画布** action inside the existing read-only target comparison.

## Original-owner record and boundary

`POST /api/projects/{nid}/studio/production/jobs/image/{jid}/target-view` accepts exactly `expected_version`, `expected_request_digest`, `expected_incarnation`, `expected_canvas_version` and `expected_canvas_digest`. It derives the Canvas ID, scope and actor from the original owned Job. The original Host/principal and `domain.read` checks remain authoritative; Production and Graph `existing_owner_only` contexts cover the entire invoker, including identity resolution. A missing File identity is never provisioned by this action.

The new `studio-image-node-target-view/1` result contains the exact original public Job, target capsule, incarnation and public `CanvasViewRecord`, with `automatic_actions:false`. It uses the same single original Canvas GET as the existing target observation, its history consistency and original empty-target proof, followed by the same final full Job/context comparison. It does not perform a second GET after a successful summary. The requested current version/digest must match; a later edit returns a closed error and is never substituted with the newest record. These separate owner reads provide a bounded observation, not a cross-owner transaction or a reservation.

Requests are limited to 4 KiB and responses to 8 MiB, with no truncation, `no-store`, `nosniff` and safe fixed error codes. The original summary endpoint retains its schema and 256 KiB limit. The client shares the original public Canvas record decoder without changing existing GET/history decoding. Redacted `UNAVAILABLE` cards retain no asset pin; the public definition may differ from the original stored definition hashed by `definition_digest`, so the view does not reconstruct hidden references or claim to verify that digest against projected JSON.

## Explicit display and lifetime

Only the current successful comparison can open the child panel. It captures that exact observation object, source lease, current Canvas pin and monotonically increasing parent/child tickets. Parent refresh, close or selection retirement synchronously invalidates and aborts the child before changing state. Old handlers cannot reopen it after a same-pin refresh or close a later child. Project, client, method, context or source changes, A/B/A, unmount, deferred dispatch and late responses retire old reads. The helper is bounded to 15 seconds. There is no polling or automatic retry.

The panel displays actual saved card IDs, coordinates, reference states, visible exact asset pins and saved viewport metadata. A missing request-node ID is stated explicitly. A same-ID card without matching original Job/target/asset provenance is not presented as a saved generated node. Later legitimate origin metadata is displayed as recorded, without forcing it to belong to the selected older Job. The display reads no media content, URL, provider or configuration and exposes no editor, locate, save, restore, execute, review or adoption action. It does not read or write browser recovery storage. Existing drafts remain untouched. Current 401/403 invokes the existing denial path; 404/409/422 remains a local failure and never selects another record.

## Evidence

Real File/API setup uses the original Canvas and Job routes, then reconstructs fresh original File owners in the same process. Two positive cases read an unchanged empty record and a later saved manual-reference card. The latter uses the existing synthetic asset fixture, which writes tiny fixed `application/octet-stream` bytes, followed by original Canvas PUT. This is a manual metadata reference, not an image-validity test, generated output or an approved task. The card ID intentionally differs from the requested node ID. During the new read, metadata files' bytes, inode and mtime remain unchanged; mutation, content, provider and task-operation sentinels are active, and the original Canvas GET runs exactly once.

The committed frontend fixture is an exact actual HTTP capture, **14,406 bytes**, SHA256 `59d805a4bfb98aff91b576ddbd4ce39bee248bc733d3a74774b18e7e914a9718`. Its starting `baseline_commit` and four `implementation_sha256` values identify the actual capture source without pretending the endpoint existed in the baseline. Other malformed/racing frontend receipts and statuses are software counterexamples. A simulated oversized response proves the transport bound, not a real oversized user record. The missing-marker test moves and preserves only its newly created synthetic fixture marker.

Prechecks: **14 File/API passed** in two non-overlapping selections; **32 frontend passed** in the two new files (24 unit and 8 existing-workspace integration cases), with no failed attempts.

Fixed application/test source: `e81c14855d5608b3e46eabde614c4cc5267dc71f`, tree `5a44175b9ccb65af02c7480e1c73e49b6f42aed0`. The following delivery edit changes documentation only. Final checks used a detached clean worktree and existing frozen dependencies; source and all three manifest/lock hashes remained unchanged before/after.

| Verification | Actual result |
| --- | --- |
| Original File/API | **31 passed**, 3 existing warnings, 14.40s (process 19.252s): 14 new exact-record cases and 17 original target-observation cases. Includes same-process fresh-owner reads, stale Job/Canvas/incarnation pins, intervening Canvas edit, missing identity, revoked Host and body/response bounds. No generation or approval. |
| Related frontend | **171 passed**, 9 files, one worker, 23.69s (process 24.524s). Includes the 32 new cases, previous target comparison, task selector and original Canvas client/history/panel regressions. New cases are part of 171, not an additional count. |
| Standard type/build | **PASS** `corepack pnpm build` (`tsc -b && vite build`), process 60.373s; Vite 9.88s, 2637 modules. Existing chunk-size warning only. |
| Independent review | Separate source/lifecycle/permission/owner/public-diff review and fixed-source raw receipt, XML, log and fixture hash audit; no blocking finding. Reviewer did not execute product operations. |

Earlier known workspace-suite failures and external Grok results are not rerun or relabeled by these bounded checks. GitHub source/CI is observed separately after normal work-branch push; local verification does not imply GitHub Actions ran.

Formal reviewed-result save/cold-reopen positive, real model/GPU/paid execution, PostgreSQL, native Windows and browser/geometry acceptance remain **NOT_RUN**. This slice does not establish browser Rebuild graph restoration or complete the formal generation-to-saved-node path. Existing media, sandbox and EACCES restrictions are not retried. Grok's window/view/keyboard work and protected shell are untouched.
