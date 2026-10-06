# Registered original local-media execution

## Implemented scope

A07 image benchmarks, U06 selected cover/storyboard refresh and A13 observed production replay reuse the original local image authority. The default-OFF flag dependencies and the V1 acceptance fence are unchanged.

- `MediaAdapterRegistry(original_registry=asset_provider_registry)` projects only the exact, enabled original `LocalImageAdapter`. A1111 and the shipped standard ComfyUI checkpoint workflow are supported. Read-only catalogs do not probe, install, start a runtime or generate an image. Replaced/disabled registrations disappear. Unknown families and arbitrary imported graphs remain non-executable.
- The wrapper preserves original registration, runtime config, model metadata and implementation identity. The original dispatch path validates live metadata, then invokes the coordinator's current-source/current-route/current-budget guard immediately before inference. A supported local route is one image per task. Reference conditioning is explicitly rejected rather than ignored.
- The ordinary media UI can select the registered route, queue one image with an explicit seed and inspect the existing brief. A separate preflight checks its current broker quote; execute requires that exact server-bound task quote. No generation occurs while queuing or cataloging. Existing media tasks, pending-review proposals, image decoding, preview and asset approval remain the authority.
- The existing benchmark executor accepts homogeneous IMAGE_WORKFLOW sets, at most six samples and one explicit sample per step. It creates the original media task, records its pointer/source digest/parameters/output hash/decoded dimensions/status/latency, and reserves/dispatches/finalizes the existing broker ledger. Media rules measure decoding, not aesthetic quality. Mixed text/image sets are rejected. Text benchmarks and unverified evidence imports remain usable. Text-only blind preference does not pretend to compare serialized media receipts.
- U06 uses current cover or storyboard preparers and exact stored shot dependencies, preserves locks and original outputs, binds selected sources/configuration/privacy to preflight, and creates new tasks without dispatch. Real routes require broker admission; unsupported source domains stay manual.
- A13 records actual supported seed/options and observed environment. Only an actual runtime-reported 64-hex SHA-256 is admitted as model evidence. No model-name hash is promoted to a weight hash. Missing historical evidence or absent model digest still blocks replay. Runtime version remains unknown when unreported, and rebuildable is false; a freshly admitted non-deterministic rerun is distinguished from environment reconstruction and byte equality.
- A13 can capture U06 results only through U06's current origin validator. The refresh/preflight binding survives replay and generic media visibility. Turning U06 off hides its manifests and derivative replay records. Parameter identity is bound to the original task; free-form negative prompts stay in its private parameters and are represented by a digest in manifests. Public exports keep the closed numeric/hash allowlist.

## Honest limits

VIDEO_WORKFLOW is import-only because the original HTTP video executor has no equivalent current proven-local broker admission. This patch does not implement a new video provider, cloud egress coordinator, arbitrary graph executor, reference-image workflow, TTS coordinator or media-family adapter.

Reported SHA-256 is runtime evidence, not a claim that the app independently read/verified weights. The external model runtime version, GPU and model quality remain unknown unless reported and independently accepted. Seed is not a determinism guarantee. Any observed equality in tests concerns the fixed synthetic PNG fixture only.

A real local runtime does not report monetary usage through this protocol. Its quoted amount is an estimate. After dispatch, unknown actual billing stays `UNKNOWN_UPSTREAM`; the author must explicitly reconcile it using the existing broker controls. Cancellation discards late results but cannot retract already-sent computation. Failed/cancelled registered-local tasks require a new task/preflight rather than an implicit replay.

No real model/GPU inference, paid call, model installation/download, credentials, merge, release or deployment was performed. Independent security review remains platform-BLOCKED; no review was requested, retried or rerouted.

## Verification

- Shared original-dispatch seam: `04e6d31`; two injected-delegate tests passed. See [backport candidate](REGISTERED_MEDIA_DISPATCH_BACKPORT.md).
- Feature core: `e49a5cf`.
- Focused new original-registration and mounted composition checks: 13 passed / 13 real-PostgreSQL parameterizations skipped locally. This includes actual-wrapper late-cancellation/result discard, unchanged unknown billing, and exact-task quote binding. Both `/api` and `/api/v1` use the production composition and existing authorization; fake only the original runtime response transport.
- Stable change-impact/production/new-route suite: 49 passed / 49 PostgreSQL skipped. Stable remaining broker/media regression suite: 68 passed / 58 PostgreSQL skipped (overlapping tests are not added into one claimed total).
- TypeScript build check and UI token guard: PASS.
- Focused UI: 39 passed across registered media, broker/benchmark, media recovery, change impact and production lineage panels. Covers single-image route/seed selection, exact preflight before execution, cancellation during a pending response, late-preflight suppression after scope change, capability matching, and original review behavior.
- The new `r4-registered-media.spec.ts` journey is collected. It starts an isolated Node loopback A1111 protocol fixture and uses the actual discovery → validate → register → explicit fixture-license acknowledgment → enable → original registry pipeline. It then exercises UI generation, A07, U06 and A13, retains unknown billing until explicit fixture reconciliation, preserves original outputs and captures three desktop viewports. There are no mocked app/API responses. Fixed synthetic PNG bytes and synthetic checkpoint digest are explicitly labeled as test evidence.
- Local Chromium/browser/visual execution is NOT_RUN due to the previously confirmed EPERM boundary. No local retry or screenshot claim. Hosted CI must execute the collected journey.
- Real PostgreSQL execution is NOT_RUN locally. New test parameters carry `file_backend_only` / `postgres_backend_only` through the existing fixtures; hosted PostgreSQL is required.

Aggregate regression results and hosted receipts belong to the parent checkpoint. Earlier in-place regression runs while implementation was still changing are not treated as final code receipts.
