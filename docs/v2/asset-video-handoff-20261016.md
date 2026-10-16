# Exact asset-to-video draft handoff — 2026-10-16

Baseline: `fa713761ff9a108c1e38ca2c0f8b1644fa6e6f33`. Containing local commit identifies delivery. IMPLEMENTED bounded frontend handoff; independent media portfolio remains PARTIAL.

## Original contracts audited

`production_execution_models.py` already requires exactly one image source for `m7.video.i2v` or one video source for `m7.video.v2v`. `production_contracts.py` replaces the historical reserved descriptors with the independent original ProductionExecutionService commands. Original provider resolution and `studio_video_execution.py` check the specific operation capability; the local provider explicitly advertises `video_to_video: False`, while the HTTP provider requires explicit configuration. This slice neither enables a reserved backend nor changes provider, dispatch, policy or permissions. A V2V draft may be filled without a configured executable provider; the panel explicitly states capability dependence and that the local route cannot execute reference video.

The original `useStudioMediaExecution` already owns single video-operation sources, optional V2V reference purpose, provider/prompt/parameters, jobs, preview and consent. The existing session-only IMAGE handoff is generalized with an optional target rather than a second authoritative store. VIDEO references now traverse the same dirty-navigation guard into the original production panel. User choice of I2V or V2V is required; mismatched asset kind is rejected. No operation/provider/route is automatically changed.

## Bounded behavior

Explicit metadata review and a second read before explicit apply require the exact original asset ID, version, SHA-256, compatible kind, undeleted state, no manual mask and matching current list metadata. No substitution with the latest source, byte download or generation preview occurs. A single empty original source slot is populated atomically; duplicate or different existing sources are never replaced. Prompt, provider, parameters, license note, reference purpose and output jobs are preserved. Original edit ownership clears stale execution preview/confirmation and cloud consent; later preview, creation, execution and review remain separately explicit and capability-gated.

Existing source/client/request/draft/permission/busy/configuration epochs and UNKNOWN guards remain authoritative. Added same-tick loading protection to the shared handoff, so metadata reads cannot begin during configuration loading even through a retained callback. Delayed acceptance rejects operation/draft/source/client/busy ABA, changed intent, cancellation and unmount. IMAGE and TIMELINE regressions remain included.

## Verification

`asset-video-handoff-20261016.json` records exact commands, exits, times, source hashes and retained receipts. 242 selected mocked UI/contract tests and 30 PUBLIC tests pass. TypeScript, Vite, test discovery, token guard, diff checks and 487-file PUBLIC closure pass. The initial 81-test pass is retained as historical evidence. No backend or persisted contract changed, so no new File owner test was necessary. Mocked UI is not browser/GPU acceptance.

Tests cover mounted IMAGE/VIDEO explicit operation and metadata acceptance, three-target dirty-navigation cancellation, I2V and V2V exact snapshots, no configured V2V execution, unchanged source slots, malformed/deleted/wrong-kind metadata, consent clearing, UNKNOWN and ABA/loading guards. Existing video graph, storyboard, shot binding and runtime-contract suites are included.

## Remaining boundaries

STORYBOARD handoff, broader output portfolio and durable media-draft recovery remain open. Unified DeliveryCenter entitlement producer remains BLOCKED; no synthetic grant. P0 BLOCKED / R3-GATE HOLD; production Prompt Adoption writes remain disabled. Browser/visual/native/performance, PostgreSQL/P0/security lifecycle, Windows/GPU/provider/user computer and full RC NOT_RUN. No paid calls, push or hosted CI because CI cost is unknown; no main merge/tag/release. Parent independent review precedes the next tracked slice. Preserve historical evidence and denial/environment/cost boundaries.
