# Original image-node task reopening

This records the binding checkpoint at `3e0876eccccb439ce23e520805cf58c82b6b35cc`. A subsequent slice adds explicit read-only candidate inspection; see [the candidate-preview delivery record](CLOUD_CANVAS_CANDIDATE_PREVIEW_20261023.md). The candidate-preview exclusion below describes this earlier slice.

A saved image queue task can now be reopened from its original node in either the image canvas or the professional dual canvas. Only a successful explicit queue POST can establish the UI association. The returned project, service, model and prompt must match the captured request, and collaboration responses must also match the current branch. After that check, the browser stores the returned job ID with the node ID and non-secret owner fields. It does not store task status, prompt, token or credentials in this association.

The fixed starting point was GitHub branch `cloud/canvas-task-20261023` at `4311d7c36b0da0e71e717304d210985aaad9b434`, tree `7c5e167a849e24291f0c376b280265346b5393b6`, with a clean worktree and matching remote HEAD. Implementation is in `20e2eb9d` and `5b1b8b0b`; the final checked source snapshot is `d4124cb8c8af128c7f75ad944df311c1cba1e370`, tree `4a9402e185dfff902151eddc191b68348d2ede7c`. The earlier [queue review](CLOUD_CANVAS_QUEUE_REVIEW_20261023.md) remains the record of its preceding checkpoint.

## Behavior and ownership

Select an image-generation node to see its original queued ID and server status. **刷新原任务状态** uses the existing authorized `GET /api/novels/{id}/image-jobs`, accepting exactly one matching task in the original project and, for collaboration, the matching branch. **打开原图片任务** opens the existing queue and focuses that ID. Provider configuration is not required to read an existing task. Mounting, reopening and refreshing do not create, execute, retry or accept a task.

This is a browser navigation association. The existing mature creative canvas has a separate versioned server `canvas_return` contract; that contract and its asset/source/version pins were not duplicated or weakened. The Rebuild graph remains a browser draft, and its association can be lost when browser storage is cleared. Backend authorization remains authoritative. Local File mode has no server collaboration branch isolation; its branch is null.

The association is isolated by verified local Host actor, or complete collaboration actor/workspace/project/storyline/branch identity. An anonymous or partial context cannot persist an owner association. Storage records use a strict versioned shape, reject unknown fields and malformed IDs, require the unique original image node, and are read back before reporting success. Storage failure does not cause an automatic POST retry. Node deletion, canvas unmount and identity/ABA changes retire a pending creation callback before it can attach an ID to a different source.

Editing a node prompt keeps the historical task reference visible with an explicit notice that the current prompt has not thereby been queued. State is always re-read rather than restored from a cached success label. Loading and errors clear the previous status; missing, duplicate, foreign-project/branch and unknown-status rows are not presented as verified success. Each read has an owner and sequence fence, so an older response cannot overwrite a newer read or a replacement task binding.

Independent QA also reproduced a P1 client-lifetime defect: after loading a service for one owner, an API-only client change followed by a parameter rerender allowed the old preparation panel to send a POST. The API now publishes a payload-free in-memory epoch notification. Canvas preparation/status sessions retire on that notification, and the shared queue fixes its original client epoch, clears old task data and prevents an old panel from reclaiming read/write authority. Transport, headers and credential handling are unchanged. Same-object API A/B/A transitions are covered, including fresh legitimate reads separated from retired responses.

## Locked dependency recovery

The earlier 274 TypeScript diagnostics came from reusing a `node_modules` directory installed for older main `7b35e4cb`, rather than the selected product lock. That older install lacked the current declared `@types/node@22.13.10` and `fountain-js@1.2.4`. They were not 274 independent source-code defects.

An isolated environment used existing Corepack 0.34.6 to obtain the repository-declared pnpm 10.6.5 from the standard registry, preserving signature checks. One `pnpm install --frozen-lockfile` installed 250 packages, including those exact dependencies; only repository-approved esbuild install scripts ran. `package.json`, `pnpm-lock.yaml` and `pnpm-workspace.yaml` remained byte-identical to the fixed start. No dependency or lock change was needed, and the shared old installation was preserved. The isolated environment occupies about 222.2 MiB.

Verification used a detached worktree of the exact source snapshot linked to those isolated dependencies. This avoids interpreting the old shared dependency environment's failures as failures of the recovered environment. The normal project build runs `tsc -b && vite build`.

## Verification

| Check | Observed result |
| --- | --- |
| Final canvas/queue/owner/binding and related regression | **131 passed**, 15 files, single worker, 21.49 s, on `d4124cb8` with frozen dependencies |
| New independent binding/client-lifetime group | **27 passed**, included in 131 |
| Binding module and canvas-source guard group | **19 passed**, included in 131 |
| Full standalone TypeScript check on intermediate `20e2eb9d` | **PASS**, exit 0, zero diagnostics |
| Standard final project build on `d4124cb8` | **PASS**, exit 0, full `tsc -b` followed by Vite; zero TypeScript errors, Vite 8.87 s |
| Prior real File queue HTTP checks | **4 passed at preceding checkpoint**, not rerun for this frontend-only slice; this does not establish real-File browser binding acceptance |
| Browser/geometry acceptance | **NOT_RUN this slice** because the environment's previously confirmed Chromium sandbox-helper ownership block remains; no bypass attempted |
| Restricted media-backend security review | **NOT_RUN**, no alternate route |

The frontend checks exercise real production components and the API client with explicit software HTTP fixtures. They are not live-provider or browser acceptance tests. No real generation, GPU, paid provider, PostgreSQL execution or automatic candidate adoption was run. Vite's existing large-chunk warnings remain separate from build correctness.

From a checkout with the frozen dependencies, reproduce the new binding checks with:

```sh
cd frontend
corepack pnpm exec vitest run \
  src/rebuild/image/canvasTaskBinding.test.ts \
  src/rebuild/image/CanvasImageQueue.binding.independent.test.tsx \
  src/rebuild/canvas/RebuildCanvas.taskIntent.test.tsx \
  --maxWorkers=1 --minWorkers=1
corepack pnpm build
```

The final 131-test group also includes the original queue, scope/consent, ImageRebuild wiring, Host session, writer adoption, graph insertion and handoff regressions. Cloud-only evidence is outside Git under `/workspace/cloud-development-20261023/`: `checkpoint-round3.json`, `frontend-round3-verified.log`, `build-round3-confirmed.log`, `dependency-recovery-4311.json`, `binding-independent.log` and `public-delivery-audit.txt`. Raw logs, dependency caches, runtime data and credentials are not published.

Four productive units independently handled binding/storage/source guards, dependency recovery, behavioral QA and public-content review through native `collaboration` tools. This slice does not modify external collaborators' asset-query backend or frontend layout work. Only the independent [cloud work branch](https://github.com/1785235376-blip/AI-Novel-Studio/tree/cloud/canvas-task-20261023) is the publication target; main and release state are unchanged.

Candidate result preview/adoption and durable server canvas binding are outside this slice. Local unique history/media/private project data have not been restored or made safe to delete by this work.
