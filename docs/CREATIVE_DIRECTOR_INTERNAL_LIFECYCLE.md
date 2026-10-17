# CreativeDirector internal execution lifecycle

Status: **internal-only implementation; primary and independent scoped verification passed**.

This slice exercises actual original File owners and a mocked verified external-local adapter wire. It does **not** enable public independent Director model preview, dispatch, content, refresh, candidate adoption or generic generation review. Public capability advertising remains unchanged, including `source_chapter_anchor_required: true`. No live-model quality or end-to-end feature completion is claimed.

## Source and ownership

- Worktree: `studio-creative-lifecycle`
- Branch: `work/dot-creative-lifecycle-20261017`
- Baseline: `3087f53276e42c57bf4baed2a76fbf75380d947e`
- Five changed runtime owners: `app/creative/director_binding.py`, `app/model_execution.py`, `app/jobs.py`, `app/creative/generation.py`, `app/creative/proposals.py`
- Additive test files: `tests/test_v2_creative_director_invocation.py`, `tests/test_v2_creative_director_execution_lifecycle.py`, `tests/creative_director_execution_fixture.py`

The original Director coordinator owns internal preview, admission and result reads. The original broker owns reservation, final-hop dispatch and terminal accounting. The original JobManager owns worker execution and persistence. The original PreparedTextInvocation, LocalModelInvocation and TextModelNode own the adapter-facing request/transport. No second engine, coordinator, registry, schema, lock class, fake chapter or synthetic Graph identity was introduced. Author, anchored Director, Graph and SCREENPLAY/adaptation behavior is retained.

Existing foundation tests and all other old tests remain byte-exact. The frozen actual Graph/SCREENPLAY fixture remains SHA-256 `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`; its literal original payloads and hashes pass the protected regression tests.

## Closed invocation contract

The original coordinator adds private `_preview_independent`, `_dispatch_independent` and `_read_independent_result` seams. No public API or UI calls them. Preview accepts only strict bounded parameters and an explicit synthetic-data choice, and requires the original captured `DiscoveryAuthority` object with a nonempty principal and live guard, plus the current actor/scope guard.

Only this trusted internal preparation creates the transient typed capability and separately sealed Creative branch of PreparedTextInvocation. It binds the exact manager, Job object and UUID, request payload, cancellation Event, adapter, route fingerprint, source binding, actor, scope, incarnation and output/deadline bounds. Exact broker-hook identities are bound once. Graph's original `bind`/`validate_job` remain Graph-only; public `start_prepared`, Author/Graph preparation and unsealed direct worker/shared-start calls still reject Creative before side effects. The private worker is claimed once.

Private seals defend the supported-caller and persisted-payload boundary. They are **not** a security sandbox against hostile arbitrary in-process Python reflection or monkeypatching. The seal, invocation, guards and hooks are never serialized or reconstructed on restart.

Execution authority is separate from `generation_content_available`, which remains false for this domain, including genuine completed internal jobs. The ordinary local route still requires the exact verified `LocalTextAdapter`, LOCAL_VERIFIED evidence and an EXTERNAL OLLAMA/LLAMA_CPP runtime. Synthetic execution requires explicit opt-in and remains subject to the original packaged-runtime prohibition. Local TEXT, current license, exact selected route/binding hash, known-zero unchanged price and budget configuration are checked through the original broker. There is no cloud fallback, retry, probe, launch or alternate transport.

## Source/transaction composition

The public passive source validator retains its original rejection of preheld owner/nested raw transactions. A distinct private locked validator derives the actual active raw scope snapshot from the original store and requires its matching active original Creative owner lease. It never accepts a detached caller snapshot as current authority. Any active Creative view must refer to the same source evidence.

Every source checkpoint validates the actual saved nonarchived independent STORYBOARD, empty chapter/evidence/ancestry/privacy dependencies, exact source ID/version/digest, project incarnation, actor and scope, using the original Creative validation. Before/after canonical checks reject mutation during validation. Legitimate surrounding admission/ledger writes remain permitted outside that read checkpoint.

The supplied owner callback requires the original raw scope first. For File, it holds original `project_operation`, checks the existing canonical marker without provisioning, then enters the original Creative owner lease. It is passed directly to broker preview/reserve/dispatch/finalize and held through raw atomic commit. Missing/deleted/replaced owners cannot be silently recreated. All authority/source/policy leases exit before provider I/O; the real-adapter mocked wire tests assert no raw/Creative scope or owner is held.

Host/actor/scope/features, Host binding ABA, exact source/proposal/admission version, complete queued receipt, broker decision/fingerprint/binding hash, price/budget/license and prepared request are rechecked at preparation, admission, final-hop dispatch, every provider event, settlement and final persistence boundaries. Broker guard callbacks re-read the active locked decision, rather than trusting pre-transaction reads. Budget configuration is frozen; the reservation's own expected inflight/accounting changes are not mistaken for configuration changes.

## Admission, completion and uncertainty

The durable proposal uses `CREATIVE_DIRECTOR_INTERNAL_EXECUTION_V1` with explicit private states:

1. `INTERNAL_MODEL_PREVIEW`: exact internal preview only; no live invocation is persisted.
2. `INTERNAL_MODEL_EXECUTING`: durable `ADMISSION_PENDING` plus original UUID/request digest before reservation, followed by the exact `QUEUED`/`RECORDED` reservation receipt before worker start.
3. `INTERNAL_MODEL_UNKNOWN`: admission/reserve/start/write uncertainty, retaining `UNKNOWN_NO_AUTOMATIC_REPLAY`. No exception path releases an ambiguous hold or allocates a replacement request.

After successful execution, the proposal's `INTERNAL_MODEL_EXECUTING`/`QUEUED` fields deliberately remain the **admission receipt**, not a statement that generation is still running or that a candidate is ready for review. The original Job terminal record and original ledger are authoritative for completion. There is no promotion to `CANDIDATES` or `NEEDS_REVIEW`.

The original worker requires exact event Job identity and response provider/model, a nonempty completed text exactly matching all deltas, a completed finish reason, and unchanged byte/deadline bounds. Late/duplicate/mismatched/incomplete output fails closed. Cancellation, authority revocation, changed cancellation identity, UNKNOWN admission, failed settlement, owner loss and uncertain final saves suppress isolated output. The original separate `execution_outcome` and once-only accounting claim are preserved, including when cancellation or revocation arrives during slow settlement. A continuously failing terminal save leaves only an in-memory uncertainty receipt; it does not claim durable completion or replay.

Private result reads require the original live sealed job, successful execution and terminal hook, a matching durable completed Job receipt, and the exact SETTLED zero-cost ledger. They recheck current authority/policy/bounds and return detached internal text only. **Private result access expires at the original deadline**, even if the provider completed earlier. It confers no candidate/adoption authority.

Restart strips every transient authority/invocation/hook, terminalizes interrupted records and clears interrupted Creative output without dispatch or accounting. Completed passive records remain unavailable to generic consumers.

## Public isolation

Public projection classifies before copying model/history data. A bounded iterative scan examines exact structural contract markers in known model fields and historical snapshots, including nested lists, so deleting a current marker cannot uncover prior private request data. Malformed/over-depth model history fails closed. It does not substring-scan user-authored prose. Public list/read projection redacts the internal model payload; public preview/dispatch/refresh/review/cancel paths reject the internal domain before generic version/review handling. Existing mounted conflict-response sanitization is unchanged. Rule-assisted independent proposals without internal execution and anchored legacy workflows retain their existing behavior.

## Primary verification

Normal interpreter startup and the actual original-runner child origin were verified using the established clean test interpreter, before product imports. Every final check used unchanged `scripts/run_v2_checks.py`, current worktree paths and owned profile/basetemp directories. Source was frozen for execution. No primary failures or repair reruns occurred.

| Check | Result | Receipt stem under `docs/delivery/v2-development/` |
|---|---|---|
| Internal invocation/lifecycle, foundation/persistence and protected backend regressions | 699 passed; 410 deselected; zero skipped | `creative-lifecycle-backend-r1` |
| Actual offline PUBLIC wheel/sdist, payload/closure/safety contracts | 87 passed; zero skipped | `creative-lifecycle-packaging-r1` |
| Forced TypeScript build | PASS | `creative-lifecycle-types-r1` |
| Production Vite build | PASS | `creative-lifecycle-build-r1` |
| Original UI token guard | PASS; 52 files | `creative-lifecycle-tokens-r1` |
| Six original bounded Director/Graph UI suites, one worker/no cache | 100 passed | `creative-lifecycle-ui-r1` |

Backend selection used `-m 'not postgres_backend_only'`, retaining neutral tests; the 410 exclusions are marker selections, not passes or skips. Existing Starlette deprecation and Vite chunk-size warnings remain. The new tests exercise real File owners and actual worker threads with a mocked wire on the real verified external-local adapter: Host/scope/feature/ABA revocation, source/route/license/price/budget changes, exact invocation and queued receipt tampering, real deadline passage during wire/settlement, UTF-8 byte overflow, event/response failures, cancellation, owner loss/recreation, persistence/accounting uncertainty, no replay, restart and mounted public/history isolation. These are protocol tests, not model-quality tests.

All **2,552** final runner-tracked source hashes are identical across final origin/backend/packaging/frontend runs, and each before/after source bracket is unchanged. The separately checked PUBLIC manifest is unchanged. Two actual wheels and two actual sdists were built offline using the verified existing packaging interpreter, without installation. Artifact construction/inspection is not installed-package runtime acceptance.

Exact commands, raw logs, source brackets and receipts are indexed in the [primary evidence index](delivery/v2-development/creative-lifecycle-origin/primary-evidence-index.json). Actual archives and saved build/stage receipts are identified by [artifact hashes](delivery/v2-development/creative-lifecycle-origin/artifact-hashes.json). Final bounded hashes are in [core freeze r3](delivery/v2-development/creative-lifecycle-origin/core-freeze-r3.sha256).

## Independent verification and remaining gates

Independent verification passed **514 cases with 227 PostgreSQL-marked exclusions and zero skips** in 75.31 seconds. These reruns overlap primary coverage and must not be added as unique test totals. The reviewer independently checked all **2,552** current source hashes, exact source brackets and core freeze, **657** unchanged foundation test sources, the literal golden fixture and unchanged PUBLIC manifest. It fully payload-hashed the two actual wheels and two actual sdists, including current Jobs/model-execution/binding module bytes; these archives were inspected, **not rebuilt**. Seven final primary receipts and their raw log hashes were verified. No scoped blocker remains.

The [independent report](delivery/v2-development/creative-lifecycle-independent-review.json) has SHA-256 `4a5a629ad9dff92d882c7991c52f9017e4cc392dc83e2d259d2098c4589221af`. The [complete evidence index](delivery/v2-development/creative-lifecycle-origin/evidence-index.json) binds primary and independent receipts, exact logs, artifacts and this report.

Public independent Director activation, PostgreSQL execution/lock behavior, live provider/model quality, browser/geometry, native desktop, Windows, packaged-runtime execution and full product/release acceptance remain unverified or unavailable. No installation, live provider, remote push, merge, tag or release was performed in this slice. Earlier historical `creative-lifecycle-*` evidence files in this repository concern different slices; only the explicitly linked `*-r1`/origin receipts above establish this slice's claims.
