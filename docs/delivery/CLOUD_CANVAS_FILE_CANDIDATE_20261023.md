# Original File/API candidate content handoff

The original-node candidate view now consumes the actual legacy File/API response shape. Approved results are read through the original asset download endpoint instead of loading `asset_uri` as an image URL. Pending candidates support only strict embedded raster data; remote candidates show source information and the missing content capability. The old queue comparison area also stops loading raw result links and displays source metadata only.

The fixed clean start was `1c19d81ddc55043a9bd908af6ddb56cda71e5186`, tree `5fbf4cc585fb1975eb44897442668de943ff61aa`. The verified code/test snapshot is `381c34ee26e3d6bc3e80dd64c894e7cc7a52ec77`, tree `4d073de2c76bb24f1efefa83e501d36bfa5f88e8`. All source is derived from the public GitHub baseline and cloud work; no Windows files or local migration package were read.

## Actual protocol and content evidence

`tests/test_cloud_canvas_candidate_protocol.py` uses the existing `ImageJobService` owner and File persistence. Test setup explicitly stores synthetic completed and approved states with `_mutate`; it does **not** execute a provider or accept a result. It creates a known synthetic file through the existing asset library, reads the original task/asset endpoints, reopens the File owner and checks the original download bytes and response headers. Execute, accept, media parsing and external candidate-fetch sentinels must remain uncalled.

The captured fixture at `frontend/src/creative/fixtures/cloud-canvas-candidate.file-api.json` is 4,396 bytes, SHA-256 `6c718698f054f339cdb0fa13d77940ced76ecfbd79bc768c21a0fe9ba643ddb8`. It carries `EXPLICIT_SYNTHETIC_OWNER_STATES_NO_EXECUTION_OR_ACCEPT` and the original envelopes:

- Both rows retain `status: SUCCEEDED`. The pending row has `approval_status: PENDING` and `asset_uri`; the synthetic approved row adds `asset_id` and `approved_at` while changing the approval marker.
- The original content route returns 68 known bytes, SHA-256 `e6fa51b216b95e6bf68e0225a622038749c4f3ddc87d33cfdca62386641c59b1`, with its actual content type, length, disposition, asset digest and nosniff headers.
- The frontend fixture-consumer test imports this capture directly and replays its original GET/download responses through the real client and node components. It does not hand-invent a production candidate schema.

These are protocol and data-path observations. They do not prove actual generation, approval, media safety, provider quality or collaboration-session authorization. The fixture's asset version and byte digest describe that synthetic asset only; neither is presented as a formal legacy job version or output proof. Actor/branch partition checks exercise the existing File owner, separately from HTTP collaboration authorization.

## Preview transport and compatibility

An approved preview requires the exact original task snapshot and server-returned asset ID. The explicit action re-reads the task, downloads only that asset through its fixed original API path, then re-reads the task again. The captured context supplies the existing session/branch headers. Asset download opts into `redirect: error`, `credentials: omit`, `cache: no-store`, `no-referrer`, cancellation and the existing fixed-buffer bounded-response helper with a 36MiB cap. Error bodies are cancelled without parsing or displaying arbitrary server content. Only a nonempty raster MIME response can become a temporary object URL.

Hiding, unloading, refreshing or retiring the owner/source invalidates pending replies and revokes an allocated URL. A denied download, unsupported content or changed final job read clears the candidate instead of falling back to its result address. Existing API callers retain their original behavior unless they opt into the new download context/options; the original backend, owner and routes are unchanged.

Pending inline data must match a complete raster/base64 syntax and the existing URI size bound, and still requires an explicit matching task re-read. HTTP, HTTPS, relative and returned blob URLs are retained only for in-memory snapshot comparison; they are never attached to an image or rendered as a link by these entries. Existing queue execute and accept actions remain explicit and separate. The comparison area no longer previews even inline images: tasks without a browser node association currently have no preview there. This capability reduction is deliberate and covered by tests.

The job/download/job reads are independent operations, **not a transaction**. Download returns the current readable content of that asset ID, not a pinned historical candidate version. Only the asset download opts into redirect rejection; the unchanged generic JSON client keeps its existing behavior. Ordinary local mode retains its original loopback access boundary, which does not authenticate an actor or provide actor-private assets. Collaboration uses the original session, project and branch checks. Pixels already delivered cannot be continuously revoked by this UI.

The unrelated existing `api.asset(id)` helper omits the metadata endpoint's required `novel_id`; this path does not use it. Fixing that helper's other consumers is outside this slice.

## Validation

All final checks ran on the fixed `381c34ee` worktree using the previously restored, repository-declared frozen dependency environment. No dependency installation, manifest/lock update or system/security configuration change was needed.

| Check | Actual result |
| --- | --- |
| Targeted frontend regression | **269 passed**, 19 files, one worker, 28.18s |
| Included pure candidate contract | 66 passed |
| Included independent interaction/transport group | 48 passed |
| Included original File/API capture consumer | 2 passed |
| Included bounded-response helper regression | 19 passed |
| Original File queue plus new protocol tests | **7 passed**: 4 existing queue + 3 new protocol, 5.86s; 3 existing warnings |
| Standard `corepack pnpm build` (`tsc -b && vite build`) | **PASS**, exit 0, zero TypeScript errors, Vite 9.07s; existing large-chunk warnings |
| Browser/geometry | **NOT_RUN**, known sandbox-helper ownership block; no bypass or security change |
| Provider/GPU/paid generation, accept/media ingestion, restricted media security review, PostgreSQL, GitHub Actions | **NOT_RUN** |

From `frontend`, the slice-specific frontend groups can be run with the declared pnpm environment:

```sh
corepack pnpm exec vitest run \
  src/rebuild/image/canvasTaskCandidate.test.ts \
  src/rebuild/image/CanvasNodeTaskCandidate.independent.test.tsx \
  src/rebuild/image/CanvasCandidate.file-api.test.tsx \
  src/novel/ImageQueuePanel.test.tsx src/boundedResponseBlob.test.ts \
  --maxWorkers=1 --minWorkers=1
corepack pnpm build
```

From a configured existing Python environment at the repository root:

```sh
python -m pytest tests/test_cloud_canvas_image_queue.py \
  tests/test_cloud_canvas_candidate_protocol.py -q -p no:cacheprovider
```

The exact cloud commands, hashes and test logs are recorded privately in `/workspace/cloud-development-20261023/checkpoint-round5.json`, `frontend-round5-final.log`, `build-round5-final.log`, and `candidate-protocol/file-api-final.log`. Runtime stores, raw logs, installed dependencies and build outputs are not included in Git.

## Remaining product scope

The [image-flow ledger](CLOUD_IMAGE_FLOW_LEDGER_20261023.md) records creation → queue → execution → candidate → review/adoption → history recovery. Its next useful proposal is a minimal read-only legacy-owner content contract for already-held pending candidates, with explicit unavailable behavior; no arbitrary fetch proxy, acceptance fallback or parallel owner was implemented. Browser-local task navigation is not server canvas/history restoration. External asset-query work and frontend shell redesign are not merged here.

This handoff targets the existing independent [cloud work branch](https://github.com/1785235376-blip/AI-Novel-Studio/tree/cloud/canvas-task-20261023). Branch publication is not whole-product acceptance or authorization to delete unique local history/data.
