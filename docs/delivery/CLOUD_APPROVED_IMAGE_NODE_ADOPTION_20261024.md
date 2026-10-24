# Explicit review and browser-node adoption of an approved image

The original image node can now explicitly associate an already approved original-job asset after the user views and confirms its content. Job and Asset remain the server owners. This slice writes only the existing browser node/task binding; it does not create a server review, accept pending media, change the canvas graph, or execute a task.

## Source and user flow

- GitHub/cloud baseline: `5a6dd53ef0fd25a80af4c6c45687dcfd6ec332c8`.
- Fixed application and tests: `726fbcb5c0b293fab6d4e3047c32e62267927a4b`.
- Tested tree: `0900577592bd5581253bec0b7772f9a20b812ced`.
- The existing work branch retains the prior two-parent asset/image combination. Main and the external frontend layout are unchanged.

1. Select the original image node and explicitly preview its original task. A pending inline candidate remains read-only. An approved asset uses the original authorized, project-scoped download; no result URL is fetched.
2. An approved image must successfully load with positive natural dimensions from the exact current preview element/source. WebCrypto hashes the actual downloaded bytes. Without content hashing, the previous read-only preview remains available but adoption is disabled.
3. **准备人工核对** re-reads the original task and asset metadata and checks current write permission. The asset must match the task, project, branch, source job, provider and model. Its real positive version, content SHA-256, raster MIME and bounded size must match the viewed bytes. Metadata is re-read around the check.
4. The user checks **已查看上述图片，并确认仅采用到此浏览器的原节点** and explicitly clicks **采用到此浏览器原节点**. The client re-reads the job and asset, downloads the exact asset again, compares actual bytes/hash/MIME/size, re-reads metadata and job, then checks permission and the current node/client fence before the synchronous local write.
5. The original node/task area shows the saved browser association. Reopening reads original-owner status again and labels the association historical and not yet rechecked. It restores neither a loaded-image acknowledgement nor a checked confirmation. No preview, adoption or server write is replayed automatically.

The original `APPROVED` marker is an existing server record, not a review performed by this UI. The new checkbox records an explicit action in the current UI lifetime; it does not assert that a person actually inspected a software fixture or grant new server authority.

## Identity, concurrency and persistence

The client captures transport identity and retires work on API/Host identity epochs, scope/project changes, source prompt revisions, node removal, task-binding changes, hidden/error/replaced previews and unmount. Old callbacks cannot use a new image's load event. The actual `src/currentSrc`, dimensions, preview identity and source fence are checked again before adoption. When a load, prepare or confirmation event observes a mismatched displayed source, the preview and acknowledgement are retired; restoring the old URI cannot revive that acknowledgement. Duplicate confirmation clicks share a synchronous running guard.

Preparation, preview and confirmation each have a 15-second total deadline, captured request context and AbortSignal. The bounded download remains capped at 36 MiB. A refused, changed, failed or timed-out read clears the active confirmation and does not retry. A non-cooperative late response cannot save an association after the deadline. Abort is retirement of reads, not a claim about cancelling model execution; this flow never starts a model.

The existing strict v1 owner/node/task binding gains one optional `adoption` object containing exactly `assetId`, `assetVersion`, `assetSha256` and `jobObservationSha256`. The asset version/hash come from the real asset owner and actual bytes. The last field is a client fingerprint of observed legacy task fields, **not** a formal immutable server job revision. No prompt, result URI, object URL, token or persisted review boolean is added. A newly queued task clears the old asset association.

The local writer compares the complete expected binding, checks current identity/unique original node and the caller's fence, then verifies a read after writing. A storage error means **saving was not confirmed**; it does not prove rollback, so the UI instructs the user to re-read the original node rather than resend automatically. A previous historical association is not erased on a failed new confirmation.

This remains browser-local navigation/adoption, not server canvas persistence or cross-device history. localStorage comparison and write are not a transaction across tabs. Job, metadata, bytes and permission reads do not form a server transaction or a continuous authorization lease; the UI records the asset version/content actually observed. Later use must authorize and re-read through the original owners. The legacy local mode retains its trusted-Host/loopback boundary; collaboration requires the current actor's original NOVEL write permission.

## Verification at the fixed source

| Check | Actual result |
| --- | --- |
| Real File/API original image path | **31 passed**, 3 existing warnings, 7.97s; exit 0 |
| Bounded frontend regression | **503 passed**, 25 files, one worker, 27.73s; exit 0 |
| Standard `corepack pnpm build`, including TypeScript | **PASS**, `tsc -b && vite build`, exit 0; Vite 8.51s, process 51.531s |
| Independent fixed-source/owner and public-content review | **PASS**; observed-source acknowledgement issue found and fixed before publication |

The File/API run used `dd87bdde0cd62fd5bb9f3955419d5e7e356bfdfb`, before the final UI-only source-retirement fix. Application backend bytes, the scoped API wrapper and all Python tests are identical at the final fixed source; the 31-case run is carried forward on that byte comparison, not described as a second run. The 31 File/API cases comprise original queue 4, candidate protocol 3, explicit execution 9, and new approved-asset readback 15. The new cases verify real stored version/digest/source, metadata version changes while the job can stay identical, deletion/restoration, a replacement asset identity, exact project/branch, real session resolution and revoked grants/membership. The fixture explicitly seeds an approved row and known file. Execute, accept, provider resolution, media fetching and image inspection are guarded against invocation in the new readback tests. This is no evidence of an actual approval or generation.

The frontend group extends the previous 430-case selection: binding grows by 21 cases, plus 20 new observation/hash helpers, 29 independent component cases and 3 captured File/API protocol cases. The latter use the original real File fixture's metadata and known 68-byte payload through HTTP replay. Image load events and dimensions are explicit software fixtures; they do not prove browser image decoding or human review. Cases include changed asset/job/provenance/permission, wrong and changed image source, observed source A/B/A without a new load or acknowledgement, owner/project/client/Host/prompt ABA, different downloaded bytes, repeated clicks, storage refusal and reopen. One case invokes the production 15,000ms callback under test, observes the original AbortSignal abort and supplies a late response to verify no save or retry; it is not a 15-second wall-clock wait.

The source A/B/A regression was also tested against the preceding `dd87bdde` production code by injecting only the new test: it failed as expected because the old acknowledgement was retained. That injection was restored before testing the final source; no existing test was removed.

Existing locked dependencies were reused. No manifest/lock, backend implementation, asset query endpoint, system security or shared shell primitive changes are part of this slice. Exact commands, source receipts, XML and logs remain cloud-only under the round8 verification record; raw logs, test stores, dependencies and build outputs are excluded from Git. A following documentation-only commit does not change tested application/test bytes. Remote HEAD and GitHub CI are checked after the normal branch push; local tests do not imply CI execution.

## Remaining capability boundaries

Pending network candidates still have no supported original-owner content read in this path. The existing accept/ingestion route is separate and was not invoked or re-reviewed. This delivery neither creates pending-to-approved server review nor persists adoption to a shared server canvas. That fuller step needs an explicit mapping from Rebuild nodes to the existing versioned canvas owner and a conditional review/adoption contract; a browser hint cannot substitute for it.

Real PostgreSQL, real model/GPU/paid providers, actual Windows execution and browser/geometry/visual acceptance are **NOT_RUN**. The existing Chromium sandbox-helper ownership block was not retried or bypassed. Earlier restricted media safety review was not rerun. Windows support for the new asset-query cursor remains unsupported/unverified; the prior explicit-mode refusal and old offset compatibility boundaries still apply. The inherited upstream EOF blank-line finding and existing build chunk warning remain tracked separately from this slice's clean diff check.
