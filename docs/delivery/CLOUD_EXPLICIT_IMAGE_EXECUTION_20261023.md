# Explicit execution of one original image task

An already queued image task now has a separate, reviewed execution confirmation. Opening a node, changing a template, saving a task or reading its status never dispatches it. The review shows the original job/project/branch, provider, model, prompt and parameters, and warns that cost is unknown and may include service fees or local compute. The author must explicitly acknowledge this one task before the original execute API is called.

The fixed clean start was `8738ecb2ecd667dd9d401c4c16c2136f812e2a17`, tree `596aa8510fa91fea93e58ab93560fe7b1570db20`. The final checked code/test snapshot is `e5e7a23b4b896511f09029cb52456c0b43c8af17`, tree `585102aa2b448161f63250a00f15be69092a7ce4`. It derives only from the GitHub/cloud line. No Windows files, migration-package source, new credentials or external paid service were used.

## Original owner and conditional execution

The legacy original owner already supports queue, execute, cancel and retry. Its old execute route did not bind a caller's reviewed inputs. This slice adds an optional precondition to that **same** route and owner; it adds neither another executor nor another job store.

`GET /api/novels/{nid}/image-jobs?execution_confirmation=1` opts into the additive `execution_confirmation: legacy-image-confirmation/1` marker. The ordinary GET keeps its existing `{items}` shape. The marker advertises this request contract, **not** permission, model readiness, a price or a formal task version. A server that ignores the query lacks the marker, so the new UI disables dispatch instead of assuming that an old server will enforce a new body.

An explicitly confirmed POST sends only:

```json
{
  "confirmed": true,
  "expected_request_sha256": "<the original input digest>",
  "expected_attempt": 0,
  "expected_updated_at": "<the original observed update time>"
}
```

Authorization stays in the original route before confirmation validation. Under the original owner's mutation lock, the claim requires QUEUED, compares those three observations, and independently rehashes the current input fields. A mismatched input, attempt or update produces fixed `409 IMAGE_JOB_CONFIRMATION_STALE` before provider resolution or state mutation. Matching execution uses the original provider, authorization/egress checks, attempt token and completion handling. No-body/null old callers retain their original behavior; this is not a universal confirmation policy for all older clients.

The request hash remains an input digest. Attempt/update preconditions are observed state, not a new persisted revision, output checksum, remote idempotency guarantee or proof that no intervening identical state ever existed.

## Capability and confirmation lifecycle

The UI supports only the known manual text-to-image contract, without reference images. The exact original row must match the current owner/project/branch/actor. A unique provider must be configured, registered, explicitly reachable, have a known adapter style and match the job's model to its current configured default. Parameters must be supported by that adapter. Unsupported models, custom/unknown adapter capabilities or incomplete rows remain unavailable rather than being guessed.

Collaboration additionally reads the original NOVEL `domain.write` summary for the exact actor and current scope. The original execute route still authorizes at dispatch. Local UI use requires the already verified Host identity, while the local backend retains its existing loopback boundary; the new UI does not create actor-private local server storage. Provider readiness/default-model configuration does not prove that a particular model is loaded, works correctly or has a known price.

Preparing the review and final confirmation each read the original task, provider configuration and applicable permission using a captured client context. Final dispatch requires the same checked input/configuration. Client/Host/scope changes, old replies, parent refresh, job changes, selected service/model/consent changes and queue parameter edits retire the review. In-memory revision guards also cover same-batch A/B/A changes. The payload always refers to the stored job; a different current draft is never substituted into its execution.

## Unknown outcomes and recovery

Before POST, the browser must write and read back a minimal pending marker. It contains stable owner/job identity in its key and only schema, job ID, input digest, attempt, update time and an operation UUID in its value. It contains no prompt, parameters, token or result URI. Missing storage, failed writes or malformed markers block dispatch. Marker schema/type validation is strict, including the digest's string type.

A 30-second client wait aborts the HTTP request, **not the provider**. Network errors, timeout, a lost response or closing the view leave the marker. Reopening the same original queued snapshot cannot blindly dispatch it again. The author can read the original task and use its existing status/cancel/requeue recovery actions. When a fresh owner read supplies a different conditional snapshot, another execution still requires a new explicit confirmation. No automatic execute, retry, cancel, accept or bulk action is added.

The marker is a recovery aid, not an execution receipt or authorization. `localStorage` comparison/removal is best effort and is not an atomic cross-tab lock. The server's locked conditional claim is the dispatch guard. This does not guarantee exactly-once remote work, stop an already issued model call, create a cross-provider transaction, or retain recovery if the user clears browser storage. An original owner marked recoverable/FAILED likewise does not prove that a remote service performed no work.

## Actual File/API evidence

`tests/test_cloud_canvas_explicit_execute.py` uses the existing File owner, original HTTP routes and repository `Automatic1111ImageProvider`, injected with an in-memory synthetic transport using the repository's established adapter-test pattern. No new production provider or executor is introduced. It checks real queue → authorized original reads → explicit conditional execute → completion/read/reopen, repeated execution rejection, delayed RUNNING reads, synthetic timeout behavior and stale conditions with zero dispatch. Another test proves the additive capability response leaves the ordinary GET unchanged.

The captured `frontend/src/creative/fixtures/cloud-canvas-execute.file-api.json` is labeled `ORIGINAL_FILE_EXECUTE_WITH_SYNTHETIC_MEMORY_TRANSPORT`. Its SHA-256 is `85b7a31231fb112cca1568200fcdfc5f560703058a3ddfccc685723e1d046fe5`. It contains the actual conditional request, opt-in response and original completion from one synthetic transport call. Its execution token is the test attempt's concurrency nonce, not an authorization credential. Its request digest and inline image are not production output-quality evidence.

The frontend consumer imports that capture directly and confirms its original task through the real client/components; its provider-readiness reply is explicitly a separate software fixture. The resulting task remains PENDING review. No accept, asset promotion, image inspection, media downloader, real network model, GPU or paid inference was invoked. Reopening a File owner in process is not a process-crash or real-provider recovery experiment.

## Verification and remaining scope

| Check | Actual result |
| --- | --- |
| Final fixed-snapshot frontend regression | **430 passed**, 22 files, one worker, 30.35s |
| Included prior targeted regression | 269 passed |
| Included new pure execution rules | 120 passed |
| Included independent execution lifecycle/transport | 40 passed, including actual client timer, same-batch parameter A/B/A and malformed pending markers |
| Included original File execution capture consumer | 1 passed |
| Original File/API combination | **16 passed**, one worker, 5.28s: 4 queue + 3 candidate protocol + 9 execution; 3 existing warnings |
| Standard `tsc -b && vite build` on final code snapshot | **PASS**, zero TypeScript errors, Vite 8.92s; existing large-chunk warnings |
| Browser/geometry | **NOT_RUN**, known sandbox-helper ownership block; no bypass |
| Restricted media safety review, real model/GPU/paid inference, accept/ingestion, PostgreSQL, GitHub Actions | **NOT_RUN** |

The final frontend groups and build ran in a detached worktree at `e5e7a23`. The File/API run preceded the code commit; its API, owner and all three test-file byte hashes were unchanged before/after the run and match this exact commit. The later marker fix touched only frontend source/testing, so the unchanged backend suite was not rerun. The checkpoint records these hashes explicitly. Counts include overlapping component groups; prior preliminary runs are not added to the final totals.

Verification reuses the existing frozen repository-declared pnpm environment. No installation, manifest/lock update or runtime security change was performed. Slice-specific commands from a configured environment are:

```sh
# From frontend:
corepack pnpm exec vitest run src/novel/imageJobExecution.test.ts \
  src/novel/ImageQueuePanel.execute.independent.test.tsx \
  src/novel/ImageJobExecute.file-api.test.tsx --maxWorkers=1 --minWorkers=1
corepack pnpm build
# From the repository root:
python -m pytest tests/test_cloud_canvas_image_queue.py \
  tests/test_cloud_canvas_candidate_protocol.py \
  tests/test_cloud_canvas_explicit_execute.py -q -p no:cacheprovider
```

Exact cloud commands and hashes are retained in `/workspace/cloud-development-20261023/checkpoint-round6.json`, `frontend-round6-final.log`, `build-round6-final.log` and `explicit-execute/combined-16.log`. Logs, test stores, model/runtime data, dependencies and build outputs are not uploaded. Browser/geometry remains blocked as described above; no security setting or `--no-sandbox` workaround was used.

The [flow ledger](CLOUD_IMAGE_FLOW_LEDGER_20261023.md) is updated. The independent [pending-candidate content proposal](CLOUD_PENDING_CANDIDATE_PROPOSAL_20261023.md) is **design only**: it uses the original owner and already-held inline content, explicitly refuses remote URL acquisition, and leaves validator/locking/admission details for a separately authorized implementation. No network proxy, SSRF surface, credential forwarding or parallel candidate owner was added.

External asset-query work was independently reviewed at its own fixed commit and is not merged into this slice. Frontend layout, server canvas persistence, node adoption and full historical restore remain outside this change. Publication to the independent cloud work branch does not represent whole-product acceptance or make unique local data safe to delete.
