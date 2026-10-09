# M3 Local Model Onboarding — M3-A Host Authority and Bounded Consent

**Status: M3 PARTIAL / M3-A bounded checkpoint. Final local evidence: 2026-10-09 15:47 UTC.**

This checkpoint adds host-authorized scope preview and explicit bounded scan
consent through the existing LocalDiscoveryService and Model Center. The complete
selected **53-file owner range** now passes on File (**2,109 passed / 1,099 skipped**)
and fresh real PostgreSQL 17.11 (**2,076 passed / 1,132 skipped**), with matching
stable **1,677-input** source maps and verified normal PostgreSQL shutdown.
Fresh full frontend is **1,981 passed / 8 existing skips**; build/45-file token
guard and **279** infrastructure/catalog cases pass. Written inventory is
**10,362 nodes, inventory only**; this is not full-product execution.

The final checkpoint and exact receipt links are in [§§12–13](#13-final-local-m3-a-checkpoint--1547-utc).
Earlier development failures, pending observations and the diagnosed first PG
failure remain timed history, not the latest status. New-SHA hosted CI and M3
browser/visual acceptance remain pending publication; local browser is blocked.
Component compatibility, hardware profiles, real inference, complete install
guidance and optional API consent/budget workflows remain partial or unexecuted.

## 1. Identity and compatibility boundary

- Repository/branch: `1785235376-blip/AI-Novel-Studio`,
  `feature/v2-narrative-platform`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47).
- Published M2-A parent: HEAD `99c43b6892038233c390be2ae61acb669163d0b5`,
  tree `69d69ffe71838263069d164a0a07b39b5f4a4333`. M2 remains **PARTIAL**.
- M3 publication identity: the actual containing commit SHA/tree must be bound
  to this checkpoint through the PR 47 publication receipt after commit. It is
  intentionally not self-embedded or substituted with the published M2 parent.
  Sections 12–13 identify the exact tested source map and staged catalog tree;
  neither is presented as a final published M3 commit.
- Requirements trace to roadmap §§4.1, 6.1–6.4, 24 GATE-M3, 26 and 29, with
  the existing [feature matrix](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md) and
  [model integration criteria](AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md).
- Original M0/M1/M2 text and immutable historical conclusions remain preserved.
  No old test, selector, timeout, golden, skip or full-roadmap status is weakened
  to make this checkpoint pass. M12 remains **USER_APPROVAL_REQUIRED /
  LOCAL_REQUIRED / NOT_RUN**.

The production discovery surface intentionally has a **security-tightening
compatibility change**, including when V2 is off. A project collaboration role
does not establish host provenance. The previously shared Model Center mutation
helper remains unchanged for its legitimate Model Center callers, but is no
longer the production discovery authorization mechanism. Turning V2 off does not
declassify cached model paths, hardware, settings or registrations.

## 2. Existing owners and stronger host authority

`app/main.py` mounts `discovery_api.py` at both `/api/model-center/local-ai`
and `/api/v1/model-center/local-ai` with `discovery_authority.py`. This applies
to snapshot, environment, preview, scan/status/cancel, settings, runtimes,
validation and registration/enable/disable/remove routes, not just the new POST.

- Packaged mode requires the **current bootstrap manager and its live issued
  session** from the existing registry, plus the required packaged/collaboration
  configuration. A token merely registered elsewhere is insufficient.
- Nonpackaged local-host mode requires a direct loopback connection and a
  credential already registered in the existing trusted-session owner.
  Nonpackaged collaboration mode fails closed, regardless of project role.
- Forwarded-identity headers, remote peers and a mismatched supplied Origin are
  rejected. Loopback, actor headers or client role claims alone grant no access.
  The in-process `testclient` transport seam is test support, not a header bypass.
- `TrustedSessionResolver.binding_generation()` tracks the existing binding's
  incarnation. Revoke/re-register of the same token cannot preserve prior scope
  authority. No session, token, Vault, persistent ACL or parallel credential
  registry is introduced by this slice.
- Authority is captured and rechecked before/after protected work and response
  delivery. Mutation guards are passed into the original owner, including after
  metadata probes and immediately before the existing atomic file replacement.
  These checkpoints do not claim transactionally atomic revocation with every
  external filesystem operation.
- Discovery success/error responses carry `Cache-Control: no-store`,
  `Pragma: no-cache`, `Referrer-Policy: no-referrer` and `nosniff`; the outer
  discovery middleware also covers early response paths. Validation failures
  return bounded codes without echoing request paths or credentials.

The existing ModelCenter, runtime registry/bridge, stable identity, Broker, Vault
and JobManager remain the only owners of their respective responsibilities.
Host discovery permission is not model enablement or inference authority.

## 3. Preview, confirmation and the original scan worker

### 3.1 Closed request/response contract

The new V2-gated routes exist under both mounts:

1. `GET /onboarding/scan-scope?include_common_model_dirs=false` previews the
   current plan. The query accepts literal `true` or `false`, default **false**.
   Common directories require a separate explicit choice for this preview;
   the choice does not change saved discovery settings.
2. `POST /onboarding/scan` accepts only `scope_digest` (exactly 64 lowercase
   hexadecimal characters) and `confirmed: true`. Extra expansion fields,
   missing confirmation and coerced truthy values are rejected. Admission
   returns 202 and reuses the original scan/status/cancel lifecycle.

The public preview declares `execution_scope: BACKEND_HOST`,
`inference_status: NOT_RUN`, `requires_confirmation: true`, exact local service
endpoints/probe paths, configured/common roots, hardware categories, metadata
inspection kinds and limits. Preview construction uses bounded path identity
metadata; it does not enumerate directories, read model contents, contact
services or collect hardware facts. A GET is not an implicit scan.

`discovery_scope.py` builds the plan; `LocalDiscoveryService` owns its ephemeral
receipts. Up to **16** previews are retained for a fixed **120-second monotonic
TTL**, with nonce, service-instance identity, actual host principal and the full
private plan bound into the digest. Public response edits cannot expand the
private plan. The digest is a consent receipt, never an access credential.

The plan includes validated runtime options, configured sources, saved settings,
resolved roots, path identity facts, relevant enabled registrations, platform,
actual probe limits and adapter identities. Confirmation rebuilds and compares
effective inputs before admission. Changed/expired/foreign/restarted/stale
receipts fail closed. An identical live receipt reuses its admitted current scan,
including after fast completion; a competing running scan conflicts, and a
consumed receipt cannot start another worker. TTL expiry still applies. Issuing
other previews does not evict the current scan receipt while it remains live.

### 3.2 Effects disclosed before confirmation

The scan is passive with respect to model execution, **not a promise of zero
state changes**. The scope explicitly includes:

- `CONFIGURED_GGUF_HEADER` reads, executable version-resource metadata and
  bounded executable-directory sibling inspection for configured llama.cpp.
- `REGISTERED_GGUF_HEADER` safety reads for relevant enabled llama.cpp
  registrations, including files outside the recursive roots.
- `RECURSIVE_MODEL_METADATA` for approved configured/common roots.
- OS/CPU/RAM observations and applicable Windows DXGI GPU/VRAM and system
  CUDA/DirectML component-presence metadata.

Existing reconciliation can disable stale registrations/routes and **persist
registration safety updates**. The preview and UI disclose both effects. It
does not register or enable models, start runtimes, execute arbitrary binaries,
load weights, call a cloud model, download/copy/delete weights or persist the
per-preview common-directory choice. No inference or license grant follows from
a header, filename, advertised model list or component-presence observation.

### 3.3 Exact defensive bounds and platform limits

Values below come from the current source, not measured throughput guarantees.

| Bound | Current contract |
| --- | --- |
| Saved inputs / deduplicated service plan | 16 configured runtimes; 16 configured roots; at most 20 planned services |
| Model list / HTTP body | 512 models per service; at most 4,194,304 response bytes, using the captured client limit |
| Network / scan time | Request timeout at most 2 seconds; 45-second scan budget checked between bounded operations |
| HTTP request scope | Declared per-service probe paths only; maximum count is the sum of those paths |
| Recursive metadata roots / entries / files / depth | At most 32 roots, 5,000 entries, 2,000 model files and depth 3; shared entry/file budget |
| Model metadata | 262,144-byte metadata bound; preview declares up to 262,152 read bytes for header framing; GGUF and Diffusers have their own bounded read semantics |
| Executable metadata | At most 256 sibling entries; Windows version resource at most 1,048,576 bytes; executable is not run |
| Other inspection bounds | At most 2,048 registered-model metadata inspections; existing Windows adapter enumeration cap 128 |
| Consent cache | 16 previews; fixed 120-second lifetime; no persistent consent authority |

Known service endpoints and saved trusted nondefault loopback runtimes are reused;
there is no port sweep, LAN/public scan or automatic fallback. Credential-required
services have no discovery probe paths and fail closed in configured-runtime
probing; separately disclosed registered-file safety inspections can still apply.
Local endpoint validation, redirect/proxy rejection and original
cancellation/deadline behavior remain in use.

`ScopeCancellation` carries the current host/feature guard, frozen plan and
captured clients into the original worker. Guard/cancellation/path checks surround
bounded reads and late-result adoption. A new or changed unplanned registered
file is not silently adopted. Shared original scan results remain truthful
partial/cancelled/error observations, not proof of a complete machine inventory.

Metadata reads and directory enumeration use descriptor-relative no-follow
ancestor traversal where POSIX supports it; regular-file checks reject special
objects. Windows retains bounded pathname/reparse checks and **does not have the
same atomic no-follow ancestor guarantee**. Windows race immunity or native
runtime acceptance is not established by Linux fixture tests. A bounded operation
already in flight need not stop instantaneously when cancellation is requested.

## 4. Frontend consumer and no-model path

The V2 Model Center entry now offers preview, an optional unchecked common-root
choice, explicit confirmation and cancellation before scan. It shows the backend
host distinction, exact service scope, hardware categories, limits, metadata
inspection details and stale-registration persistence. Paths and manual runtime
configuration are advanced details. Skipping/collapsing discovery leaves manual
creation available; no required model installation or port entry is introduced.

`localAiDiscoveryOwner.ts` and the captured client in `localAiDiscoveryApi.ts`
freeze the original session/local-host context for one mounted consumer. Owner,
project and local-session epoch changes fence old responses; an explicitly empty
captured credential does not adopt a later global token. Model Center and the
environment summary remount/reset scoped consumers, abort pending reads and
discard stale preview/polling results. Permission denial clears protected state;
scope conflicts/expiry require a fresh preview rather than automatic scan retry.
Editing settings or runtime configuration invalidates the displayed preview.

`AIEnvironmentSummary` only reads the prior explicit scan. It labels cloud/backend
facts separately from the user's computer and retains `NOT_RUN` for inference and
Windows acceptance. Detect, Validate, Register, license/configuration review and
Enable remain separate existing actions. A displayed `verified_capabilities`
metadata check does not become real generation evidence.

Current full frontend/build evidence is recorded in §12. Actual browser acceptance
is not inferred from unit checks, successful builds or JSX inspection. No visual,
keyboard, responsive-layout or screenshot approval is claimed for M3 here.

## 5. Verified development evidence, never summed

Original logs were read and their SHA256 hashes recomputed against their JSON
receipts at this checkpoint. Each listed receipt records parent HEAD `99c43b...`,
`sources_changed_during_check: false` and equal before/after input maps. The maps
differ between runs, so these are separate development snapshots. Receipt links
retain exact command, source paths/digests, environment and UTC interval.

| Receipt | Actual result / duration | Recorded input count |
| --- | --- | --- |
| [Host-cache first reproduction](docs/delivery/v2-development/dev-m3-host-cache-first-repro.json), 14:28:16–14:28:24 | **FAIL: 4 failed**, 5.13 s; nonpackaged collaboration could read host cache with V2 on/off on both mounts | 1,662 |
| [Host-cache correction](docs/delivery/v2-development/dev-m3-host-cache-fixed.json), 14:31:26–14:31:35 | **23 passed**, 5.40 s | 1,664 |
| [Scope service first](docs/delivery/v2-development/m3-scope-service-dev-01.json), 14:32:02–14:32:08 | **27 passed**, 3.50 s | 1,665 |
| [Legacy first](docs/delivery/v2-development/m3-scope-legacy-dev-01.json), 14:32:43–14:32:53 | **FAIL: 1 failed / 158 passed**, 7.27 s; cancellation lost already-observed partial service candidates | 1,665 |
| [Host-authority matrix](docs/delivery/v2-development/dev-m3-host-authority-matrix.json), 14:34:49–14:35:06 | **296 passed**, 13.62 s | 1,666 |
| [Legacy correction plus scope](docs/delivery/v2-development/m3-scope-legacy-dev-02.json), 14:35:41–14:35:52 | **186 passed**, 8.15 s | 1,666 |
| [Mounted onboarding first](docs/delivery/v2-development/dev-m3-mounted-onboarding-first.json), 14:38:21–14:38:30 | **14 passed**, 5.67 s | 1,669 |
| [Mutation guards](docs/delivery/v2-development/dev-m3-mutation-guard-integration.json), 14:39:54–14:40:08 | **223 passed**, 10.13 s | 1,669 |
| [Scope service hardening](docs/delivery/v2-development/m3-scope-service-dev-02.json), 14:40:46–14:40:56 | **209 passed**, 7.25 s | 1,670 |
| [Mounted precommit revocation](docs/delivery/v2-development/dev-m3-mounted-precommit-revoke.json), 14:41:07–14:41:17 | **23 passed**, 6.52 s | 1,670 |
| [Scope concurrency/replay hardening](docs/delivery/v2-development/m3-scope-service-dev-03.json), 14:43:10–14:43:19 | **215 passed**, 7.03 s | 1,671 |

The first failures are retained; later passing snapshots do not erase them.
Selections overlap and cannot be added together. No full File backend, real
PostgreSQL, final full frontend/build/token, final catalog/manifest or exact-source
hosted M3 completion has been established by this table. Actual user Windows/GPU,
real local inference, paid API execution and quality review are **NOT_RUN**.

### 5.1 Later service development receipt, 14:49 UTC

[Scope service development 04](docs/delivery/v2-development/m3-scope-service-dev-04.json)
finished at **14:45:01 UTC: 216 passed**, 7.25 seconds. Its **1,672-input**
before/after maps agree and the recorded source-drift flag is false. The raw
log SHA256 was independently verified as
`1083a351fa6dc6f294cc4896726448c7a38fc906afdfbd2a9ccdbc06e34f6f19`.
This adds the registration-reconciliation deadline check to development coverage;
it is another overlapping snapshot, not final integrated evidence. The original
14:44 table and failure history above remain unchanged.

## 6. Separate M2 hosted finding and correction under development

The published M2 push [run 37943398984](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37943398984)
and PR [run 37943412489](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37943412489)
are separate events. The push log records source `99c43b...`; the PR independent
media log records merge SHA `7f0d911549b04e8dbb7cf078316ad74c42095449`, with the
same tree `69d69ffe...`. They are not one combined run or a published M3 result.
The parent observed original V2 workflow/geometry and TCP jobs passing in both.
Each independent-media job actually finished **6 passed / 2 failed**, at exact
labels `关联目标` and `已保存创作图`.

The retained push [first-failure log](docs/delivery/v2-development/m2-ci-browser-113863292053-first-failure.log)
has SHA256 `a8a58b19931011079524f51d01dc180743297af4aa3882b2dbd510cb7865fc9b`;
the PR [first-failure log](docs/delivery/v2-development/m2-ci-browser-113863336723-first-failure.log)
has SHA256 `9edcdfb25aaf49dce68745d7b304e60be9f796c2973d7599466920b2251b5d1d`.
The development reproduction identifies implicit select labels including option
text. The narrow production correction adds nine explicit `aria-label` values
in three creative components, preserving old selectors/timeouts and geometry.

[Select-label development evidence](docs/delivery/v2-development/m2-select-labels-development.json)
retains **RED 3 failed / 1 passed → GREEN 4 passed**, plus a **47-pass** nearby
selection. All three raw log hashes were verified. These worker logs lack full
before/after source maps and are not final integrated proof. Hosted revalidation
is **PENDING**. Local browser is **BLOCKED**; no blocked artifact access was
retried or replaced by another route, and no trace/screenshot was inspected here.
Hosted Windows jobs cover only their existing native/package contracts, not the
user's Windows/model/GPU acceptance.

## 7. Remaining gate and initial verification plan — 14:44 UTC

| Roadmap / baseline requirement | M3-A advancement | Still open |
| --- | --- | --- |
| START-02; MODEL-01/02/03/04 | Actual host authority, closed preview/consent, bounded configured/common metadata and existing service reuse | Final integration and real authorized host/runtime observation; no generic service enumeration |
| START-03; MODEL-07/09 | Distinct discovery/metadata/registration/enable states and explicit `NOT_RUN` | Full requested lifecycle vocabulary and real execution evidence |
| START-05/06; MODEL-08/19/20/21 | Skip/no-model path and current blockers remain visible | Need-specific source/license/size/dependency/download/install/resume/cleanup guidance |
| MODEL-05/10/12/13/14/15 | Existing adapters and declared metadata preserved | Complete component compatibility, modality adapters and real generation/quality |
| MODEL-17/18 | Bounded host metadata, unknown facts stay unknown | Measured 8 GB / 12 GB / RTX 5080 16 GB + 64 GB profiles; actual peak memory/speed/quality **LOCAL_REQUIRED** |
| MODEL-23/24/25/26 | Existing Broker/Vault/budget owners preserved; no cloud fallback added | Full optional API disclosure/consent/budget/reconciliation UX; paid execution **BLOCKED / NOT_RUN** |
| GATE-M3 | Useful host-private bounded onboarding foundation | **PARTIAL**; this report does not complete the full M3 roadmap |

Before a publishable checkpoint, freeze actual source and verify the selected
integrated owner/File/real-PG tests, full frontend/build/token checks, current
catalog/manifest and preserved old test inputs with exact receipts. Keep browser
and hosted outcomes separate from local contracts and do not substitute old M2
successes. Bind the real end SHA/tree only after commit/publication. Continue safe
nondependent work without claiming missing M1 storage, M2 media execution,
complete M3 model/API or M12 Windows gates have closed.

## 8. Append-only planning hardening update — 2026-10-09 14:55 UTC

**Provisional development update; source freeze is still pending.** Scope
planning and confirmation replanning now have a fixed **5-second cooperative
budget**, exposed as `limits.planning_budget_seconds`. `planning_check()`
rechecks live authority and the shared planning deadline between each runtime,
configured-root and registered-file metadata operation. `planning_lock()` waits
for existing Model Center/discovery owner locks in intervals of **at most 50 ms**,
rechecking authority/deadline rather than waiting indefinitely. It never holds the
discovery lock while acquiring the Model Center lock.

Planning-budget expiry reports `LOCAL_AI_SCOPE_BUDGET_REACHED`; revocation retains
its fail-closed code. A failed/revoked/over-budget planning attempt does not issue
a new preview or consume consent by starting a scan. Confirmation also retains
the existing receipt-expiry and final admission checks. These are cooperative
boundaries: they do not forcibly interrupt an OS metadata call already in flight.
The original **45-second scan budget**, **120-second receipt TTL** and **16-preview
cache bound** are unchanged. The 5-second budget is additional admission/planning
protection, not a shorter model runtime timeout or proof of real inference.

[Planning development receipt](docs/delivery/v2-development/m3-scope-planning-dev-01.json)
ran **14:51:47–14:51:59 UTC**, with **224 passed** in 9.16 seconds: 65 new scope
cases and 159 existing discovery/environment cases in that selection. Its log
hash was independently verified as
`cd416c990ad58c4fe76bcebc9953a6667b93b031a20ec1a1d6b1881e66823c02`.
The receipt explicitly records **source drift**: before/after inputs changed
**1,673 → 1,674**, with `tests/test_v2_discovery_browser_fixture.py` added during
the run. The service-owned files did not change in that comparison. The passing
execution remains **development-only**, not an equal-final-source or aggregate
PASS; all earlier failures and source-bound receipts remain intact.

The next acceptance input is still being prepared for the existing independent
hosted-browser configuration: original HTTP/File/UI and original session binding,
with synthetic discovery-only adapter/hardware and new independently configured
projects. This is a fixture/acceptance authoring update only. No browser has run,
no visual approval or final catalog/manifest coverage is inferred, and no paid
provider, actual user Windows or real model inference is involved. Final integrated
source identity and evidence remain pending; full M3 remains **PARTIAL**.

## 9. Source freeze and terminal local checks — 2026-10-09 15:05 UTC

**Latest checkpoint: source frozen at 15:01 UTC; M3 remains PARTIAL.** The preceding
sections are retained as timed development history. Integrated owner File and real
PostgreSQL are still running at this observation. Full frontend, build/token,
infrastructure/catalog and inventory checks below are now terminal. No published
M3 commit or browser execution has been established.

### 9.1 Exact source and corrected catalog authority

The final local input map contains **1,676 paths**. Its canonical JSON SHA256
(sorted keys, compact separators) is
`aefdbfd9884879ab2e17b42754c8ae7cbb6ecd54de4b8e192c9b158e6fe22259`.
The catalog-owner regression, build, full frontend, infrastructure/catalog and
browser collection receipts each contain this exact map, equal before/after maps
and `sources_changed_during_check: false`. Their recorded HEAD remains the
published M2 parent; this map identifies the uncommitted tested inputs.

`refresh_product_api_catalog.py` now narrowly refreshes discovery's current
host-authority/dependency and V2-gate annotations. The old catalog otherwise
retained the removed shared Model Center mutation helper as discovery's observed
owner. Other owner annotations are preserved. The new
[catalog-owner regression](docs/delivery/v2-development/dev-m3-discovery-catalog-owner-final.json)
finished **3 passed**, 5.63 seconds, with matching source map and log hash
`44a6d733745a63733c33565b46b9c8ca575ccef33bfa3b07e98cc3fc78410e13`.
This does not create or change a product authorization decision.

[Catalog generation](docs/delivery/v2-development/catalog-8cbb5bc7af09.json)
is bound to staged tree `8cbb5bc7af09e7d40165312e64b13c0175d5792a` and records
**2,111 mounted method/path operations**, M3 **+4 / −0** from M2's 2,107.
Cumulative inventory is 1,833 starting operations + 278 additions, with no removals.
Both prefixes are separately inventoried. The application source fingerprint is
`6a6bfbc80bf2ee2f5d6f536f6d038cf43ec25c92ec357b5aee768a04dbfa83e7`.
All four generated catalog/OpenAPI file hashes match the generation receipt.
The staged generation tree is not an invented final/published M3 commit tree.

### 9.2 Terminal frontend, build and infrastructure checks

| Receipt / UTC interval | Actual result | Verified log SHA256 |
| --- | --- | --- |
| [Full frontend](docs/delivery/v2-development/stage-m3-full-frontend.json), 15:01:59–15:03:09 | **1,981 passed / 8 existing skips**, 261 passed files / 2 skipped files; 70.47 s | `85b889c4b551a65af17a3d945bc7e6817aa11bf20959c9de742b4f099dc6a345` |
| [Build](docs/delivery/v2-development/stage-m3-build.json), 15:02:00–15:02:45 | **PASS**, TypeScript, Vite and 45-file UI token guard | `e15cc9d152154cc8f4409dfffcc5a1786e41061237a48a519a2742e2e2820e60` |
| [Complete infrastructure/catalog](docs/delivery/v2-development/stage-m3-complete-infrastructure-catalog.json), 15:03:32–15:03:45 | **279 passed**, 9.86 s; original infrastructure/TCP harness and surface-catalog selection | `cb8d9c1025ccfe5b5c99df0a5242bddb05200c33955b9b9612c96c1fe0af8db1` |

The Vite result retains large-chunk warnings: App **900.90 kB** and
ExperimentalWorkbench **628.01 kB** uncompressed. No warning threshold was
relaxed. These checks do not constitute browser screenshots, responsive geometry,
real-model generation, hosted full-backend acceptance or full M3 completion.

### 9.3 Written backend inventory and actual browser collection

[Independent collection review](docs/delivery/v2-development/stage-m3-collection-review.json)
and [additive review decision](docs/delivery/v2-development/stage-m3-manifest-review-decision.json)
confirm **10,335 nodes = published M2 10,178 + 157**. The additions are 7 fixture,
3 catalog, 59 host-authority, 23 mounted-onboarding and 65 scope cases. All published
M2 nodes remain in order; old test/gate bytes and historical skip policy are
unchanged. The frozen 9,151-node baseline remains untouched with SHA256
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.

[Independent recollection/write](docs/delivery/v2-development/stage-m3-manifest-written.json)
finished at **15:03:41 UTC** with **10,335 nodes**, zero collection errors,
`tests_executed: false`, status **INVENTORY_ONLY**. The actual written
`.github/ci/coverage_manifest_v2.json.gz` SHA256 was independently verified as
`498c3059954528fc4db2676b3aedce8bed6fff3b758f55f45bb943bebaebe36a`.
Neither collection nor manifest writing is backend test execution.

[Actual Playwright list output](docs/delivery/v2-development/stage-m3-browser-collection.json)
finished **15:03:31–15:03:32 UTC**, with the same stable 1,676-input source map
and verified log SHA256
`85c09419fdacd9d1ba607c160a6a59e9dfe385a5c0206fefbedd9f423a19fd60`.
It lists **7 original live + 11 independent live cases**; the latter retains the
prior eight and adds three M3 enabled/default-off/acceptance-mode cases in separate
projects. This is **INVENTORY_ONLY / NO_BROWSER_EXECUTION**, despite the collection
command's exit-zero status.

The new acceptance input exercises original File/HTTP/React and the actual
discovery authority/consent/worker, with a test-only closed synthetic metadata
adapter and synthetic hardware. Its fixed fixture identity is registered through
the original trusted-session owner, then bound through the original local-session
UI. It does not replace application HTTP routes with frontend mocks or discover
real host models. Owned empty fixture paths, no-launch guards and explicit
test-owned cleanup confine its effects. The authored enabled case covers preview,
cancel/re-preview, common-root choice, legacy bypass rejection, explicit confirm,
polling and synthetic report; gated projects assert no probes. Viewport screenshots
are authored expectations, not captured/approved images at this checkpoint.

The earlier [fixture self-check](docs/delivery/v2-development/dev-m3-ui-browser-harness-final.json)
has **7 passed**, 25.06 seconds, with explicit source drift during development;
its verified log hash is
`01fd503b893804917a7d500da30699d1b2c0222e8e26612cdaca437eee4fc2b0`.
Its name does not override the drift or turn TestClient/subprocess fixture checks
into Chromium execution. Final integrated owner receipts are awaited separately.

### 9.4 Still pending at this checkpoint

The 52-file selected original-owner File and actual PostgreSQL 17.11 integration
runs have not yet supplied terminal receipts here. They are not the full 10,335-node
manifest. Exact published M3 source/hosted revalidation and actual browser/visual
review remain pending; local browser stays blocked. M2 hosted history is being
recorded separately and cannot be substituted for M3 results. Full component
validation, model profiles, real inference/quality and install/API workflows stay
PARTIAL; user Windows and paid API execution remain NOT_RUN.

### 9.5 Integrated File result, 15:08 UTC

[Original-owner File integration](docs/delivery/v2-development/stage-m3-integrated-owner-file.json)
finished at **15:07:32 UTC: 2,082 passed / 1,099 skipped / 1 warning**, 310.49
seconds. It began at 15:02:15 UTC. This is the recorded **52-file selected owner
integration**, including original asset/project/workflow/media contracts and
M1/M2/M3 discovery/session/model-center owners, **not the full 10,335-node backend
manifest**. Its 1,676-input before/after maps are equal and match §9.1 exactly;
source-drift is false. The raw log SHA256 was independently verified as
`a36f7980a53bafc66b1067c5b9359c24bba2c4268183f936c67d95c26bc253d0`.

The skips retain 1,098 existing opposite-profile cases plus the existing actual
Windows native acceptance case guarded at
`tests/test_provider_runtime_v2_host_hardware_inventory.py:407`. That native test
was skipped on this host, not passed or replaced by a mock Windows result. The
warning is the existing Starlette/httpx TestClient deprecation. Real PostgreSQL
integration remains running at this observation; no cross-profile total,
full-manifest execution, browser/visual PASS or full M3 completion is inferred.

## 10. Terminal published-M2 hosted record — 2026-10-09 15:20 UTC

The [M2 terminal manifest](docs/delivery/v2-development/m2-ci-terminal.json),
SHA256 `f69554807ecf8e43b291eaa42ae81ef902baf807a85cbabfa7dd6e93cbee325a`,
now records all five watched workflows naturally terminal, attempt 1, with no
agent rerun or cancellation. All **29** retained job-log hashes and byte counts
were independently verified: 27 new terminal logs plus both unchanged media
first-failure logs. This is evidence for published M2 HEAD `99c43b...` and its
separate PR merge checkout `7f0d911...`, same tree `69d69ffe...`; it is not M3 CI.

| Workflow/event | Terminal result and precise boundary |
| --- | --- |
| Cloud CI push `37943398984` / PR `37943412489` | **FAIL each**: 7 successful, 3 failed and 1 cancelled job per event. Full product/strict-backend acceptance did not pass. |
| Cloud File execution, each event | **CANCELLED / INCOMPLETE** at the configured 20-minute job budget; last logged progress 98% push / 95% PR. No terminal full-backend test count. |
| Cloud PostgreSQL execution, each event | Shard 0 **3,349 passed / 1,740 skipped / 5,089 deselected**; shard 1 **3,289 passed / 1,800 skipped / 5,089 deselected**. All four execution jobs succeeded, but both strict aggregate jobs **FAIL** at the prerequisite; later provenance/full-collection reconciliation was skipped. Do not combine shards/events into an aggregate PASS. |
| Cloud frontend, each event | **1,923 unit passed / 8 skipped**; **104 browser passed**, plus **2 separate real TypeScript-client tests**, typecheck/build/tokens PASS. The two client cases are not browser passes. |
| Original V2 browser, each event | **7 live + 8 geometry passed**, kept separate from other frontend/browser selections. |
| Independent-media browser, each event | **6 passed / 2 failed**, preserving the exact select-label failures and pending correction revalidation described in §6. |
| Original TCP, each event | **2 original TCP + 102 harness cases passed**, separate from File/PG aggregate acceptance. |
| Windows package/contracts, each event | **59 native contract + 3 V2 environment cases passed**, package smoke PASS; interactive desktop, user acceptance and real model inference NOT_RUN. |
| Local Interop push `37943399064` / PR `37943412326` | **PASS each**; File and PostgreSQL each report **345 passed / 68 skipped** per event. Windows reference 8 checks and native-boundary 33 checks remain MOCK_ONLY counterparty evidence, not real two-product/user-desktop integration. |
| Shared R123 `37943412383` | Workflow success means **all three known defects reproduced RED** on baseline `c6f2126115b52e17839d48efea091dc21ec08c61`, tree `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`. It is not current-head product acceptance. |

The 104 frontend browser cases comprise geometry 9, Interop 12, business 2,
experimental 7, R4 63, export 1, functional surface 9 and branch surface 1.
Counts are maintained per event/selection; no cross-event or cross-profile
stitching is performed. Original XML/complete-collected-coverage artifacts were
not independently downloaded/reconciled. No denied artifact, screenshot or trace
retrieval was attempted. Successful Windows and MOCK_ONLY jobs retain their
bounded execution level. Full M2 remains PARTIAL, and this terminal record neither
repairs its failing jobs nor validates the uncommitted M3 candidate.

## 11. First M3 PostgreSQL failure and transport recovery — 15:20 UTC

[The first 52-file M3 PostgreSQL integration](docs/delivery/v2-development/stage-m3-integrated-owner-postgres.json)
is now terminal **FAIL: 2 failed / 2,047 passed / 1,132 skipped / 1 warning**, 811.97
seconds, run **15:02:17–15:15:57 UTC**. It records equal before/after **1,676-input**
maps matching §9.1 and no source drift. The raw log hash was independently verified:
`c754654a4221918105b75c1b23a56c748749ebc0569d20487ad01690e74eb0cf`.
The exact unchanged failing tests are:

- `tests/test_r2_workflow_execution.py::test_workflow_api_requires_session_and_hides_other_owner`
- `tests/test_r2_workflow_execution.py::test_direct_agent_jobs_do_not_bypass_workflow_owner_isolation`

Both tracebacks report `KeyError: 'id'` after the original `/api/novels` create
response was parsed. The failure log alone does not establish that response's
cause or authorize weakening either assertion. The first failed result is
retained; there is no integrated PostgreSQL PASS at this observation. The
[SQL runtime receipt](docs/delivery/v2-development/stage-m3-integrated-owner-postgres-postgres-runtime.json)
confirms actual disposable loopback **PostgreSQL 17.11**, database
`v2_creative_tests`, port 55432, via the recorded version/database/address/port
query. Matching normal-shutdown evidence is still pending here.

A separate [15:13 transport-recovery receipt](docs/delivery/v2-development/m3-upload-transport-recovery.json),
SHA256 `33c09526bd5d4d0ae6434d52902a8c7ffcccaf097f8c43bc5132e154cf410fa0`,
records an execution-tool disconnect while reading bounded evidence chunks before
Git blob upload. An incomplete chunk failed validation and was discarded before
blob creation. The same executor recovered; the original PostgreSQL session was
not restarted and the branch had not moved. The 1,676-input map still matched
completed File evidence. Its PG-pending statement is the state at recovery time,
not a denial of the subsequently observed terminal failure above.

Current File/frontend/build/catalog successes remain their actual bounded results;
they do not erase this failed PG integration. Diagnosis/correction and any honest
fresh verification are pending. Publication identity/hosted browser revalidation,
full M3 model/API scope and user Windows/inference remain open.

### 11.1 Confirmed reused-database cause and normal shutdown, 15:24 UTC

The [isolation diagnosis](docs/delivery/v2-development/m3-postgres-isolation-diagnosis.json)
now establishes **test-database reuse**, rather than inferring a product defect
from the missing `id`. The actual original create API correctly returns **409**
for both fixed titles already present in `v2_creative_tests`. SQL shows those
rows were created at **14:04:35 UTC**, within the prior M2 PG run
**13:52:24–14:06:21 UTC**, before the M3 run began. The unchanged workflow test
file's SHA256 is
`43fb770f9ecd0518a0bc1def0713daacf766ee4292ad0e47f40424b33f90fb9d`.
No old assertion or fixed title was changed and no previous row was deleted or
renamed to hide the conflict.

The [first diagnostic](docs/delivery/v2-development/dev-m3-pg-create-conflict.json)
failed before HTTP due to an unused invalid `novel_repo` import; its script/log
are retained with verified log SHA256
`7d3a40829a605190a5dd710c3a88a4944e564e71c069a34fe742954daa645f42`.
The [corrected diagnostic](docs/delivery/v2-development/dev-m3-pg-create-conflict-response.json)
then recorded the actual SQL identity, existing timestamps and both 409 responses;
its verified raw log SHA256 is
`44ef4efe6bb0abdedaf11aed62e0842a23e4cce0bb2ee94dc9978f3792ccdbc4`.
These diagnostics explain the retained failed integration; they do not turn it
into a pass.

[Original-run server log](docs/delivery/v2-development/stage-m3-integrated-owner-postgres-server.log)
now verifies normal fast shutdown: request at **15:15:57.677 UTC**, completed
shutdown checkpoint and `database system is shut down` at **15:15:57.687 UTC**.
Its independently verified SHA256 is
`201931b3e56839599131312aaa92add7de58cd3a2dca6a94a92d38c5a0bbe082`.
The earlier shutdown-pending statement remains its timed observation.

A narrow correction to `scripts/run_v2_postgres_checks.py` and new isolation
regressions is now in progress: explicit fresh owned database mode, rejection of
pre-existing database names, original migrations and preservation of previous
data. Product source and original tests stay unchanged. The complete owner
selection plus new runner tests will require a new source freeze and fresh
source-bound checks; the earlier 1,676-input map remains historical evidence for
its own runs, not the final identity of the forthcoming runner correction.

## 12. Fresh-database correction and current-source checks — 15:42 UTC

**Current local candidate: 1,677 source inputs; full M3 PARTIAL.** The earlier
1,676-input File/PG/frontend evidence, including the failed PG attempt and its
confirmed diagnosis, remains historical. The current source-map SHA256 is
`964ad4a0c317f43d65e2aa8793d6f87b5e6630b977ee269803c42c6248fd143f`.
All current-source execution receipts in this section have matching before/after
maps and `sources_changed_during_check: false`. The new full selected-owner File run is
terminal; the fresh full selected-owner PostgreSQL run is still pending.

### 12.1 Narrow verification-runner correction and smoke proof

`scripts/run_v2_postgres_checks.py` adds explicit `--fresh-database` with an
explicit, validated `v2_*` database name. It refuses an existing name rather than
clearing/reusing its data, creates from `template0`, verifies the actual
loopback database/user/OID and empty application-object inventory, then applies
all 20 original sorted migration files with their recorded hashes. The previous
diagnostic reuse mode remains explicit in receipts. It records
`existing_database_untouched` when rejecting reuse, retains created databases
for evidence, and stops a server only after successful startup has established
ownership. Ambiguous/failed startup does not authorize stopping another server.
No product source, original test assertion/title, migration or previous row was
changed to obtain a pass.

[Final runner/helper regressions](docs/delivery/v2-development/dev-m3-pg-isolation-final.json)
are **32 passed**, 2.89 seconds, including 27 new isolation cases and the existing
runner selection. Verified raw log SHA256:
`da1c29f2fb7797902dc1db2b165fb4ced675503bf7a105ce628a12911018d94d`.
This is a separate overlapping check, not a number added to owner integration.

[Fresh real-PG smoke](docs/delivery/v2-development/stage-m3-fresh-postgres-smoke.json)
reran the **same two original failing tests unchanged** and finished **2 passed**,
3.84 seconds, at 15:30:33 UTC. Verified log SHA256:
`9a0ea97c3257780bfc5ed40cccab69bc995c6e59736f6da1eda9ab218ac75005`.
Its [runtime receipt](docs/delivery/v2-development/stage-m3-fresh-postgres-smoke-postgres-runtime.json)
identifies actual PostgreSQL 17.11, database `v2_m3_isolation_smoke_20261009`,
OID **31259**, absent before creation and empty before migrations. All **20**
original migration hashes were checked against source and applied successfully;
normal server stop/cleanup and retained database are recorded. This confirms the
narrow isolation correction, but does not replace the complete selected-owner
run or erase the first failed attempt.

### 12.2 Fresh-source terminal checks and exact hashes

| Fresh receipt / UTC interval | Actual result | Verified log SHA256 |
| --- | --- | --- |
| [53-file File owner integration](docs/delivery/v2-development/stage-m3-fresh-owner-file.json), 15:31:49–15:37:12 | **2,109 passed / 1,099 skipped / 1 warning**, 317.00 s | `0f3b07907279d7934bd315ce65b3167547e4e711fbe99f6aff4be0434297ad7c` |
| [Full frontend](docs/delivery/v2-development/stage-m3-fresh-full-frontend.json), 15:31:50–15:33:01 | **1,981 passed / 8 existing skips**, 261 passed files / 2 skipped files; 69.91 s | `59a3ff5e5a1ce8ffda79d83521d0a468ed8d07717024f84967c0c6feb4a2c9a3` |
| [Build](docs/delivery/v2-development/stage-m3-fresh-build.json), 15:31:52–15:32:36 | **PASS**, TypeScript/Vite and 45-file UI token guard; large-chunk warnings retained | `d1a35ed03e5f43273b5fd06419b839f96ae80a571d1a37019ddbff3d6d2c647e` |
| [Infrastructure/catalog](docs/delivery/v2-development/stage-m3-fresh-infrastructure-catalog.json), 15:32:44–15:33:03 | **279 passed**, 16.18 s | `716994e5aa39e8d949623205d5576510db86d3edc97221b963fb7605af912276` |
| [Actual browser collection](docs/delivery/v2-development/stage-m3-fresh-browser-collection.json), 15:32:45–15:32:47 | **7 original + 11 independent**, **INVENTORY_ONLY / NO_BROWSER_EXECUTION** | `85c09419fdacd9d1ba607c160a6a59e9dfe385a5c0206fefbedd9f423a19fd60` |

The File receipt executes the **complete selected 53-file owner range**, with
27 runner-isolation cases added to the original 52-file range. It is **not full
product execution of all 10,362 manifest nodes**. Its 1,099 skips retain the
existing 1,098 opposite-profile cases plus one existing actual Windows-native
acceptance case. The TestClient deprecation warning remains. These fresh receipts
must be used for the current candidate instead of reusing the initial 1,676-input
results merely because several counts agree.

### 12.3 Fresh catalog and written inventory

[Regenerated catalog](docs/delivery/v2-development/catalog-417922cb0fe8.json)
uses staged tree `417922cb0fe81113b3a237d318325fda60cfc857` and retains **2,111
operations**, M3 +4/−0. All four generated file hashes match. Application source
fingerprint remains
`6a6bfbc80bf2ee2f5d6f536f6d038cf43ec25c92ec357b5aee768a04dbfa83e7`:
the correction changes the verification runner and its new tests, not product
application logic.

[Fresh collection](docs/delivery/v2-development/stage-m3-fresh-collection-review.json),
[review decision](docs/delivery/v2-development/stage-m3-fresh-manifest-review-decision.json)
and [written manifest](docs/delivery/v2-development/stage-m3-fresh-manifest-written.json)
record **10,362 nodes = previous 10,335 + 27** runner-isolation cases. Old nodes
remain in order; old test/gate bytes and historical skip policy are preserved.
The actual written manifest SHA256 is verified as
`bc15318b92cae0ee7a3c581321de95f3577c684b0ced26daf9f7228ccda57715`.
This is **INVENTORY_ONLY**, not execution of 10,362 tests. The original frozen
baseline is unchanged. Browser collection similarly preserves all 7+11 cases
without launching Chromium.

### 12.4 Pending at 15:42 UTC

The complete 53-file fresh PostgreSQL selection is still running against newly
created `v2_m3_owner_20261009`; its final outcome and normal shutdown must be read
before being reported. No M3 published SHA or new hosted workflow outcome exists
in these receipts. Full-product hosted CI is a separate post-publication result,
not this selected local owner range. Actual browser/visual, user Windows/inference,
paid providers and the remaining full M3 roadmap remain open.

## 13. Final local M3-A checkpoint — 15:47 UTC

**M3-A bounded checkpoint is ready for publication with full M3 explicitly
PARTIAL.** All selected local checks are terminal on the current **1,677-input**
map `964ad4a0c317f43d65e2aa8793d6f87b5e6630b977ee269803c42c6248fd143f`.
Sections 5–11 retain development and earlier-source results; §12 contains the
fresh File/frontend/build/infrastructure/collection receipts. This section
supplies the last pending fresh PostgreSQL result and the final boundary.

[Fresh 53-file PostgreSQL owner integration](docs/delivery/v2-development/stage-m3-fresh-owner-postgres.json)
ran **15:31:48–15:45:46 UTC** and finished **PASS: 2,076 passed / 1,132 skipped /
1 warning**, 831.24 seconds. Its before/after maps are equal, the drift flag is
false, and its raw log SHA256 was independently verified as
`170f67d1a287e8f7b65d354e3d0cd6182c1016d9dc8be2628770e26d8f387e31`.
The skips retain existing profile/native-acceptance gates; they do not mean all
Windows or opposite-profile cases executed in this run. The same full selected
owner range is **2,109 passed / 1,099 skipped** on File (§12.2). Counts remain
separate by backend and are not summed into a product-wide total.

The [fresh runtime receipt](docs/delivery/v2-development/stage-m3-fresh-owner-postgres-postgres-runtime.json)
confirms actual PostgreSQL **17.11**, loopback database `v2_m3_owner_20261009`,
OID **32129**, absent before creation, zero application objects before migrations,
and successful application of all **20 original SQL files**. Each migration hash
was independently checked against source. The created database is retained;
`checks_exit_code: 0`, `server_stop: stopped`, `cleanup_status: completed` and
confirmed startup ownership are all recorded. The original reused database and
first failed integration remain preserved.

The matching [server log](docs/delivery/v2-development/stage-m3-fresh-owner-postgres-server.log)
shows the normal fast-shutdown request at **15:45:46.835 UTC**, completed shutdown
checkpoint and `database system is shut down` at **15:45:46.846 UTC**. Its verified
SHA256 is `17379372e233872eb2cbfc68d5b07354d7ba1fc9f0fe967cb749c534d5ce0ffd`.
The runtime receipt closed at **15:45:46.948761 UTC**. This is actual SQL/server
lifecycle evidence, not a substituted PostgreSQL mock or a pass inferred from a
still-running process.

Final local state:

- **PASS:** complete selected 53-file original-owner File and fresh real-PG
  integration, full frontend 1,981/8, TypeScript/Vite/45-file token guard and
  279 infrastructure/catalog checks, all on the same stable current input map.
- **INVENTORY_ONLY:** written 10,362-node manifest and actual browser collection
  of 7 original + 11 independent cases. Catalog remains 2,111 operations, M3
  +4/−0, with unchanged application fingerprint and current authority annotations.
- **Preserved failures:** first host-cache reproduction, first legacy cancellation
  regression, initial reused-database PG integration and initial diagnostic import
  failure, plus published M2's terminal Cloud FAIL/media failures. Corrected local
  results do not erase or relabel those original attempts.
- **Still pending:** exact M3 publication SHA/tree, full-product hosted CI for that
  new SHA, and actual M3 browser/screenshot/visual acceptance. Local browser is
  blocked. M2 hosted results in §10 belong only to their stated push/merge source.
- **Still PARTIAL / LOCAL_REQUIRED / NOT_RUN:** complete M3 component/profile/
  inference/quality/install/API workflows and actual user Windows/GPU acceptance.
  No paid model API, new runtime/model installation, merge or release is asserted.

The actual containing commit SHA/tree cannot be embedded as a self-reference in
this report. PR 47's publication receipt must bind the eventual real SHA/tree to
these source-bound results; the M2 parent, catalog-generation staging tree and
source-map fingerprint are never used as a replacement commit identity. This
publishable bounded checkpoint does not close the full M3 roadmap or weaken the
existing M0/M1/M2 historical boundaries.

The consolidated [pre-publication verification receipt](docs/delivery/v2-development/stage-m3-publish-verification.json)
(SHA256 `5b37cb838652f60412af1c63b9212b7a175c3c67f6a89440dcc90973a8cd7cca`)
binds all six fresh checks to the same source map, their individual receipt/log
hashes, PostgreSQL identity/migrations and both manifest/catalog identities. It
also verifies the unchanged tracked original test/workflow bytes and protected
AppShell, tokens and primitives. Its browser entry explicitly records
`tests_executed: false`; verification before publication is not a hosted-CI result.
