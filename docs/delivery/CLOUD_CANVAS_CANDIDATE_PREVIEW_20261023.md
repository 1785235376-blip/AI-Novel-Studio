# Original-node image candidate inspection

Historical checkpoint: the [subsequent File/API content handoff](CLOUD_CANVAS_FILE_CANDIDATE_20261023.md) supersedes the raw-URI preview behavior below. Current node previews use strict inline data or the original asset content API; the original queue comparison is metadata-only.

An original image-generation node can now show the completed task's candidate source information and explicitly preview its result. The panel uses only the existing authorized image-job owner. Opening the node reads metadata; clicking **预览原任务候选结果** re-reads the exact original job and compares the observed snapshot before attaching an image URI. No execute, retry, accept, asset-write or graph-write operation is added to this path.

The fixed clean start and observed remote HEAD were `3e0876eccccb439ce23e520805cf58c82b6b35cc`, tree `c1e32721a5d9d38f0f88ec8c354cb7495f1d7e00`. The checked code/test snapshot is `d5774f9953ebf75efe8c16067700649d75061ed3`, tree `7ce675d43a8ecc926f07af8258bb7e8f540ad80e`. Source is GitHub-derived cloud work; no Windows source or migration-package contents were used. The preceding [node-binding record](CLOUD_CANVAS_NODE_BINDING_20261023.md) remains a historical checkpoint.

## Existing capability and its limits

| Existing capability | Use in this slice |
| --- | --- |
| `GET /api/novels/{id}/image-jobs` | Original authorized list read, exact bound job ID, project and collaboration actor/branch checks |
| Completed legacy row fields | Candidate URI, provider/model, original prompt, request digest, attempt, updated time and recorded approval/asset ID |
| Existing explicit execute and accept POSTs | Remain separate original queue operations; not called by the candidate view |
| Formal task version, candidate-specific GET, output-byte digest | Not present in this legacy contract; not invented here |
| Server Rebuild canvas/node binding | Still absent; the preceding browser navigation binding is reused |

`request_sha256` describes the original input, not the result file. `attempt` is an execution count, and `updated_at` can also change when a result is accepted. Their combination with the URI and other displayed fields is an **observed task snapshot**, not an immutable server revision, file-integrity proof or new authorization. File/local rows have no collaboration branch, and do not acquire server actor privacy from the browser's local Host association.

## Behavior and lifecycle

Only a completed legacy row with matching original identity and complete source metadata becomes a candidate view. Pending and approved records are distinguished using the server's approval fields; an approved record must also supply its asset ID. The view presents the original node/job/project, provider, model, prompt, input digest, execution attempt and task update time. A changed draft prompt is explicitly identified as separate from the historical task. Nothing writes a candidate or its prompt back to the graph.

The preview button makes another original-owner GET. The same exact row and all checked snapshot fields must still match. A changed, missing, duplicated, unreadable, cancelled or retrying task invalidates the old candidate, clears its displayed source/status and requires a fresh read. Owner/client/Host/ABA changes, task-binding replacement, external storage notifications and node-source retirement also invalidate it. Starting a parent refresh synchronously retires the old preview even before React commits. Node prompt edits increment an in-memory source revision synchronously, including a same-batch A/B/A edit, so an old preview confirmation cannot be reused.

The image element is absent until explicit preview succeeds. The existing URI helper is reused with local syntax guards against control characters, backslashes, URL user information and malformed protocol/origin parsing. Unsupported or missing result addresses leave source information readable and preview disabled. The raw URI is kept only in memory for comparison and the explicit image source; it is not placed in visible text, links, titles, logs or storage. No URI is reconstructed from a guessed asset ID. The new code does not fetch or decode media bytes itself.

The image uses `no-referrer`. This does not guarantee anonymous transport, absence of redirects or cookies, continuous authorization, or media safety. A protected/expired address may fail to display; the panel reports that failure and preserves the previously read source record. It does not bypass authentication or fall back to generation, acceptance or another download route. A preview read denial instead clears the candidate source as well as the image.

## Integration boundary

- `CanvasNodeTaskStatus` reads and holds the current source snapshot; `CanvasTaskCandidateView` performs explicit revalidation and display. The pure `canvasTaskCandidate` module validates/projects only known fields.
- `RebuildCanvas` and `DualCanvas` extend the existing optional renderer callback to `(node, isSourceCurrent, sourceRevision)`. The image entry forwards those values and the current draft prompt; no CSS, shell, theme or layout change is introduced.
- `useCanvasTaskBinding` includes storage notifications in its session retirement key. No new persistent binding fields, credentials, backend owner, API endpoint or dependency are added.
- External asset-query performance/pagination and frontend layout work are outside this slice. The asset-query branch is not merged here.

## Observed validation

| Check | Result |
| --- | --- |
| Combined targeted regression on exact `d5774f99` | **208 passed**, 17 files, single worker, 23.55 s |
| New pure candidate-contract portion | **53 passed**, included in 208 |
| New independent candidate interaction portion | **24 passed**, included in 208 |
| Previous targeted frontend portion | **131 passed**, included in 208 |
| Standard project build (`tsc -b && vite build`) | **PASS**, exit 0; full TypeScript phase succeeded, Vite 9.73 s; existing large-chunk warnings remain |
| Browser/geometry acceptance | **NOT_RUN this slice**, known environment sandbox-helper ownership block remains; no bypass |
| Real inference, GPU, paid provider or PostgreSQL | **NOT_RUN** |
| Previously restricted media-backend security review | **NOT_RUN**, no alternate route |

Frontend tests use real components/API calls and clearly identified software HTTP fixtures. Candidate images and signed-query examples in tests are synthetic fixtures; they are not presented as generated production results. URI tests exercise only the frontend projection/syntax rules, not backend media security or image-byte validation. No original queue/File tests are being recounted as live candidate acceptance.

Validation reuses the unchanged frozen dependency environment from the preceding slice: repository-declared pnpm 10.6.5, existing Corepack and the existing isolated lock-resolved packages. Manifest, lockfile and approved-build settings are unchanged; no installation was needed in this slice.

Reproduce the two new groups from `frontend` with the declared environment:

```sh
corepack pnpm exec vitest run \
  src/rebuild/image/canvasTaskCandidate.test.ts \
  src/rebuild/image/CanvasNodeTaskCandidate.independent.test.tsx \
  --maxWorkers=1 --minWorkers=1
corepack pnpm build
```

The combined 17-file group includes those groups and all 15 files listed in the prior node-binding verification. Cloud-only evidence is under `/workspace/cloud-development-20261023/`: `checkpoint-round4.json`, `frontend-round4-final.log`, `build-round4-final.log`, `candidate-contract-owner-final.log`, `candidate-independent.log` and `public-delivery-audit.txt`. Raw logs, URI-bearing runtime data, caches and installed dependencies are excluded from Git.

The source handoff targets the existing independent [cloud branch](https://github.com/1785235376-blip/AI-Novel-Studio/tree/cloud/canvas-task-20261023). Publication is not whole-product, live-provider or browser acceptance. Main and release state remain outside the change, and local unique history or project data have not been restored or made safe to delete.
