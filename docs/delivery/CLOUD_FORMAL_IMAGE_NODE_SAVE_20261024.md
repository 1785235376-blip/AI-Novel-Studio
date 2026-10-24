# Formal image-node placement in the original saved canvas

This slice implements a separate, explicit formal text-to-image entry for one selected Rebuild image-generation node. It uses the existing Production Job, human-review, Asset and CanvasView owners. It does not upgrade legacy accepted results or migrate a browser graph. The starting published commit is `bc16fc4ae0f7d1117cb60dbf40f3123f2ab81356`.

## Implemented path and authority

1. The selected node explicitly opens the original verified workspace. The user then creates one original empty CanvasView. Opening the entry itself does not create, queue or execute anything. Node title, ID, original position and the exact prompt digest are captured; other nodes, edges and the browser graph remain drafts.
2. The existing formal production panel prepares a local, source-free `m5.image.t2i` request. The additive `canvas_image_node` capsule (`studio-canvas-image-node/1`) binds the real project/scope/incarnation, CanvasView ID/version/definition digest and captured node. It is part of the original immutable command, not a permission or approval marker. Prompt, route and operation are fixed for this target; choosing local model/configuration and parameters uses the original panel. There is no cloud-provider fallback or automatic dispatch.
3. The original preview/create, execution preclaim, last dispatch check, source checks, review entry and publication phase recheck the original target. Editing that CanvasView invalidates the captured target. Execution and human review remain separate explicit original-owner operations.
4. After the original owner records approval, a separate inspect/consent/save action calls `POST /api/projects/{nid}/studio/canvas-views/{vid}/image-node-result`. Both read and write authority remain current through the original invocation guards. The request carries strict explicit confirmation and original version/incarnation/digest plus exact Job/request and Asset pins.
5. The server reads the real actor/scope-owned original Job before acquiring the Canvas scope/asset/project transaction. It requires terminal APPROVED state, the exact command capsule, original request and receipt digest, real candidate and promoted Asset version. Inside the existing transaction it compares the raw Asset's exact pin, original production origin, approval provenance, project binding and visibility. It neither reads media bytes nor performs approval.
6. The original CanvasView gains one card at the captured node position and a versioned `image_node_origin` containing the capsule, original Job identity/version/request digest and exact Asset pin. Exact duplicate saves return the existing association without another history event. Ordinary create cannot mint this origin; ordinary save/restore cannot remove or rewrite it or its asset pin. A mapped card can subsequently be moved using the existing canvas owner.

The saved definition and history remain in `creative_canvas_views_v2`; no new database, queue, Asset copy, execution owner or review state is introduced. Old commands and canvas definitions omit the new optional fields and retain their original serialization. The legacy `studio-canvas-return/1` i2i/audio contract stays separate.

## Reading and failure behavior

The selected node can explicitly list/read its original formal tasks and their original saved CanvasViews. Recoverable tasks and saved placements are explicitly selected; reading never executes, reviews or adopts. The UI compares project/scope/incarnation, node binding, original Job and current Asset pin. The saved card retains its actual current coordinates after a later authorized move. There is no claim that prompts, edges or the whole Rebuild graph are server-persisted or shared across clients.

Parent dispatch wrappers recheck the captured selection and authority at invocation. Selection, prompt, placement, project/client/Host changes retire old callbacks, including A/B/A transitions. Synchronous pending/unknown guards prevent duplicate clicks and retained callbacks from resending an uncertain mutation. A failed/unknown save preserves the input and shows no success; recovery is read-only.

One remaining recovery limit is an **unknown initial empty-canvas create before any formal Job was queued**. The request ID remains visible in the live instance, but existing list/get projections do not resolve that request ID to a node. The node recovery action cannot automatically identify this orphan empty view after a cold reopen. It blocks resend; it does not guess a target or claim recovery. A future original-owner request lookup could address this without a parallel store.

`CURRENT_METADATA` in original CanvasView GET/history describes current Asset metadata. The stored origin is a historical association, not an independent fresh Job authorization or a new review attestation. New mapped mutations recapture the original Job and exact Asset proof; the formal-node reopen UI also reads that original Job before showing its association.

## Verification and limits

The real File/API tests use the mounted original routes and newly reconstructed File services. They cover actual empty-view creation, formal preview/create to QUEUED, immutable node intent, idempotency, cold Job/Canvas readback, and refusal of unapproved or counterfeit result requests. They also cover changed targets, source/read/write authority, strict confirmation and old serialization. Provider, review, accept, content inspection and media-fetch sentinels must remain unused. One stale-target execution request exercises only the metadata preclaim refusal and must not reach the original ImageJob executor.

Frontend tests use explicitly synthetic software HTTP records for approved-result association and cold reopen. Those records exercise client fields and UI behavior; they are not actual approval receipts or proof that the backend accepted a reviewed generated result. No APPROVED state, production-origin receipt or provenance is fabricated in a File owner.

**A real File approved-result adoption/cold-reopen positive is NOT_RUN.** Producing that positive would require the previously restricted original media review/ingestion path, which was not retried. Implemented code and passing queue/refusal/software tests do not establish that acceptance. Real models, paid/GPU calls, PostgreSQL, native Windows and browser/geometry acceptance also remain NOT_RUN. The earlier browser sandbox and media restrictions were not bypassed.

The final tested source is `82c7ad4dc4d2f862fd1d5e830c7e8c7c4bc76d6a`, tree `25b1c748f1f592d405af759d4151e7cc9a17e1f4`. The following delivery edit changes documentation only.

| Evidence | Actual result and boundary |
| --- | --- |
| Real File/API | **23 passed**, 3 existing warnings, 10.52s at `8945e6a3c4a833bc32dca14f0397f8f2fdd58b40`: 6 existing manual-card persistence/refusal cases and 17 new formal-node queue/cold-read/refusal cases. All backend and Python-test bytes are unchanged in the final source. No formal reviewed-result save positive. |
| Related frontend regression | **210 passed**, 25 files, one worker, 47.64s at `406b63bcdfb0dc2e2b1488aa06be9f4cc1fd0d12`. This includes the new groups below; their counts must not be added again. |
| Actual original panel + HTTP client software replay | **3 passed**, included in 210: preview/impact/queue with the new capsule, parameter ABA and an unbound global execution refusal. No provider, execute, review or media call. |
| Container adoption and reopen software projections | **8 passed**, included in 210: explicit save, unknown/retained callback, deferred permission, node ABA, StrictMode and cold read with explicit record selection. This group stubs the production panel; it does not produce a real approved owner state. |
| Result HTTP request/receipt checks | **4 passed**, included in 210: exact original POST body and wrong Job, pin or target refusals. Responses are software projections. |
| Final test-only type correction | The following change only makes the partial container fixture's type assertion explicit; no production or runtime assertion changes. Its **8 cases passed again**, 1.33s at the final source. This overlaps the earlier 210, not 8 additional cases. |
| Standard type/build | **PASS** `corepack pnpm build` (`tsc -b && vite build`) at the final source: process 50.934s, Vite 8.57s, 2630 modules. Existing chunk-size warning only; package manifests and frozen lock unchanged. |
| Independent review | Source/authority/public-diff review completed separately from test execution, with final delivery checked before publication. |

Initial verification at `8945e6a3` retained a JSX closing-brace build/transform failure and an outdated closed-client method-list assertion (192 frontend cases passed, one assertion failed). These were corrected before the 210-case pass. That later build then caught a test-only partial-fixture type assertion; the final source corrects it and passes the standard build. Original failure logs remain in cloud evidence. Static source review did not detect the initial JSX typo and is not represented as compiler acceptance.

Normal work-branch push and exact remote/CI readback are recorded separately after verification. Local verification never implies GitHub Actions ran.
