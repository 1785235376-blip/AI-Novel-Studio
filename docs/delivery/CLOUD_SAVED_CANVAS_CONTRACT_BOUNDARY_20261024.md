# Existing saved-canvas verification and the legacy adoption boundary

The original saved display-canvas owner has been checked, with permanent regression tests and a small fix to its existing Save action. **The Rebuild generation-node/legacy-result association is still browser-local.** No admission adapter, node migration, new canvas owner or database is implemented by this delivery.

## What exists and what was verified

| Path | Actual capability and evidence |
| --- | --- |
| Original saved display canvas | `CreativeCanvasViews` already supports create, list, get, save and version history under `creative_canvas_views_v2`. Cards retain original ID/position and an exact `asset_id/version/digest/kind` pin. New real File/API tests verify manual-asset card Save and cold reopen through the mounted original routes. |
| Original formal production result return | `CanvasImageTaskReturn` already verifies an APPROVED original production Job and its formal Asset, targets its captured original card and calls the original conditional Save. Its existing frontend fixture is software HTTP replay; it does not establish a new real File review/ingestion result. No new return action is added here. |
| Rebuild generation nodes and browser journal | `CvGraph` stores node types, titles, prompts and edges in browser storage, with a separate owner-scoped browser task/adoption history. There is no server CanvasView ID/card mapping for these nodes. They were not silently converted or synchronized. |
| Legacy approved generated asset | A readable original legacy Job may say APPROVED and point at a real Asset. That alone is insufficient for Studio admission: the original Workspace requires formal production provenance for an asset with `source_job_id`. The new File negative test verifies rejection without partial canvas/job writes. |

The real File positive cases use **manual registered Asset cards**, not reviewed formal generated results. An original Job's synthetic APPROVED marker is explicit negative-fixture setup; no formal origin is fabricated. A complete real File approved-production-result Save/reopen chain is **NOT_RUN** in this slice because no complete reusable approved owner state was supplied that avoids the previously restricted review/media work.

## Existing Save defects fixed

The general **保存媒体画布** update previously called only `save(id, version, definition)`, although the original client/API already support origin conditions. For an **existing saved base with a supplied verified `draftOwner`**, it now also passes the actual `expected_incarnation` and captured `expected_definition_digest`. The base project and scope must match that owner. Invalid provided incarnation/scope/digest is refused before mutation, keeping the input. It does not invent an incarnation from a browser node or Job ID.

The serialized draft owner now participates in callback retirement, and a component cannot reuse its first owner under a replacement owner. Owner/project/client A/B/A and late results cannot publish an old success. A task handed to a parent read/mutate wrapper rechecks its captured authority when that wrapper actually invokes it, rather than relying only on the earlier button click.

Independent testing found another real defect: after the first PUT failed with an unknown outcome, invoking a previously captured Save callback sent a second PUT despite the displayed disabled button. A pure published-baseline counterexample records that failure. A synchronous unknown-write ref and immediate callback retirement now block both the entry and deferred request. The original input remains visible; no success is shown and no automatic or retained-callback retry is sent. The existing explicit list/read and confirmed draft-discard/replacement paths remain available.

New create requests keep their original contract. A caller without `draftOwner` keeps the old version-only compatibility behavior; it is **not** counted as the new strong-origin path. Generic whole-view Save does not add `expected_card`; the existing formal single-card return already uses that separate source-card condition. No server DTO, permission, admission rule, mutation owner or storage collection is changed.

## Exact compatibility gap

| Interface | Current requirement | Why the browser association cannot stand in for it |
| --- | --- | --- |
| `CanvasViewDefinition` / `CanvasAssetCard` | Strict display definition: title, cards, viewport and optional groups/options; each writable card has a position and actual Asset pin. | Rebuild `t/title/prompt/edges` and task journal are absent from this schema. Saving the whole Rebuild graph would be lossy or invalid. |
| `CanvasViewSave` | `expected_version`; paired optional `expected_incarnation` and `expected_definition_digest`; optional `expected_card` requires that pair. | Browser journal revisions and node IDs are not server versions, incarnation, view ID or original card identity. Ordinary GET supplies version/digest; verified overview/draft owner or history supplies incarnation. |
| Workspace Asset admission | For `source_job_id`, `_studio_result_origin.contract == studio-production-result/1` with correct job, original scope/incarnation and provenance. | Legacy `ImageJobService.accept` records source job/provider/model/parameters/approval time, but not this formal production-origin contract. Correct legacy Asset version/SHA does not satisfy it. |

The internal unsupported-source reason is `CREATIVE_ASSET_ADAPTER_REQUIRED`. Canvas metadata state becomes `UNAVAILABLE`; create/save then return a source-change rejection (409). Tests use the actual original service and HTTP routes and verify unchanged persisted scope/job state. Client-supplied origin labels or copied production receipts are not a remedy.

The Rebuild graph storage key is only kind/project based, while its task binding is separately owner scoped. The entire loaded browser graph must not be treated as an authenticated actor/branch/incarnation-owned server definition. This delivery does not add a misleading “saved to server” state to Rebuild.

## Minimum later contracts — not implemented

1. Choose an explicit original-owner admission policy for legacy results, or use the already compatible formal production path. Any adapter must resolve and verify the current original Job/Asset, approval, authorization, project/scope/incarnation and exact asset pin under those owners. It cannot accept client-origin metadata as production authority or bypass existing media/provenance validation.
2. Define an explicit, versioned mapping from a representable browser selection to an existing saved view/card, using real original-owner IDs and CAS conditions. Decide what happens to generation-node drafts, prompts and edges that are not asset-display cards. The existing `studio-canvas-return/1` capsule demonstrates the formal path's original-card binding; a browser journal cannot replace it.

These are interface gaps and a necessary scope decision, not completed functionality or permission to build a parallel migration system.

## Verification receipt

Cloud/GitHub starting point: `abb62695ba7f29b614dca58c48ae115277658963`. Fixed application/test source: `0e5f06f8c9272e4e0b5abf642557139692691493`, tree `84e7fa9ae099785b64a93e49fee08b962df44676`. A later delivery-document commit does not change those tested bytes.

| Check | Actual result |
| --- | --- |
| Original File/API Save/cold-reopen and refusal tests | **6 passed**, 3 existing warnings, 7.60s at `4937eeb740c1d2ca7f0794c99d69ac04a9853f8c`; following change is test-fixture-only, relevant backend/API/Python bytes unchanged |
| Related frontend selection, including new 12-case independent Save regression | **131 passed**, 13 files, one worker, 23.20s at the fixed source |
| Standard `corepack pnpm build` | **PASS**, `tsc -b && vite build`; process 49.285s, Vite 8.53s at the fixed source |
| Independent fixed-source review | **PASS**; final delivery documentation separately reviewed before publication |

The six File cases exercise original mounted POST/PUT/GET/history, rebuild actual File Asset/Workspace/Graph owners and read back the exact saved card pin. They cover version/incarnation/definition/card conditions, stale and foreign assets with no partial write, wrong branch and revoked write/read grants, and refusal of a synthetic legacy APPROVED asset without formal provenance. Provider execution, accept, inspection and media fetching are guarded against invocation. This proves manual display persistence and the refusal boundary, not generated-result quality or formal approval.

The new frontend cases use the real Studio HTTP client with explicitly synthetic CanvasView records. They check the exact strong PUT body, input/read/saved distinctions, cold remount/get pin identity, old compatibility behavior, invalid provided owners, A/B/A, delayed parent dispatch, 409/403 responses and UNKNOWN old callbacks. No browser rendering, binary validity or formal provenance claim follows from those records.

Initial related frontend verification retained **126 passed / 5 failed**. All five failures were in the pre-existing dual-canvas software fixture and also reproduced on the untouched published baseline as 5 passed / 5 failed. Capability probing found jsdom Blob lacked `arrayBuffer()`, which candidate hashing requires. A two-line **test-only** import/stub of the standard Node Blob made those original ten cases pass; bytes, hashes, assertions and production candidate guards were not changed. This is test environment compatibility, not a media safety workaround or real provider review. The original UNKNOWN baseline negative and all these diagnostic records are retained cloud-only.

Exact commands, logs, pre/post source and dependency hashes and refusal/cold-read evidence remain under the round10 cloud records. Raw runtime logs, test stores, build outputs and dependencies are excluded from Git. GitHub HEAD and CI are queried after normal work-branch publication; local tests do not imply Actions execution.

Real formal-result File approval/return, PostgreSQL, real providers/GPU/paid calls, native Windows and browser/geometry acceptance are **NOT_RUN**. The restricted media review and Chromium sandbox were not retried or bypassed. Main and release state are unchanged. No local Windows data, old migration package, new credentials or additional dependencies were used.
