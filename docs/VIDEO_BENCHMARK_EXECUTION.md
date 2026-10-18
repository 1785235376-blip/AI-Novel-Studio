# Bounded local video benchmark: implementation and evidence

Date: 2026-10-18 UTC. Scope: the approved A07 local T2V benchmark slice. This is a **partial contribution to DIF-08**, not full Model Lab acceptance or a real-model performance report.

## Delivered boundary

The original benchmark surface can explicitly run one saved `VIDEO_WORKFLOW` sample through an already registered, enabled `LocalVideoAdapter`, the original `ProductionExecutionService`, `StudioVideoExecution`, durable video job owner, private Asset owner and Model Broker reservation ledger. There is no second workflow engine, background benchmark worker, automatic fallback or runtime startup.

- Video-only task sets use `NONEMPTY` as a decoded-output/receipt check, not a quality score. Existing text/image execution remains separate.
- The fixed requested preset is width 256, height 256, duration 1 second, frame rate 8 and seed 7. The original recipe's actual frame rounding and request preview remain authoritative. These are requested parameters, not measured inference throughput.
- Each sample requires an original request preview and an exact version/digest-bound confirmation. A run has at most six samples; subsequent samples require their own explicit actions.
- Admission records a server-created benchmark binding, project incarnation, task-set hash, route fingerprint, request digest, deterministic original job ID and Broker authorization digest. Public responses omit the admission binding, internal sample map, incarnation and nested run history.
- The original Production API cannot operate a benchmark-bound job without its server-owned binding. Original job creation and queue/send semantics remain in the original owners.
- The existing Production last-mile callback rechecks benchmark state and Broker reservation before provider actions. Publication/recovery check the already-held source snapshot before Asset/project locks, rather than introducing scope reads under Asset locks.
- Unknown submission is retained as the original `UNKNOWN` job and is never automatically replayed. Refresh/reconcile use the same job. Explicit recovery can continue the original proven `QUEUED` job after fresh confirmation. Reconstructing the adapter for the same persisted registration does not change its durable route binding; original Production still pins the live adapter during each wire action.
- Local cancellation fences further publication but does not claim remote computation stopped. An already-dispatched reservation remains held. A proven pre-admission failure with neither a reservation nor an original job returns to a retryable preview state; ambiguous admission does not receive that exception.
- Deadlines are checked during explicit actions/last-mile checks. This slice does not add an autonomous timer or scheduler.
- Output remains a private original `AWAITING_REVIEW` candidate. The benchmark UI can explicitly fetch authenticated candidate bytes and record evidence-level human verification. It cannot adopt, approve or publish the candidate.

## Truthful measurements and cost

The coordinator records observed task-completion latency, including admission, orchestration, polling, validation and user delay between actions. It does not call this model inference latency. `latency_ms` remains unavailable for video routing, and the observed metric is explicitly routing-ineligible. Original decoded media metadata and the private candidate digest are retained as output evidence.

Inference latency, generation FPS, tokens/second, GPU/VRAM usage, cold/warm-start performance and subjective quality remain unavailable. A successful injected-transport test is not evidence of real model inference, GPU performance or model quality.

The bounded path requires a current explicit zero external-provider-fee **estimate** and a zero reservation ceiling. Neither the `LocalVideoAdapter` name nor a loopback endpoint proves an actual free provider transaction. No special actual-zero rule was added. After dispatch, completion retains unknown actual cost in the original Broker ledger (`UNKNOWN_UPSTREAM` where finalized without billing evidence). Host compute, electricity and hardware costs are unmeasured and excluded.

An unresolved original hold may block the next sample under the existing budget policy. Only the existing explicit Broker reconciliation owner may resolve it. Tests that report a synthetic zero bill do so through the original user-reported bill path and assert `USER_REPORTED_UPSTREAM_BILL`; they do not create verified free-inference evidence.

## Exact implementation/test file inventory

Only these thirteen source/test files belong to this benchmark slice. Other camera/Storyboard/Studio changes in the shared checkout are outside this report.

| File | Ownership/change |
| --- | --- |
| `app/experimental/model_benchmark_video.py` | New bounded coordinator and passive exact local-video route projection |
| `app/experimental/model_benchmark.py` | Video composition, delegation, evidence visibility/review and routing eligibility |
| `app/experimental/model_benchmark_api.py` | Explicit video actions/private candidate read, Host/incarnation fencing and public projections |
| `app/experimental/model_broker.py` | Registered video candidate integration and routing-ineligible evidence exclusion |
| `app/experimental/model_broker_api.py` | Accurate original-video benchmark preflight support marker |
| `app/experimental/api.py` | Compose the benchmark with the original Production and Host authority owners |
| `app/creative/production_execution.py` | Narrow optional binding, dispatch/publication/recovery and private-read seams |
| `app/services/studio_video_execution.py` | Persist original decoded measurement and output-observation timestamp |
| `frontend/src/experimental/ModelBenchmarkPanel.tsx` | Exact preview/execute/recovery controls, private video viewing and truthful disclosures |
| `frontend/src/experimental/modelBrokerClient.ts` | Original scoped action and authenticated Blob methods |
| `frontend/src/experimental/ModelBenchmarkPanel.video.test.tsx` | Video UI/client lifecycle, private preview and late-response tests |
| `tests/test_v2_video_benchmark.py` | Nineteen lifecycle cases per File/PostgreSQL backend |
| `tests/test_v2_video_benchmark_api.py` | Forty mounted API cases per File/PostgreSQL backend |

This document is the additional report artifact. No catalog, packaging, migration or shared build files were changed by this report task. No commits or pushes were made.

## Final backend evidence

All backend runs used the original `scripts/run_v2_checks.py` runner, directly or through `scripts/run_v2_postgres_checks.py`, with the existing clean `.runtime/recovered-python-20261018/bin/python` interpreter and owned test temporary directories. Model traffic used an injected Comfy transport. Video bytes were generated and decoded by real CPU FFmpeg/ffprobe. No live model server, provider call, GPU inference, download or runtime enabling was performed.

Receipt links below are relative to this document. Each check receipt has a same-basename `.log`.

| Applicable coverage | Receipt | Result and qualification |
| --- | --- | --- |
| Final lifecycle implementation, File | [video-benchmark-file-r3](delivery/v2-development/video-benchmark-file-r3.json) | 44 passed, 44 deselected. Nineteen lifecycle cases are applicable to the unchanged final lifecycle source. The other 25 cases exercised the earlier API and are superseded below. |
| Final lifecycle implementation, PostgreSQL | [video-benchmark-pg-r1](delivery/v2-development/video-benchmark-pg-r1.json) | 44 passed, 44 deselected, with the same nineteen-case lifecycle applicability and superseded earlier API subset. |
| Final mounted API including incarnation fix, File | [video-benchmark-api-incarnation-file](delivery/v2-development/video-benchmark-api-incarnation-file.json) | 40 passed, 40 deselected; source unchanged during the check. |
| Final mounted API including incarnation fix, PostgreSQL | [video-benchmark-api-incarnation-pg](delivery/v2-development/video-benchmark-api-incarnation-pg.json) | 40 passed, 40 deselected; source unchanged during the check. |

The current hashes of all thirteen files above match both final incarnation API receipts. For the two lifecycle receipts, only `model_benchmark_api.py` and its API test differ from current benchmark-owned sources. The lifecycle coordinator, original-owner seams and lifecycle test remain identical. Therefore the final bounded coverage is nineteen lifecycle plus forty mounted API cases on each backend; it is not a claim that a single final 59-case combined command was run.

Coverage includes explicit approval/digest checks, single-send idempotency, unknown submission without replay, cancellation before download/publication, source/route changes, remote or unqualified endpoint rejection, private original bytes, standalone binding denial, owner recreation, adapter reconstruction and original-job refresh, unknown-cost holds, manually reconciled second admission, late sample-pointer fencing, Host revocation and sanitized conflicts.

PostgreSQL used the existing cluster `.runtime/recovered-utf8-pgdata-20261018`, database `v2_recovered_ocr_export_20261018`, OID 16384, and loopback port 55439. Runtime receipts record database reuse, no database creation and no migrations:

- [Lifecycle PostgreSQL runtime receipt](delivery/v2-development/video-benchmark-pg-r1-postgres-runtime.json)
- [Final API PostgreSQL runtime receipt](delivery/v2-development/video-benchmark-api-incarnation-pg-postgres-runtime.json)

The final API runtime receipt records `server_stop=stopped` and `cleanup_status=completed`. An independent `pg_ctl status` after the harness also reported no server running. The database was retained.

## Final API boundary reinspection

Read-only reinspection after the final tests confirmed these properties in `model_benchmark_api.py`:

1. `video_guard` captures the current Host principal, original actor/scope authority and original project incarnation. Its identity lookup uses `existing_owner_only()` plus `incarnation()`; it cannot lazily create a File owner marker and does not read a scope document. It preserves the original Asset-to-project lock order when called inside an Asset phase.
2. `current()` rechecks actor/scope, Host, incarnation and the appropriate feature gates. Missing, invalid or changed incarnation is denied.
3. The status endpoint's first run projection only determines whether stronger video authority is needed. When video runs are present, it rereads the returned run projection after incarnation capture and rechecks before returning the full status response.
4. Candidate bytes are obtained through the original binding-aware private candidate reader. `video_call` performs its final authority/incarnation check after the lower helper returns and before the endpoint constructs the byte response and Asset headers. The read route does not refresh, poll, submit or publish.
5. Success and error paths recheck current authority. A lower-owner CAS response contains only the conflict code and `current_version`; the latter is an exact integer in `1..2**53-1`, otherwise null. Booleans, objects, strings, nonpositive and oversized integers are not echoed as versions.
6. Original private-route cache headers and public video-run projection remain in place. Historical internal admission bindings are not exposed through run history or the internal sample map.

Regression tests obtain valid old private bytes, recreate or delete the owner before the helper returns, and require denial without bytes or Asset headers. Delete-only File coverage proves no marker was provisioned. A separately recreated fresh owner can read its own new candidate. A status recreation race cannot return the old run. No unresolved blocker was found at these reviewed application return boundaries. Already delivered bytes are not claimed to be remotely revocable.

## Regression and frontend evidence

- [video-benchmark-regression](delivery/v2-development/video-benchmark-regression.json): 116 passed, 49 deselected across original video foundation/API, receipt bounds, registered local media and post-interop Broker tests. This was an earlier development regression, reported source changes during execution, and predates later scoped fixes. It is **not** a final integrated release gate.
- [video-benchmark-text-regression](delivery/v2-development/video-benchmark-text-regression.json): 20 passed, 20 deselected in `tests/test_r4_model_broker.py`; unchanged source during that check. It predates later video-only API/coordinator refinements and is supporting regression evidence, not a final combined build.
- Final focused frontend run: 45 tests passed across four files, including 31 new video tests. The scoped TypeScript check passed without diagnostics. These frontend results were observed in tool output; no persistent frontend receipt/log or screenshot was saved. Do not represent them as a durable runner receipt or browser acceptance.

Frontend commands, run from `frontend/`:

```sh
node node_modules/vitest/vitest.mjs run src/experimental/ModelBenchmarkPanel.video.test.tsx src/experimental/ModelBenchmarkPanel.continuation.test.tsx src/experimental/ModelBrokerPanel.test.tsx src/experimental/RegisteredMediaPanel.test.tsx
node node_modules/typescript/bin/tsc --noEmit --target ES2022 --module ESNext --moduleResolution Bundler --jsx react-jsx --strict --skipLibCheck --esModuleInterop --allowSyntheticDefaultImports --lib ES2022,DOM,DOM.Iterable src/experimental/ModelBenchmarkPanel.tsx src/experimental/modelBrokerClient.ts src/experimental/ModelBenchmarkPanel.video.test.tsx
```

UI coverage includes explicit preview confirmation, current-sample/version fencing, original queued recovery, unknown-state read/reconcile-only behavior, cancellation, preserved text/image controls, truthful cost/metric copy, authenticated private Blob reads, no automatic playback, and aborted/discarded late reads with ObjectURL cleanup on close/refresh/scope change/unmount. Browser/visual QA was blocked and not retried. Full application build, packaging/catalog reconciliation and integrated checks remain release-owner work.

## Preserved earlier evidence inventory

The following prefixes each retain their original `.json` and `.log` under `docs/delivery/v2-development/`:

- `video-benchmark-file` — initial exploratory failure: one fixture incorrectly read a private Asset without its original project/binding context; the fixture was corrected to use the original Production candidate reader. The failed receipt is retained.
- `video-benchmark-api-file` — earlier 33-case File pass.
- `video-benchmark-file-r2` — earlier 42-case File pass, with source changes during the run.
- `video-benchmark-file-r3` and `video-benchmark-pg-r1` — lifecycle-applicable evidence described above.
- `video-benchmark-api-final-file` and `video-benchmark-api-final-pg` — earlier 28-case API passes, superseded by the incarnation fix despite the historical `final` filename. They record concurrent unrelated camera/workspace source changes.
- `video-benchmark-api-incarnation-file` and `video-benchmark-api-incarnation-pg` — current final scoped API evidence.
- `video-benchmark-regression` and `video-benchmark-text-regression` — supporting regressions described above.

The PostgreSQL prefixes `video-benchmark-pg-r1`, `video-benchmark-api-final-pg` and `video-benchmark-api-incarnation-pg` also retain their `-postgres-runtime.json` receipts. No earlier result was overwritten or relabeled as later acceptance.

## DIF-08 mapping: partial only

The expanded `PoemSeed_Studio_V2_Dot_Full_Gap_Backlog_20261019_r2(1).txt`, DIF-08, requires controlled cross-model comparison of quality, timing, peak VRAM, actual API fees, output dimensions and limitations; separate real measurements from estimates; preserve original Model Center/Provider/WorkflowRun ownership; authorize local/cloud separately; and cover 8/12/16 GB budgets with queue/unload strategies. Its acceptance includes same-character comic-panel A/B with reusable references/seeds, recoverable interruption/OOM/remote rejection, and CPU-only non-inference management.

This slice contributes an executable original-owner local-video sample path, controlled requested parameters, exact provenance/private output access, truthful observed timing, conservative billing, explicit recovery and synthetic CPU validation. It does not close DIF-08.

Still outside this slice:

- Same-character comic-panel dual-model A/B and fixed-reference comparison; no video quality-ranking or automatic model selection was added.
- Comparable model inference timing, actual GPU/VRAM peaks, cold-start/throughput measurements and 8/12/16 GB memory-budget/unload acceptance.
- Real model execution, real hardware validation, live provider interruption/OOM/remote-rejection trials and live cloud authorization/billing validation.
- Provider-reported actual invoice/usage integration for this video route. Unknown cost and existing holds remain intentional until original reconciliation.
- A general model benchmark recipe/preset library, additional modalities/operations or adoption/publishing controls.
- Full r2 release integration, packaging, catalog/manifest checks, Windows validation and visual/browser acceptance.

The broader r2 release scope remains open. This report documents only the implemented and verified bounded contribution.

## Subsequent root integration evidence

The root integration runner subsequently recorded 193 passing tests across nine
frontend files (including both benchmark suites), TypeScript compilation, Vite
production build and UI token guard in
`docs/delivery/v2-development/camera-benchmark-integrated-frontend.json` and its
original log. Source hashes were unchanged; all 3036 receipt source paths matched
committed source e96b749ad7cd6eab29befe0db051c9e1fbf4a060. Actual browser acceptance
remains NOT_RUN. The six PUBLIC wheel/catalog checks also passed with stable
sources; see `camera-benchmark-public-wheel.json`.
