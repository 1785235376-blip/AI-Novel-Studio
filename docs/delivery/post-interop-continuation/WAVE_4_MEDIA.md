# Wave 4: deepen the original media production workflows

Original starting source: PR #42 `e58c72b04182cd374af092314386b90f8250a173`. After the 2026-10-06 executor reset, this unpublished Wave 4 work was reconstructed from retained source/edit commands against the verified official source bundle at HEAD `4d736c0d14bdcd12d0ad3cc7146553971654620b`, tree `6b8269fb95e695178ce4c587c9fc729275d0e848`. Published Wave 1 ancestry and original history were retained.

This document records new continuation work, not a historical acceptance upgrade. PR #37–#42 evidence and the historical blocked independent audit are unchanged. The prior matrix remains F00 INTEGRATED / other 39 PARTIAL. Pre-reset test counts are not reused as evidence for the reconstructed source.

## Original IDs and honest status

| Original ID / owner | Exact previous gap | Implemented continuation | Product boundary |
| --- | --- | --- | --- |
| A08 Director | Geometry/axis checks existed, but explicit establishing/OTS/POV/insert and rack-focus vocabulary plus rhythm/repeated-framing checks were missing. | Additive shot-function/focus fields in the existing proposal; discoverable camera-motion vocabulary; same-scene declared-direction, repeated-framing and transparent 3:1 estimated-duration review suggestions. Applied through original screenplay CAS/history and original approval gate. | PARTIAL; deterministic metadata contract; actual camera/image understanding and model quality NOT_RUN. |
| Existing R3 Cover/Storyboard, U06 refresh | Cover omitted typography intent; original shot IDs had to be copied; storyboard had create but no revision route. UI could block cancel while execution awaited its response, and scope replacement could retain comparison/form state. | Original-project catalog/pickers, cover typography in durable briefs and registered adapter requests, explicit cover and storyboard revision controls, storyboard CAS/history API, stale-brief feedback, cross-version comparison labels, independent cancel and scope/late-callback fences. | PARTIAL; synthetic PNG remains MOCK_ONLY; injected registered-adapter transport is a contract fixture, not real model acceptance. No GPU/ComfyUI/H3/paid service run. |
| A09 Asset Lineage | Existing DAG was correct but the generation projection exposed only task/operation/input digest. | Original approved asset projection now carries observed adapter/workflow versions, model identity, seed when recorded, production time, prompt digest, and screenplay/scene/shot pointers. No raw prompt is added to the public export or a second asset authority. | PARTIAL; license remains an author declaration; unrecorded edges are UNKNOWN. |
| A13 Production Manifest | Existing booleans separated replay/byte equality, but did not explicitly label approximate reproducibility versus deterministic claims in every view/export. | Independent assurance labels in recorded views, current preflight and allowlisted export. Replay is NOT_CHECKED until fresh preflight; approximate reproducibility NOT_EVALUATED; determinism is only SYNTHETIC_PROTOCOL_ONLY, otherwise NOT_VERIFIED. | PARTIAL; same seed does not promise GPU/model byte equality. |
| B03 Audiobook / Voice Direction | A malformed attribution adapter could report confirmed without a speaker. Base audiobook timing accumulated rounded milliseconds despite measured WAV frame evidence. Old frame metadata survived an edit. Voice execution shared the cancellation busy state. | Unknown speaker is always NEEDS_REVIEW. Base timeline uses exact frame/sample-rate fractions until its millisecond view. Segment edits clear old frame evidence. Duration manifests distinguish unmeasured/partial/measured and explicitly state no word alignment. Independent cancellation remains available during execution and for stale owner-visible running jobs. | PARTIAL; TTS quality, cloned voice, ASR/forced alignment and lip sync NOT_RUN / NOT_CONFIGURED. Synchronous bounded mixer remains synchronous, not a new durable task system. |
| B04 Subtitle Timeline | Existing precise cue editing must not imply ASR precision from an audiobook source. | Retain original subtitle service and inherited boundary tests; upstream manifests expose measured-frame evidence and unknown alignment explicitly. Audiobook UI stops displaying a numeric start with a fabricated/null end and fences old manifest/subtitle views by plan version. | PARTIAL; manual/measured segment timing only. No word/phoneme alignment or subtitle burn-in added. |
| A12 OTIO | Shot camera/action/sound/dialogue fields were silently omitted from screenplay exchange; unknown keys in the exchange metadata namespace were silently discarded. Summary conflated clip timeline start with source trim. | Explicit per-shot loss codes and UI explanations; unknown extension-loss warning and malformed exact-time rejection; source in/out separated from timeline positions in summary; audio/video relation explicitly limited to independent-track timing. | PARTIAL; pinned official OTIO 0.18.1 required. Resolve/Premiere/other NLE acceptance NOT_RUN, media remains unbundled. |
| U06 selective refresh | New cover typography could be dropped when a stale original task was refreshed. | Regression asserts current-source preparation retains typography through the original fresh task while old task/results remain unchanged and no asset is auto-approved. | Existing bounded original refresh retained; audio/video refresh are not mislabeled as image execution. |
| U07 integration seam | Task center navigation could only open a media feature generally. | `MediaPanel.requestedTaskId`, `VoiceDirectionPanel.requestedTaskId`, `AudiobookPanel.requestedPlanId` locate only IDs returned by current original-authority read. Missing/out-of-scope IDs show unavailable; navigation performs no generation, retry or approval. | Parent owns shared Workbench/navigation plumbing. |

## Existing authorities, APIs and persistence

No parallel framework, project state, model registry, asset library, task executor, or permissions table was introduced.

- `GET /api[/v1]/novels/{nid}/experimental/media/catalog`: current original screenplay/shot IDs and minimal project character identities. Stale scenes and other branches omitted. No character secrets or model calls.
- Existing `cover-briefs` and `storyboard-briefs` listings include current-source stale state.
- `PUT /api[/v1]/novels/{nid}/experimental/media/storyboard-briefs/{rid}?expected_version=N`: same original screenplay/shot identity, current expected screenplay version, normal experimental-store CAS/history. Old candidates remain historical and cannot approve against a new brief. Owner-controlled refresh briefs cannot be edited through this ordinary path.
- Existing cover PUT reused by visible revision form. `typography_intent` is bounded to 2000 characters and passed through original registered image adapter input.
- Existing compare response reports candidate stale state and whether selected candidates bind the same source version. Historical comparison does not authorize stale promotion.
- Existing production endpoints gain read-only `assurance`; no endpoint/flag/Interop wire changes.
- Original `voice-direction/jobs/{id}/cancel` reused; no second audio job state.

All changes use existing versioned JSON documents / original asset metadata. No SQL schema change or migration is required. New fields are additive and optional/defaulted for old documents. File and PostgreSQL use the same existing transaction/CAS code. Rollback must retain stored JSON/history; older servers may ignore new view fields but cannot accept new Director fields in old strict input schemas. Do not point an older executable at active new-form edits without exporting/reviewing original data. No user V1 data was used.

## Reconstructed regression coverage

Runtime/UI reconstruction used anchor-checked replacements on the verified source. All 14 runtime/UI diff numstats match the retained pre-reset edit checkpoint. The 14 backend test functions, 6 media UI cases, 3 voice UI cases and 1 browser journey were recovered, including final typed `Row.version` fixes. No original assertion or skip was removed or broadened.

Reconstructed journeys:

1. Original screenplay → proposal with new grammar → compared apply → original screenplay new draft version and original history → service restart recovers exact fields.
2. Original scoped catalog → original Shot → storyboard brief → synthetic candidates → brief revision → old promotion rejected → cross-version comparison labelled → restart → current candidate promoted to original asset library with same Shot lineage.
3. Cover typography → existing task snapshot → injected original registered image transport receives typography → manifest retains seed without claiming determinism.
4. Original completed cover → chapter changes → U06 fresh preflight/current-source task → typography retained, old task untouched, no auto-promoted asset.
5. Malformed unknown speaker attribution → NEEDS_REVIEW; unknown/partial audio remains unmeasured. One hundred measured 44.1-kHz frame durations must not accumulate millisecond-rounding drift. Editing clears old measured evidence.
6. Official OTIO import/export → loss acknowledgement gate; explicit shot-field and extension warnings; source in/out remain separate from timeline starts.
7. UI contracts: independent media/voice cancellation during pending execute, stale-job cancellation, scope replacement discarding late comparison, conflict-preserved draft, newer typing retained after late save, exact current task selection without execution.

Current post-reset verification:

- Reconstruction checkpoint Python AST syntax: PASS for 7 backend files and the then-14-function regression module; subsequent mounted asset-contract regression is included in the current checks below.
- Owned runtime diff whitespace: PASS.
- Earlier post-reset backend union (before the later source-visibility correction): **288 passed, 205 PostgreSQL cases deselected, no skips**, 2 warnings, 107.35 seconds. Uses restored Python 3.12.14 and pinned official OTIO 0.18.1. Covers all reconstructed backend regressions plus original File/API/auth/CAS/history/restart/cancellation/late-result, U06 and batch owners. The exact command and log hash are in the machine-readable delta. No CJK-font-bound test was requested or skipped in this run.
- Fresh exact staged frontend: **1231 passed /8 inherited opt-in skips**, TypeScript and design-token guard PASS. The official pinned environment was restored through normal approved setup. Tested code tree `ac967d2a769b76c61bfb60ba01e12c0a2ca4ebc1`; see WAVE_4_STAGED_VERIFICATION.json. Pre-reset counts are not reused; final-source hosted checks remain required.
- PostgreSQL: NOT_RUN locally; no confirmed disposable DSN. The continuation regression module now has 12 PostgreSQL-parametrized cases, including the new asset-read contract under both API prefixes; the source-visibility module adds 10. Hosted `postgres_backend_only` must execute them.
- Current corrected browser journey: NOT_RUN pending the next exact-source hosted run. The prior superseded hosted run exposed the two media failures documented below. Local Chromium remains platform-blocked and was not relaunched. `frontend/tests/e2e/r4-post-interop-media-continuation.spec.ts` is matched by the original R4 config and contains actual API/UI, reload and 1366×768 / 1440×900 / 1920×1080 overflow/screenshot checks. Hosted exact-commit verification remains required.
- Historical independent review: BLOCKED and unchanged. Neither source reconstruction nor syntax checks are full product/native/creative acceptance.


## Missing-character candidate visibility correction

A bounded continuation review found that the initial missing-character fix covered brief lists but not existing generated candidates. With a generated Alice-bound cover and an independent generated cover, withdrawing Alice left `briefs()` readable and `tasks()` intact, but `proposals()` called `_stale()` and raised `MEDIA_CHARACTER_REFERENCE_INVALID`. This caused the media panel's combined owner reads to fail.

The correction catches only that exact recognized error in `_stale()`, matching the existing brief-list projection. It marks the affected historical candidate stale without changing persistent state. Other ValueErrors, unexpected suffixes and permission errors still propagate. Original queue and promotion checks are unchanged: stale queue and approval still reject; the independent cover remains queueable and its candidate can be approved into the original asset library.

`tests/test_post_interop_media_visibility.py` now covers generated candidates as well as briefs: current tasks/proposals/comparison/Inbox, read-only persistence, stale queue/approval rejection, independent promotion, both API prefixes, authentication and V1 acceptance mode, and explicit unexpected-error propagation. It uses the inherited File/PostgreSQL fixture without changing skips or existing assertions.

- Pre-fix evidence: the added File regression failed with the exact missing-character error in `proposals() → _stale()`.
- Fresh corrected focused run: **88 passed, 81 PostgreSQL cases deselected, no skips**, 1 warning, 73.23 seconds. Covers visibility, all Wave 4 continuation tests, original media workflow/evidence, U06 change impact, production lineage and registered-local media.
- Independent bounded check on the same runtime/test hashes: **52 passed, 45 inherited PostgreSQL skips**, plus the original direct File reproduction yielding 2 briefs, 2 tasks and 4 candidates with correct stale flags. Counts overlap and are not summed. This closes the reported read-availability defect; it does not replace the historical blocked audit or full product acceptance.
- The earlier Node setup block was subsequently resolved through official pinned setup. Exact-stage frontend/TypeScript receipts are recorded above and fresh correction checks below; local browser and PostgreSQL remain NOT_RUN. No model, GPU or paid service execution occurred.

## Hosted media compatibility corrections

Verified hosted run `37498190450` (head `dedb813`, merge checkout `4774ad6f`, compact artifact `11429826185`) reported two media failures before being superseded. These are failures on that earlier source, not a passing final browser result.

1. The new continuation journey successfully created the original Shot brief, revised it, generated and compared candidates, and approved an asset with the correct Shot lineage. Its next request incorrectly omitted the required `novel_id` query on `GET /api/assets/{asset_id}`, so the existing API correctly returned 422. The new browser fixture now supplies `params: { novel_id: nid }`, keeps the HTTP 200 assertion, and additionally checks returned asset/project identity. The runtime API and its required project authority are unchanged. A production-mounted regression proves missing query → 422 with the exact missing query field, correct project → 200 and matching stored asset digest, wrong project → 404, under both `/api` and `/api/v1`.
2. The inherited registered-media journey expected `确定性协议可复现：否`, but the continuation changed that label to `合成协议确定性：否`. The original compatible label is restored. The separate synthetic-only determinism explanation, same-seed limitation and byte-equality status remain. A new UI regression tests both true/false evidence states. The inherited browser test and all its assertions are untouched.

Fresh checks on these corrections:

- Backend: **58 passed, 36 PostgreSQL cases deselected**, no skips, 1 warning, 32.87 seconds. Includes new mounted asset query cases, source visibility, continuation, original registered-media/production mounted routes and project authorization.
- Frontend: **30 passed** across 5 focused media/lineage files; TypeScript **PASS**; token guard **PASS (42 files)**. These are real local tests using restored official dependencies, not reused pre-reset counts.
- The previously recorded exact staged code tree `ac967d2a769b76c61bfb60ba01e12c0a2ca4ebc1` remains its own receipt: full frontend 1231 passed / 8 inherited opt-in skips, TypeScript/token checks, 24 new File cases / 20 PG deselected, and identical 7306-node collections with 44 additions and unchanged inherited test digests/skips. That receipt predates these two hosted-browser corrections and is not relabeled as a final corrected-browser pass.
- No local Chromium, workflow rerun, real provider/GPU/model execution or runtime asset-permission relaxation occurred. The next correction commit requires its own full CI/browser results.

## Opus UI handoff

Changed consumer panels: `DirectorPanel`, `MediaPanel`, `ProductionLineagePanel`, `AudiobookPanel`, `VoiceDirectionPanel`, `TimelineExchangePanel`. No AppShell, tokens, theme, module order or core primitive changes. New controls reuse `Panel`, `Button`, `Badge`, `Field`, `Form`, `StatusMessage` and `experimental-*` classes. The original implementation inspected the Design System and canonical VIDEO reference; reconstruction preserves those edits rather than proposing a new design language.

Do not break:

- Original screenplay approval after Director apply; no visual score or invented spatial evidence.
- Explicit fixture-versus-registered-route choice and original broker preflight. Unknown costs remain unknown.
- Cancel remains clickable while awaiting execute; late results cannot reactivate cancelled tasks.
- Same-scope conflict drafts survive; client/authority replacement unmounts private local state.
- Brief edits preserve original identity/history; old source versions never overwrite current artifacts.
- Promotion recovery uses original durable intent and existing asset, not a new upload or guessed result.
- Manifest traceable/replayable/approximate/deterministic/byte-equal labels remain independent.
- Measured segment boundaries never imply ASR, word alignment, lip sync or voice quality.
- OTIO losses require acknowledgement; no all-NLE compatibility claim or media packaging.
- Original flags stay default OFF and V1 acceptance server-denies experimental routes; Interop 1.0 authority semantics and files remain frozen.
