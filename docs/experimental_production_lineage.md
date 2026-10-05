# Experimental asset lineage and controlled production replay

## Scope and ownership

A09 extends `AssetLibraryService.source_asset_ids`, its cycle checks, verified content and recoverable deletion. It does not create another asset library. New origin/operation/license declarations, parent and chapter versions/digests, producer metadata and declaration history are stored with the existing asset. A compare-and-swap write preserves concurrent changes. The reserved `asset_lineage_v2` parameter cannot be introduced or modified by legacy caller-controlled generation parameters.

The asset view resolves every parent against the current exact project/branch. Deleted parents remain recoverable tombstones; inaccessible or missing parents become anonymous unavailable placeholders. No denied parent ID or title is returned through the projection or conflict body. Metadata/version/content drift is explicit. Existing edges cannot be removed by the annotation form. No cache cleanup deletes original files.

Replacement impact is the exact recorded downstream asset DAG, current and historical media brief/task references, shot/storyboard references and motion-frame/result references. Unrecorded dependencies are UNKNOWN. There is no inference of complete project impact and no automatic replacement, regeneration or approval. Other U06 domains, satisfied-result locking and selective multi-domain recomputation remain separate unfinished work.

## Flags and routes

- `asset_lineage_v2`: `/experimental/production/assets`, detail, versioned annotation and impact.
- `production_manifest_v2`: immutable manifests, export, preflight and replay pointers; requires asset lineage and the existing cover/storyboard and adapter-registry flags.
- `model_broker_v2`, when enabled: explicit fresh route preview, original shared budget reservation, final dispatch guard and settlement. A missing configured broker fails closed.
- `V1_ACCEPTANCE_MODE=true` closes all new routes. Disabled capture creates no new provenance on original media tasks. Replay tasks reject normal media execution/retry entry points even while the older media features remain enabled.

Both API prefixes mount the same authorization and services. Writes recheck current actor/scope/branch, source versions, feature state and budget. Export is no-store, authenticated and a closed allowlist. Raw prompts remain only in the existing private media brief; public exports contain digests and numeric parameters, no arbitrary labels, manuscript, reference IDs, paths or credentials.

## What a manifest proves

New media tasks record the observed App/Python/zlib versions and adapter/workflow implementation digests, the exact declared model identity and a model implementation hash only when available. Historical tasks without original runtime evidence remain incomplete; the current runtime is never imputed as their original runtime.

The current supported production request records its actual candidate count, input versions/digests, configuration difference and output digests. Its media request contract does not expose seed or arbitrary model parameters; seed is explicitly `NOT_SUPPORTED_BY_MEDIA_REQUEST`, not a fabricated default.

The UI separates input traceability, environment reconstruction, replay eligibility, deterministic protocol evidence and byte equality. A seed is never treated as a quality guarantee. License declarations are not legal verification.

## Replay and recovery

1. Select a successful existing media task and explicitly record a manifest.
2. Run preflight. It compares current source/privacy/adapter/model/runtime/output evidence and, when required, obtains a fresh broker decision for the exact registered route.
3. Explicitly create a replay with the preflight digest and idempotency key. A new **existing-media-domain task** and replay pointer commit in one ExperimentalStore transaction. No dispatch occurs during creation.
4. Explicitly execute. The latest authority, dependency evidence and shared budget are checked again at dispatch and before accepting the result. No old cloud authorization is reused. Results remain in the original media proposal/review flow.
5. Cancel through the replay control or existing media task cancellation. A late result cannot revive it. Running tasks after process loss are marked recoverable/unknown; no automatic retry occurs. A new preflight and new task are required.

A crash between task creation and reservation leaves a discoverable queued task. The next explicit execution checks current dependencies and recovers the same idempotent reservation. An uncertain create can be retried with the same idempotency key. Concurrent execute attempts cannot cause the losing request to settle the winning request's in-flight ledger. An unavailable/corrupt persisted replay output never receives a byte-equal claim.

## Verification boundaries

The complete software path runs the existing deterministic synthetic PNG adapter: `SYNTHETIC_PROTOCOL_ONLY`. It creates actual PNG bytes, compares exact digests after restart and never claims model quality, GPU determinism or a real production image model. Unconfigured adapters, incomplete real-model identity or unintegrated fresh cloud authorization produce specific blockers. No paid API, private credentials or model download is used.

Tests are parametrized for File and disposable real PostgreSQL and cover actual mounted APIs, authorization, exact flag dependencies, legacy-route bypass, cycles, source/privacy drift, missing/deleted/denied parents, CAS, parallel idempotency, restart, cancellation, export redaction, budget settlement and output integrity. The React tests exercise actual scoped client calls, explicit creation/execution, error/draft recovery, in-flight cancellation and late response fencing. Real model quality and third-party renderer compatibility remain NOT_RUN.
