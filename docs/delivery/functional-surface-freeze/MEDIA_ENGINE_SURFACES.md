# Media production and engine adapter completion

Status: CONTRACT_VERIFIED for local service/adapter contracts; PARTIAL for end-to-end real-model production. All real ASR/alignment/image/video/post models, target Godot/Ren'Py runtimes, GPU execution and perceptual quality remain NOT_RUN. No runtime or model was installed and no cloud provider was called.

## Existing ownership retained

- Production / subtitle timeline remains `SubtitleTimelineService`; `subtitle_processing.py` is its helper and adapter seam, not a second workspace, caption authority or task system.
- Caption rows, processing attempts and review receipts share the existing `ExperimentalStore` scope transaction, with real File and PostgreSQL storage paths. No database migration or historical interop schema is changed.
- Speech generation, voice authorization, character mapping, emotions, attribution and audiobook plans remain in `DirectedAudiobookService`, the original `AudiobookService` executor, asset library and original review flows.
- BGM/music, ambience and SFX remain original audio-provider/audio-track inputs. Measured mixing remains the bounded `LocalPcmMixer` using original audiobook mix proposals, not a second rendering service.
- Interactive Story / Visual Novel remains `InteractiveStoryService`, planning-node identity, author-owned adaptation rows and exact-source review. Godot is another export target in the same bundle as the existing engine-neutral JSON and Ren'Py generated text/menu subset.
- Direct manuscript reads in media, audiobook, director, production lineage, comics and translation catalogs now use `chapters_for(scope)`. Media/audio source receipts retain collaboration scope so a later validation cannot substitute mainline prose.

## Subtitle processing data and state

Input: existing caption ID and exact version, adapter ID, operation (`ASR`, `FORCED_ALIGNMENT`, `BURN_IN`) and, only for alignment, a bounded transcript. A caption supplies the existing project/workspace/branch source, measured audio/video asset, rational timebase and current source snapshots. No URL, command, plugin package, credential, file path or arbitrary parameter is accepted.

Persisted task: immutable actor/project/scope; caption and media version/digest; adapter identity; attempt count; claim token and process-instance identity; result or sanitized error; CAS version/history; local-only privacy; exact result-review digest. Public projections omit claim, raw transcript, history and binary payload. Foreign-owner, foreign-scope and withdrawn-source results are withheld.

Transitions:

- Queue -> QUEUED only with an explicitly host-configured executable local adapter; otherwise durable NOT_CONFIGURED. ASR/forced-alignment execution is currently limited to explicitly injected synthetic fixtures; real model adapters remain NOT_CONFIGURED until the original model/media admission coordinator is integrated. Trusted local burn-in transforms may use the non-model adapter seam. There is no implicit synthetic fallback.
- Execute -> durable RUNNING claim -> NEEDS_REVIEW only after before/after authority, source and adapter checks plus bounded result validation.
- Cancel -> CANCELLED; cooperative guard and claim fences discard late output. It does not promise preemptive interruption of arbitrary trusted host code.
- An interrupted RUNNING attempt survives restart. A new service instance reports recovery_required; explicit recover -> INTERRUPTED and explicit resume -> QUEUED. No automatic replay occurs.
- FAILED/CANCELLED/INTERRUPTED/NOT_CONFIGURED can resume only after exact current source/configuration checks. Changed source requires a fresh task, not silent rebinding.
- Approve/reject requires `domain.review`, current CAS and exact preview digest. ASR/alignment approval updates the original caption atomically with the task receipt; it does not write manuscript or Canon. Burn-in approval enables a bounded original-owner download; it does not publish or silently promote an asset.
- Manual caption editing reopens DRAFT and manual timing. Previous source/result provenance remains in version history.

Result constraints:

- ASR/alignment returns 1–2000 validated plain-text cues in the original rational timebase, within the measured media duration; all text is bounded to 100,000 characters.
- Forced alignment must preserve the supplied transcript after whitespace normalization. Model-provided speaker IDs are rejected; original voice attribution review remains authoritative.
- Burn-in returns bounded MP4/WebM bytes, inspected by the existing media validator; measured duration must remain within one millisecond of the source and MIME must match. Synthetic byte-preserving fixtures are explicitly MOCK_ONLY and prove no rendering quality.
- Input/output media is limited to 8 MiB, retained render bytes to 32 MiB per scope, processing tasks to 200 per scope, and attempts to 50 per task. Task transition history keeps digest receipts without duplicating binary outputs or transcripts. Larger production media requires a future bounded streaming implementation; there is no claim of production-scale rendering.
- No phoneme timing, lip sync, ASR accuracy or visual burn-in quality is inferred from valid cues/container bytes.

## Mounted API and functional UI contract

Both `/api` and `/api/v1` mount the existing prefix `/novels/{nid}/experimental/subtitle-timeline`:

| Method | Suffix | Authority | Purpose |
|---|---|---|---|
| GET | `/processing/catalog` | domain.read | Schema, configured adapters, states and safety boundaries |
| GET | `/processing/tasks` | domain.read + original actor | Current original-owner tasks and stale/recovery state |
| POST | `/processing/tasks` | domain.write | Queue against exact caption version |
| POST | `/processing/tasks/{id}/execute` | domain.write | Explicit trusted adapter dispatch |
| POST | `/processing/tasks/{id}/cancel` | domain.write | Claim cancellation and output discard |
| POST | `/processing/tasks/{id}/recover` | domain.write | Mark interrupted prior-instance claim |
| POST | `/processing/tasks/{id}/resume` | domain.write | Revalidate and explicitly requeue |
| POST | `/processing/tasks/{id}/approve` | domain.review | Exact result admission |
| POST | `/processing/tasks/{id}/reject` | domain.review | Exact result rejection |
| GET | `/processing/tasks/{id}/file?expected_version=N` | domain.read + original actor | Approved burn-in bytes only |

Required flags: `subtitle_timeline_v2`, `voice_direction_v2`, `audiobook_v2`. Flags are default-off and V1 acceptance mode wins. Disabled/unauthorized routes fail closed; response and error caching is disabled; conflicts return sanitized version/status rather than stored content.

The formal UI surface remains Production -> existing subtitle timeline. Components: original asset/track selection, operation/adapter picker, transcript input, version/source inspector, processing task list, exact cue/result review, recovery controls and reviewed download. Loading, empty, error, unauthorized, missing configuration, disabled, conflict, review and recovery states are returned by the catalog. The new controls are a formal UI Surface Contract; no final visual redesign or new top-level navigation is introduced. `processing_task_projection` and `processing_review_projection` expose bounded original-owner navigation to the unified centers. Inbox approval must open the exact-result original review flow; batch approval is unavailable.

## Godot and Ren'Py engine adapters

`EngineExportAdapter` exposes shipped pure validation and file generation. No executable adapter upload or registration endpoint exists. `GodotExportAdapter` produces:

- `godot/story.json`: `ai-novel-godot-story/1`, strict bounded nodes/variables, zero-based resolved target indices, source-node identities, typed condition trees and manifest-only media references.
- `godot/story.schema.json`: strict envelope/node/variable schema.
- `godot/README.txt`: plain-text consumption guidance and explicit target-integration limitations.

The validator rejects foreign target indices, duplicate IDs, untyped/unknown expressions, unknown keys, calls/code, invalid variable assignments, excessive nesting and invalid bounds. Read-back validates emitted JSON before inclusion; existing deterministic bundle checksums include every new file.

Godot is explicitly `GODOT_4_DATA_ADAPTER` / `TARGET_INTEGRATION_REQUIRED`: it is a data exporter, not an included Godot runtime, playable project or tested target importer. Ren'Py remains `RENPY_8_5_4_TEXT_MENU_SUBSET` with escaped author strings, generated bounded labels/choices and no packaged media/custom screens/addons. Both engine runtimes stay NOT_RUN.

The original `/interactive-stories/engine-contract`, `/export-preview`, `/export` APIs expose the new target schema and limits. Source changes, lost review, archived adaptations, permission revoke and stale CAS continue to block export. Export is bounded synchronous pure work: cancellation discards the response with no external write; resume/restart regenerates only from a fresh current-source/review receipt. Existing persisted adaptation history/restore remains the recovery authority.

## Media family and SDK audit

- Qwen-Image, FLUX/FLUX.2, MiniMax H3, Wan, LTX, SeedVR2 and RIFE remain explicit family contracts. Discovery is not a runnable workflow. The existing configured original registry is not replaced or auto-enabled.
- The original image bridge still requires broker/provider guards and only supports its real single-image transport; reference conditioning is rejected when unsupported. Cover/storyboard, character-reference, edit and multireference schemas remain distinct from executable capability claims.
- T2V/I2V/start-end/continuation remain schema-level operations routed only through configured original video/motion owners; no mock fallback is advertised as a real video workflow.
- SeedVR2 accepts source/upscale schema and RIFE source/target-FPS schema; neither is relabeled as text generation. Added finite sound-design schemas specify prompt and duration. Unsupported fields and invalid bounds fail closed.
- Existing Agent/Workflow SDK is finite declarative authoring, exact source/model receipts and trusted local recipe execution. Existing Import adapter is bounded candidate extraction; existing Model Adapter SDK is the original bound host protocol. The new exporter protocol reuses the reviewed export owner. These are contracts, not a third-party executable extension system.
- Executable plugins remain `DENY_ALL`. No sandbox/trust/capability/file/network gates were relaxed.

## Extended-creation audit

Existing translation workspace, terminology/locked terms, translation-memory choices, comic/webtoon layout and export, interactive stories, visual novels, shared-universe snapshots/pins, structured/project fork/compare/human merge and template library remain their existing owners. They already provide versioned authoring/review/history/source fencing and explicit recovery restrictions. This patch extends existing engine export and fixes scoped catalog/source reads rather than introducing another translation/comic/universe/template module. Translation model quality, target comic rendering/font coverage and engine interoperability retain their original limits; no new broad REAL_VERIFIED claim is made.

## Verification and handoff boundaries

`tests/test_surface_freeze_media_engine_adapters.py` parameterizes real File and PostgreSQL persistence, and tests actual production `/api` + `/api/v1` trusted-session/membership composition in addition to isolated adapters. Coverage includes real forked branch sources independent of mainline, original unified Task Center projection/cancel, read-only exact-result Review Inbox pointers, sanitized provider failures, literal-preserving Godot export, exact review/CAS, permission changes during processing, source invalidation, foreign actor/branch, cancel/late output, interrupted restart/recover/resume, disabled flags/V1, concurrent dispatch claims, configuration failure, media read-back and Godot schema/checksums. PostgreSQL requires the existing hosted real PostgreSQL gate; local execution does not emulate it.

Opus may redesign layout, labels, spacing, control grouping and visual feedback inside existing Production/Tasks/Review surfaces. It must preserve owner routing, feature dependencies, all authoritative IDs, rational timing, source versions, CAS, actor/branch scoping, result-review digest, no automatic replay, no implicit model configuration, fail-closed visibility, local-only privacy, NOT_RUN/MOCK_ONLY disclosures and DENY_ALL execution policy.

### Supplemental local run receipts (2026-10-07)

All commands used the existing isolated `r2-run.sh` and repository test venv, with `-m 'not postgres_backend_only'`. They are supplemental File-profile evidence, not the final exact-SHA hosted gate.

- Expanded existing + new media/engine/voice/comic/translation/director suite: 366 passed, 1 unchanged skip, 314 opposite-profile deselected. The unchanged skip is the pinned OFL font fixture, which the hosted gate supplies.
- After passing explicit caller scope into media/audio/subtitle/lineage source validation: 96 passed, 90 opposite-profile deselected in the focused regression subset.
- Final new-surface file: 34 passed, 33 opposite-profile deselected. This includes actual JSON Schema validation, source-scope non-fallback, current mounted Task Center cancellation and Review Inbox pointers.
- `git diff --check`: clean.
- Ordinary implementation/self-review verified cancellation/retry late-output and concurrent review fences and corrected provider-error disclosure and Godot whitespace preservation. This is not the historical independent audit; that audit remains BLOCKED and was not retried.
- Real PostgreSQL, target engines, real models, GPU and production media quality: NOT_RUN locally. No new skip was added, no original test/assertion/skip changed, and no fake PostgreSQL path was used.
