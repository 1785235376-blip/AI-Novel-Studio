# Wave 1: original-owner UX continuation

Source: new `work/post-interop-r4-r5-ux-continuation` successor, starting from frozen PR42 `e58c72b04182cd374af092314386b90f8250a173`; Wave0 documentation baseline `8ed7afd9`. This is a new implementation record, not a rewrite of PR39's historical PARTIAL matrix.

## Capability deltas

| Original ID | New bounded implementation | Status and remaining boundary |
| --- | --- | --- |
| U01 | Review Inbox IDs join the existing actor-private workspace's pending references. Reopen reads each original domain again; origin-OFF, removed or revoked references disappear with a recovery warning. | INTEGRATED / PARTIAL. Existing chapter/anchor/reference restoration remains; native crash/power-loss acceptance is LOCAL_REQUIRED. No task resumes automatically. |
| U02 | Distinguish corrupt browser draft from no draft; keep raw bytes, prevent overwrite, explicitly export or discard before opening backend text. Browser-offline labeling suppresses automatic network save attempts while allowing explicit local-backend save and keeping receipt/CAS validation. | IMPLEMENTED / PARTIAL. Same journal/key, old valid records accepted; no extra manuscript store. Browser storage can still be cleared or physically lost. |
| U03 | Add original novel, volume, scene, timeline and Review Item projections. Existing character/location/foreshadowing plus new story records open exact original editor records, freshly reread. Non-title source changes invalidate the search receipt. Original task result source pointers retain owner, ID and parent ID. | INTEGRATED / PARTIAL. Not universal organization/rule/asset/graph search. Unsupported branch manuscript/dataset adapters remain fail-closed, never fall back to local manuscript. Literal search remains visibly lexical. |
| U07 | Add receipt-bound explicit cancellation to original author, import, team, media, agent, workflow, image, export, voice, audio/TTS and motion authorities. Add missing original audio/TTS, motion and Review Inbox projections; expose safe provider/model identity, requested-vs-observed route and explicit unsupported-action reasons. Exact owner navigation reaches import/team/inbox/export/agent/image/audio/workflow/motion controls. | INTEGRATED / PARTIAL. Retry/resume/review stays in each original preflight/recovery/review owner. Money remains UNKNOWN without a verified accounting receipt; no synthesized percent. Final Media/Voice/Audiobook experimental deep-link forwarding is integrated with Wave4. |
| U08 | Preserve existing real preview/final-request authority; scene identity is now carried through character-only preview, receipt identity and dispatch. | PARTIAL. Explicit Research/Canon/Story Graph add/pin controls are an assigned follow-on refinement, not claimed complete in this checkpoint. |
| U09 | Existing Local AI Discovery now translates runtime/model/adapter/license/VRAM/CUDA/identity blockers into specific next steps while retaining evidence labels. | IMPLEMENTED / PARTIAL. No runtime, node, model, Torch/CUDA/driver install, upgrade or launch occurs. GPU/model acceptance remains LOCAL_REQUIRED / NOT_RUN. |
| U12 | Task and diagnosis endpoints recheck current authority after all source reads and before returning/exporting. Cancellation conflict errors expose only current version, not source prompt/lease payloads. | CONTRACT_VERIFIED / PARTIAL. Diagnostics remain allowlisted, preview-digest-bound and user-triggered local download. |
| U05 | Existing selection receipt and original CAS/partial revision integration retained and regression checked; character scene context does not opt into selection revision. | PARTIAL. Further revision implementation belongs to Wave2; no real-model quality claim. |

## Original task owners and actions

- Author generation: original `JobManager` and authenticated generation read/cancel, current origin feature guards and terminal transitions. No replacement executor, retry or task store.
- Import and creative team: original scoped/versioned transition methods; exact CAS version from the displayed task receipt. Original claims and late-callback fences remain authoritative.
- Cover/storyboard media: original media transition. Safe-batch-owned tasks explicitly require their origin coordinator and cannot be cancelled through this generic action.
- Agent jobs: trusted original session/owner read and original cancel in QUEUED/WORKING. Local experimental project access alone does not grant original agent authority.
- Workflows: original workflow owner/read/cancel, including cancellation of linked original agent jobs; waiting approval and paused stages remain explicit.
- Image and export: original authenticated routes and terminal rules; results continue through the original review/download controls.
- Voice direction: exact actor/scope/origin-bound original audio queue. No duplicate display through the ordinary audio reader.
- Ordinary audio/TTS: original queue and original cancellation; no ASR/alignment or quality claims.
- Motion/video: original screenplay ID and task ID; cancellation uses the existing provider cancellation behavior where an original remote task exists. No cloud provider was called in verification.
- Review Inbox and audiobook plans: original review/plan records, not invented executors; cancellation absence is explicit. Review and recovery remain in their owners.
- Model-based simulator/judge/translation/declarative background jobs: existing original author projection and owning proposal surface retained. Universal feature-specific historical-item focusing is not claimed.

## API and old-data compatibility

`POST /novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` accepts only `expected_revision` (SHA-256 of the allowlisted task projection). Requires current project writer plus original owner authorization. Source/state drift is 409; invisible or unsupported owner is 404; feature OFF and V1 acceptance stay server-gated. Original task transitions decide terminal races. Responses contain only the workspace task projection.

Search kind additions and task projection fields are additive. Existing routes, workspace keys and owner collections are reused. No SQL migration or old migration edits; File and PostgreSQL use the same existing original repositories and experimental JSON document CAS. New mounted tests inherit actual File/PG fixtures; PG is not silently replaced with File.

## Verification

- New mounted File API cases cover both `/api` and `/api/v1`, original cancellation and persistence, late-output terminal protection, actor/writer revocation, source changes, branch isolation, exact owner pointers and review resume. Exact final counts/commands are in `WAVE_1_UX.json`.
- Focused inherited and new unit/React tests verify recovery, task confirmation, actual owner navigation, unchanged save receipt/CAS handling, context scene-receipt invalidation, shell routes and design-token rules.
- Added three hosted browser journeys: original scene search/editor navigation; original import cancellation/reopen; corrupt draft reload/export/discard. Static Playwright collection passes (3 cases).
- Local browser execution is BLOCKED by the previously verified platform Chromium-launch denial; it was not retried or routed around. Screenshots/geometry/browser execution await the inherited hosted lane. Existing AppShell tests pass; no protected shell geometry was changed.
- Actual PostgreSQL execution awaits the inherited hosted PG lane. Real models/GPU/Windows/ComfyUI/H3/paid APIs remain NOT_RUN / LOCAL_REQUIRED. Synthetic API and mock protocol verification is not literary/media-quality acceptance.

## Opus integration notes

Use existing DS-v1 panels, buttons, labels, notices and token styles. Preserve the one NOVEL/IMAGE/VIDEO shell; no new visual language or parallel navigation/state store.

Do not remove: corrupt-draft overwrite gate and raw export; distinction between browser-offline and backend receipt; explicit cancel confirmation; per-task receipt/version and current authorization; safe-batch coordinator-only actions; model route evidence label; unknown costs/progress; exact original record/parent IDs; target-scope remount; stale/absent record warnings; character-only scene receipt invalidation. Browsing/recovery must never execute, retry, approve or synthesize implicitly.
