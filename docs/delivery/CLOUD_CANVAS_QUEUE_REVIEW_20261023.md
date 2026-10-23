# Cloud canvas queue review and handoff

The selected image node can prepare a prompt for the existing persistent image queue. Saving requires an explicit service/model choice and, where applicable, current cloud-prompt consent. A saved task displays the server's job ID. Reading, saving, cancelling and executing remain separate actions; opening or reopening the panel does not execute a job.

This follow-up starts at `4b5c8aa259c4432102e9e6d2a173ec52c789ad94`, tree `71b13a6d2a9e01ad4f269e64c9e7e3d3e716fd51`, with a clean worktree. Its parent is the GitHub Hermia baseline `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`. All changes derive from GitHub source in the selected cloud environment; no Windows source, local migration package, private local history, model or credential is included. The first-slice behavior and observed remote heads are recorded in [the original delivery record](CLOUD_CANVAS_IMAGE_QUEUE_20261023.md).

## Independent review and fixes

An independent reviewer reproduced old save/execute callbacks surviving an identity transition, including a same-batch A/B/A transition. A verified local-host session change also left the old private queue visible, and an API-client-only rebind allowed old provider metadata to return. The implementation now checks the current store scope, actual API-client identity and monotonic client/session epochs before requests and before applying results. Permission failures retire visible jobs and prevent further writes from that owner. Pending duplicate clicks are rejected synchronously.

Changing the selected service, model or consent synchronously invalidates an old confirmation callback, including changes before React commits a new render. Provider metadata and queue responses from retired owners cannot populate the current panel. These are in-memory lifecycle guards, not new credentials or transport changes.

The existing queue already supported reading statuses and focusing a requested task ID, so that interface was reused. A new regression exposed an older GET response overwriting a newer cancellation result. A per-owner read sequence now accepts only the latest read and its error. Reopening reads persisted server state without creating or executing a task.

Small existing type-check defects were also repaired: the writer's primary adoption action uses the existing `COMPLETED` state mapping and passes its authorized original job to the existing version-aware handler; drag MIME detection uses the actual iterable contract; handoff module literals are narrowed without changing their values/order; Vite ambient declarations reference the already installed package. No layout, theme, asset-query API, dependency manifest or lockfile was changed.

## Observed validation

| Check | Result |
| --- | --- |
| Queue, canvas wiring, scope/permission/ABA/consent and readback regression | **55 passed**, 9 files, single worker, 8.24 s |
| Independent reviewer portion of that queue group | **21 passed**; included in 55, not an additional count |
| Writer adoption, graph insertion, module gate and handoff regressions | **37 passed**, 4 files, single worker, 11.36 s |
| Real File repository and HTTP queue persistence/readback | **4 passed**, 4.26 s; provider resolution and media execution sentinels both remained unused |
| Vite production bundle alone | **PASS**, 8.93 s; existing large-chunk warnings remain |
| Full TypeScript check on isolated GitHub `6ba25ad7` | **FAIL**, 280 diagnostics; identical to the starting `4b5c8aa` output |
| Full TypeScript check on final reviewed source | **FAIL**, 274 diagnostics; remaining diagnostics match the classified dependency-related set |
| Three-viewport browser and geometry checks | **BLOCKED before test bodies**, 0 acceptance passes: Chromium SUID sandbox helper ownership is invalid in the environment |
| Previously restricted media-backend security review | **NOT_RUN**, no alternative route attempted |
| Whitespace/diff checks | **PASS** |

The 274 remaining TypeScript diagnostics comprise 181 Node built-in imports, 2 `fountain-js` imports, 70 Node global declarations and 21 related implicit-type errors. This environment lacks the declared `@types/node@22.13.10` and `fountain-js@1.2.4`. No package was installed, lockfile changed or different runtime version substituted. The normal package build includes TypeScript and therefore is not reported as passing; only Vite bundling passed.

Frontend checks use clearly identified software HTTP fixtures and real components/API calls. They do not establish live-provider or real-File browser acceptance. The four backend checks separately use the actual File repository, queue service and HTTP routes. They cover server IDs and saved parameters, same-key parameter conflicts, cancelled state surviving a new owner/client, and separate project queues. In this legacy File/local mode, `X-Branch-Id` is ignored and stored `branch_id` is null: these tests prove project partitioning, **not server-side collaboration branch isolation**.

Reproduce the queue group from `frontend` with existing installed tools:

```sh
node node_modules/vitest/vitest.mjs run \
  src/rebuild/canvas/RebuildCanvas.test.tsx \
  src/rebuild/canvas/RebuildCanvas.taskIntent.test.tsx \
  src/rebuild/image/CanvasImageQueue.test.tsx \
  src/rebuild/image/CanvasImageQueue.independent.test.tsx \
  src/rebuild/image/ImageDualGate.test.tsx \
  src/rebuild/image/ImageRebuild.canvasQueue.test.tsx \
  src/novel/ImageQueuePanel.test.tsx \
  src/novel/ImageQueuePanel.readback.test.tsx \
  src/localHostSession.test.ts \
  --maxWorkers=1 --minWorkers=1
```

The four additional frontend files are `src/AppBrokerRecovery.test.tsx`, `src/creative/GraphCanvas.insertion.additive.test.tsx`, `src/ui/ModuleStartGate.test.tsx` and `src/ui/handoffSmoke.xUx10.test.tsx`. Backend checks are in `tests/test_cloud_canvas_image_queue.py`, using isolated temporary roots, File storage, disabled cloud dispatch and the existing Python environment. No dependencies were installed.

Cloud-only evidence is kept outside the Git deliverable under `/workspace/cloud-development-20261023/`: `queue-final.log`, `ts-baseline-final-targeted.log`, `file-queue-readback.log`, `build-round2.log`, `typecheck-round2-tip.log`, `ts-baseline-classification.json`, `visual/results.json` and `checkpoint-round2.json`. Raw logs, runtime data and installed dependencies are excluded from the branch. Four productive independent units were coordinated through `collaboration.spawn_agent`; no separate Cloud Codex developer-launch endpoint was available or claimed.

## Handoff and remaining limits

The delivery target is the independently named GitHub branch [`cloud/canvas-task-20261023`](https://github.com/1785235376-blip/AI-Novel-Studio/tree/cloud/canvas-task-20261023), under the user's authorization to publish checked cloud-derived work. Publication is a source handoff, not product acceptance. Main, release state, security settings and external collaborators' asset-query/backend and UI-layout work are outside this change.

Browser verification requires a correctly provisioned sandbox helper; no sandbox bypass or ownership change was attempted. Missing declared dependencies block the full type check. GPU, paid providers, PostgreSQL and real inference were not run. The canvas remains a browser draft without a durable server canvas/card/job binding; video nodes are not wired to dispatch. Duplicate-click suppression and backend same-key tests do not prove exactly-once recovery from an uncertain POST response. Local commits, full Git history, media and private project data have not been restored, so this branch does not justify deleting local unique data.
