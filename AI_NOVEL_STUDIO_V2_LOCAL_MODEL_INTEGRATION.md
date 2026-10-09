# V2 Local Model Integration: Existing Owners, Evidence and M3 Gates

Inspection: 2026-10-09 UTC, baseline `4350a61fb9f61acccb845fef96b24b9b1275bbd3`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47). M1 is in progress; the full M3 onboarding/runtime/download/API milestone is **PARTIAL**, not completed. Real user Windows discovery, GPU inference and model quality are **LOCAL_REQUIRED / NOT_RUN**. No user model/runtime was started, installed or downloaded in this documentation task.

The 2026-10-09 roadmap §§4–6, 20, 26 and 29 are requirements. Existing code and receipts determine what is actually implemented. In particular, **detecting a file, advertising a model, validating a protocol, generating media and approving quality are separate evidence levels**.

## 1. Single owners and extension points

| Responsibility | Existing owner / source | Integration rule |
| --- | --- | --- |
| Actual host facts | `app/provider_runtime_v2_host_hardware_inventory.py`: `WindowsHostHardwareProbe`, `build_host_hardware_snapshot` | Reuse Host inventory for CPU architecture, physical RAM and available GPU/DXGI facts. Missing facts remain unknown. |
| Runtime definitions/configuration/lifecycle | `app/model_center/domain.py`, `runtime_profiles.py`, `service.py`: `RuntimeDefinition`, `ModelCenterService`, `RuntimeLifecycle` | Preserve typed profiles, trusted configuration, stable runtime identity and managed/external distinction. |
| Model discovery and registration lifecycle | `app/model_center/discovery.py`: `LocalDiscoveryService`; `discovery_types.py`, `discovery_probes.py`, `discovery_environment.py` | Extend bounded metadata inspection; do not introduce another inventory or permission system. |
| Host-local discovery API | `app/model_center/discovery_api.py` | Every route, including reads, requires the trusted host session. |
| Execution adapters | `app/model_center/discovery_bridge.py`: `LocalDiscoveryBridge`, `LocalTextAdapter`, `LocalImageAdapter` | Publish enabled adapters into the existing text/image registries; do not execute during discovery. |
| Provider/model/runtime stable IDs | `app/stable_identity.py`; provider/model registries in `app/runtime.py` | Preserve existing UUID/identity history; display names and model-family guesses do not redefine identity. |
| Read-only selection bridge | `app/provider_runtime_v2_model_center_snapshot_bridge.py`, `provider_runtime_v2_routing_service.py` | Consume existing owners. A candidate/route snapshot is not dispatch authorization. |
| Routing, privacy and budget admission | `app/experimental/model_broker.py`, `model_broker_api.py`, `app/source_privacy.py`, `app/credential_vault.py` | Reuse current source checks, route/credential binding, budget reservations and reconciliation. |
| Task lifecycle/results | `app/jobs.py`, existing generation/media services | Use the existing JobManager and asset owners. No separate Studio queue or duplicate billing ledger. |
| User interface | `frontend/src/ui/ModelCenter.tsx`, `LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts` | Existing Model Center is the entry; capability shortages do not prevent manual Studio use. |

`architecture_id` in runtime requirements is an explicitly configured CPU architecture UUID, not detected host architecture and not an inferred family default. The snapshot bridge cannot fill it from RAM/GPU/platform observations. See [runtime requirements authority](docs/provider_runtime_v2_runtime_requirements_authority.md).

## 2. Exact current lifecycle

Use **Detect → Validate → Register → Configure/license review → Enable → authorized task dispatch/Launch**. These are distinct operations, not a one-click implication of readiness.

1. **Detect:** an explicit Scan starts a bounded worker; startup and GET do not scan. It records observations and partial failures. It does not register models, load weights or execute binaries.
2. **Validate:** passive metadata/header/protocol/workflow-structure checks. No sample generation and no executable `--version` invocation. A current evidence fingerprint is retained; local-model identity drift removes old authority.
3. **Register:** saves metadata in the existing discovery/Model Center integration, initially disabled. It does not copy weights or add routing authority.
4. **Configure:** reviewed adapter selection and license acknowledgment. Changed adapter/configuration invalidates validation or disables the record as required. Acknowledgment records the user's review; it is not a commercial-use license grant.
5. **Enable:** API `EnableInput` requires explicit confirmation; backend refreshes validation and checks adapter, capability, locality and license blockers. Current discovery publishes enabled records as **DEGRADED**, with inference still unverified. It does not preload a model.
6. **Launch/dispatch:** only a real authorized task can invoke an enabled route. Managed llama.cpp uses the selected executable/model on demand and stops the managed process after the task. External runtimes remain user-controlled.
7. **Disable/remove/restart:** disabling blocks future dispatch; removing deletes application registration metadata, not installed models. Backend restart preserves registrations but disables them pending fresh validation and explicit Enable. Unknown upstream jobs are reconciled, never automatically replayed.

Current implemented labels include `DISCOVERED`, `NOT_FOUND`, `VALIDATION_REQUIRED`, `LICENSE_REQUIRED`, `INCOMPATIBLE`, `DISABLED`, `DEGRADED` and explanatory enable blockers. The roadmap's longer lifecycle is a target semantic vocabulary; it is not claimed as an already implemented enum. `verified_capabilities` records bounded metadata/adapter evidence; `verified`/`inference_verified` remain false in discovery. No filename/header can create inference PASS or hardware `COMPATIBLE`.

## 3. Bounded discovery and safe reuse

At baseline, default probes cover Ollama `127.0.0.1:11434`, ComfyUI `:8188` and A1111 `:7860`. Under `narrative_production_v2`, LM Studio `:1234` and llama.cpp `:8080` are also probed. Existing trusted Model Center runtime definitions, configured provider sources and explicit saved loopback runtimes are reused. Non-default ports are discoverable only through trusted configuration/enumeration; arbitrary port, LAN or public-network scanning is not a solution.

- Runtime/settings limits: 16 configured runtimes, 16 configured roots, 20 deduplicated probes, 512 models per runtime; JSON responses ≤4 MiB, bounded 2-second network I/O and response reading. Scan budget is 45 seconds checked between bounded operations, not a guarantee that every operation is instantaneously interrupted.
- V2 environment inspection: up to 32 configured/common roots; at most 3 directory levels, 5,000 entries and 2,000 inspected model files across the scan. Results can be `PARTIAL`/`BOUNDED` rather than a false complete inventory.
- File types: bounded GGUF metadata, Safetensors JSON headers/structural offsets, and Diffusers `model_index.json`. Header reads are limited to 256 KiB. No tensor load, pickle deserialization, imported model class, repository code or custom-node execution.
- Fixed Windows roots include known LM Studio, Hugging Face, Ollama and ComfyUI locations plus validated cache environment settings. Users must see/approve the scan scope; explicit Scan is not authorization to traverse the whole disk.
- Root drives, UNC/network locations, symlinks/junctions and unsafe endpoints are rejected/skipped by existing guards. HTTP requires numeric loopback or canonicalized localhost; proxies, redirects, URL credentials, query strings and fragments are rejected.
- GET `/environment` returns the last explicit scan and is V2-gated. It never initiates probing. Local paths/hardware are protected local output; public catalog projections omit discovered paths.
- Current de-duplication is canonical-path and runtime-endpoint based. **Content-identical weights at different physical locations are not proven to be merged by content digest.** M3 must add bounded, truthful duplicate-location evidence if needed, without deleting or copying either file.

Common-root discovery is metadata-only. Safetensors or Diffusers files are not automatically executable candidates; bindings/components still require a reviewed adapter. Windows CUDA/DirectML system-DLL presence is recorded as `COMPONENT_FOUND_NOT_VERIFIED`; it is not a working driver, CUDA compute or inference claim.

## 4. Runtime and modality support is deliberately uneven

| Observed source | What current code can establish | Remaining boundary |
| --- | --- | --- |
| Ollama | Tags/show metadata, stable local identity, completion capability; existing local text adapter | Hosted/remote models advertised by a localhost server are blocked as local. Recheck locality before dispatch. Real text quality/GPU remains untested here. |
| llama.cpp/GGUF | Known text architecture metadata plus explicit executable/model or compatible external runtime binding | Valid GGUF alone is insufficient. CPU offload, context and real model/hardware performance need measurement. |
| ComfyUI | `/system_stats`, `/object_info`, loader binding and reviewed SD checkpoint T2I workflow structure | Current discovery bridge supports the existing SD T2I adapter. Family names do not provide FLUX/Qwen-Image/Wan/LTX/V2V/Previs execution adapters. |
| A1111 | Advertised image checkpoints and existing image adapter | Selected checkpoint and actual returned media need real runtime acceptance. |
| LM Studio / OpenAI-compatible local | Bounded model enumeration | `/v1/models` does not grant completion capability; unsupported enable path remains blocked. |
| Custom HTTP | Explicit local health metadata/declarations | Unknown execution adapter and credential binding remain blocked. |
| Safetensors / Diffusers files | Passive format/metadata observation | No implicit full component verification, weight loading, Python import or model-family execution. |
| Video / restoration / interpolation / audio / 3D | Existing specialized registries/contracts may be reused | Discovery classifications alone prove none of their end-to-end production capabilities. Each actual adapter must be tested separately. |

Retain `minimax-h3` as its disabled legacy audio identity and `minimax-h3-video` as an independent VIDEO identity. Do not rewrite old history into a different modality. Static gray-model images, Previs video and real 3D/camera data remain distinct input types; a provider must explicitly support a reference/control type before the UI offers it.

## 5. No-model operation, storage and optional paid services

No model is a prerequisite for project creation, manual text, imported image/audio/video assets, supported manual editing or independent export. M1's new manual path is still being verified; this principle must not be advertised as complete for pending NLE/3D features.

Maintain separate categories for app/runtime, referenced model locations, project/assets, cache/proxy, owned temporary files and user-selected export. Model discovery/registration never moves, deletes, copies or downloads weights. Storage cleanup must operate on an explicit owned cache/temp manifest with a preview and applicable approval. Existing ComfyUI/Ollama/model roots are not cleanup targets.

M3 download/install UX is not complete merely because these categories are documented. A future implementation must show source, current license/model card, purpose, complete dependency sizes, destination/free-space check, checksum/signature when provided, retry/resume and cleanup boundaries. New executable plugins/custom nodes or model-repository code require separate permission; metadata never grants it.

The Broker already defaults `allow_cloud_fallback=False`, binds current input/source versions and budget, and rejects unknown/insufficient capacity, unavailable credentials and unpriced upstream exposure according to policy. Existing media/audio cloud paths can explicitly report budget/egress integration blockers; do not bypass them by calling a provider directly. A complete optional multimodal API experience remains M3/M5–M8 work.

Before any paid or external route, require the user's selected provider/task, exact outgoing inputs, applicable privacy/rights review, estimate and maximum cost, credential binding and current authorization. Display local alternatives without silently selecting one. `UNKNOWN_UPSTREAM` retains exposure and needs reconciliation; cancellation is not proof the vendor stopped billing. This task authorizes no personal paid API use.

## 6. M3 executable acceptance criteria

Each case needs exact source/runtime identity, fixture or real-service classification, result and redacted receipt. These checks are **NOT_RUN for the current M1 tree**.

| ID | Action | Required observable result |
| --- | --- | --- |
| LM-01 | Open Model Center and GET snapshot/environment with all services stopped | No scan/process/download; application remains usable; later explicit scan returns bounded missing/partial outcomes. |
| LM-02 | Use no/expired host session on both `/api` and `/api/v1` discovery routes | 401, no paths, hardware, settings or registration mutation. |
| LM-03 | Scan synthetic roots containing allowed headers, malformed headers, a junction/symlink, an out-of-depth file and an oversized response | Only bounded allowed metadata read; denied targets remain untouched; partial/error codes retained. |
| LM-04 | Scan a trusted non-default saved loopback runtime and then a redirect/LAN/public endpoint | Saved trusted endpoint is usable; unsafe destination/proxy/redirect is never contacted. |
| LM-05 | Detect → Validate → Register a supported model | No generation/process/weight copy; disabled record linked to original Model Center identity. |
| LM-06 | Configure/license review → explicit Enable → one synthetic authorized dispatch | Only dispatch invokes the adapter; candidate remains inference-unverified until a separate real result exists. |
| LM-07 | Disable/remove/change configuration during a pending operation; restart backend | Older responses cannot restore authority; external files unchanged; restart requires revalidation/Enable. |
| LM-08 | Ollama advertises hosted model or changes locality/digest before dispatch | Fail closed before prompt transmission; no local label on remote inference. |
| LM-09 | Comfy lists a family but lacks required reviewed nodes/loader binding | Show precise missing workflow/adapter; no guessed workflow or automatic plugin installation. |
| LM-10 | No compatible local route, cloud disabled/unapproved, unknown price or revoked source | No paid fallback or source upload; user receives actionable blocker and manual workflow remains available. |
| LM-11 | GPU memory insufficient, task cancelled after submission or backend restarted | Truthful resource/cancellation/unknown-upstream state; no automatic repeat charge or discarded confirmed assets. |
| LM-12 | Approved real Windows runtime/model test | Record hardware, model/quantization/components, actual inputs/outputs, elapsed time, peak VRAM/RAM and quality review separately. **LOCAL_REQUIRED.** |

Existing regression inputs include `tests/test_local_ai_environment_v2.py`, `test_local_ai_discovery.py`, `test_local_ai_discovery_adversarial.py`, `test_local_ai_discovery_egress.py`, `test_local_ai_discovery_remaining.py`, the `test_provider_runtime_v2_*` files, `test_model_center_phase1.py` and `test_model_center_phase2a.py`, plus `LocalAiDiscovery.test.tsx` and API client tests.

Example isolated rerun for the engineering owner, not executed by this review:

```sh
python scripts/run_v2_checks.py m3-local-model-contracts -- python -m pytest -q --tb=short tests/test_local_ai_environment_v2.py tests/test_local_ai_discovery.py tests/test_local_ai_discovery_adversarial.py tests/test_local_ai_discovery_egress.py tests/test_local_ai_discovery_remaining.py tests/test_provider_runtime_v2_host_hardware_inventory.py
```

The historical [local-AI receipt](docs/delivery/v2-development/local-ai-environment.json) and [log](docs/delivery/v2-development/local-ai-environment.log) record **208 passed / 1 skipped**, exit 0 at 2026-10-09 04:52 UTC with recorded HEAD `7cecb9c91ea813f8a86658e8e18f2407783d1729` and stable before/after source fingerprints. That is cloud/synthetic evidence for that source snapshot, not current-source or real-model acceptance. See [Windows plan](AI_NOVEL_STUDIO_V2_WINDOWS_ACCEPTANCE_PLAN.md) and the earlier [Local AI Windows checklist](LOCAL_AI_WINDOWS_ACCEPTANCE.md) for deferred native checks.

## 7. Completion gate

M3 is complete only when safe existing-model reuse, no-port-entry normal paths, component compatibility, no-model onboarding, explicitly authorized install/API choices and failure/recovery are actually wired through the existing owners and verified at their declared execution level. RTX 5080 16GB/64GB RAM and 8GB/12GB profiles are acceptance targets, not guarantees that any named model will fit or that all models can coexist in VRAM.

## 8. Append-only M3-A host authority and bounded-consent implementation

**2026-10-09 14:44 UTC; development source, full M3 PARTIAL.** Published M2-A parent
is `99c43b6892038233c390be2ae61acb669163d0b5`, tree
`69d69ffe71838263069d164a0a07b39b5f4a4333`. Sections 1–7 above retain their earlier
source/evidence meaning. [M3 report](MILESTONE_M3_REPORT.md) records the new source
and verified development receipts; it does not mark LM-01–12 globally completed.

Production discovery now requires independent current Host provenance for all
routes and cached data, even when V2 is off. Packaged bootstrap/live issued session
or local-only direct-loopback/existing registered credential is required. A
nonpackaged collaboration role cannot authorize host scanning or path reads.
Forwarded claims, wrong supplied Origin, expired/rebound tokens and late authority
changes fail closed. The shared Model Center role helper is intentionally
unchanged. This is a security-tightening compatibility change; no new credential
or persistent consent authority is created.

V2 adds GET `onboarding/scan-scope` and POST `onboarding/scan` under both discovery
mounts. Common directories default false per preview, independently of saved
settings. Strict confirmation binds a 64-character digest and literal true to an
actual host principal, service instance, full effective plan and fixed 120-second
lifetime; at most 16 previews live in memory. Stale/expired/foreign/consumed scopes
cannot start extra work, and identical live confirmation reuses the original scan.
The original scanner, cancellation, status and 45-second bounded deadline remain
authoritative; the old production HTTP scan cannot bypass V2 consent.

Scope disclosure includes configured and registered GGUF files (even registered
files outside recursive roots), executable version resources/siblings, approved
recursive metadata and hardware categories. Existing reconciliation may disable
stale registrations/routes and persist safety state. It does not auto-register,
enable, start/load, download, delete/copy weights or call a cloud model. Discovery
metadata and header validation remain separate from actual inference. POSIX
no-follow descriptor traversal has stronger ancestor semantics than Windows
pathname/reparse checks; Windows atomic race immunity is not claimed.

The current bounds, service limits and preview behavior are detailed in report
§3.3. Development receipts cover synthetic scope/authority/replay/drift/cancel and
mutation guards, retaining first failures; final integrated File/real-PG/full
frontend/build/catalog/manifest evidence is pending. Complete component validation,
need-specific install guidance, measured hardware profiles, inference/quality and
optional API consent/budget/reconciliation remain open. User Windows and real
models remain LOCAL_REQUIRED / NOT_RUN; no personal paid API use is authorized.

### 8.1 Bounded planning hardening, 14:55 UTC

Preview/confirmation replanning now checks current authority and a **5-second
cooperative deadline** between runtime/root/registered-file metadata operations,
including at-most-50-ms existing-owner lock wait intervals. The public limit is
`planning_budget_seconds`; exhaustion is `LOCAL_AI_SCOPE_BUDGET_REACHED` and does
not issue a preview or admit/consume a scan. Already-running OS metadata calls are
not forcibly interrupted; 45-second scan and 120-second receipt TTL are unchanged.
The [224-pass development run](docs/delivery/v2-development/m3-scope-planning-dev-01.json)
records concurrent browser-fixture source drift, so final source proof is pending.
New original HTTP/File/UI fixture authoring uses synthetic discovery-only hardware
and adapters, not actual inference; browser execution and full M3 remain open.

### 8.2 Frozen-source evidence checkpoint, 15:05 UTC

At the 15:01 source freeze, stable matching **1,676-input** maps bind full frontend
**1,981 PASS / 8 existing skips**, build/45-file token **PASS**, infrastructure/catalog
**279 PASS** and the narrow corrected discovery-authority catalog regression
**3 PASS**. Catalog is **2,111 operations (+4/−0)**; written backend inventory is
**10,335 nodes**, all old test/gate/order/skip contracts preserved. Actual browser
collection is **7 original + 11 independent**, including three M3 synthetic
metadata-only cases through original HTTP/File/UI/session/discovery owners.
No browser or actual model executed. The 52-file File/real-PG selected integration
is still pending, with exact source/log/manifest hashes in
[M3 report §9](MILESTONE_M3_REPORT.md#9-source-freeze-and-terminal-local-checks--2026-10-09-1505-utc).
Full M3 and LM-12 real Windows/inference criteria remain open.

### 8.3 Integrated File checkpoint, 15:08 UTC

The [52-file original-owner File selection](docs/delivery/v2-development/stage-m3-integrated-owner-file.json)
now passes **2,082 cases / 1,099 skips**, 310.49 s, with the stable final 1,676-input
map. One skip is the existing actual Windows hardware acceptance test; the other
1,098 are existing opposite-profile cases. No actual Windows/model inference is
claimed. Real PG is still running, and this is selected integration rather than
full-manifest/browser proof. Exact log/source binding is in
[M3 report §9.5](MILESTONE_M3_REPORT.md#95-integrated-file-result-1508-utc).

### 8.4 First integrated PG failure retained, 15:20 UTC

Real PostgreSQL 17.11 was verified by SQL, but the first 52-file integration is
**FAIL: 2 failed / 2,047 passed / 1,132 skips**, 811.97 s, with stable matching
1,676-input maps. Two unchanged workflow API tests lacked an `id` after original
project creation; diagnosis and normal-stop evidence are pending. Transport
recovery did not restart the test process or change source. Published-M2 Cloud
workflows are now terminal FAIL despite successful PG execution shards and
bounded browser/TCP/Windows jobs; strict aggregates failed. See
[M3 report §§10–11](MILESTONE_M3_REPORT.md#10-terminal-published-m2-hosted-record--2026-10-09-1520-utc)
for precise per-run scope. No passing metadata/UI check establishes real-model,
paid API or user Windows acceptance, and full M3 remains PARTIAL.

### 8.5 Confirmed PG harness isolation issue, 15:24 UTC

The two first-PG failures are now traced to reused test data: SQL shows both
fixed-title rows created at 14:04:35 UTC during M2; the unchanged original API
correctly returns 409. The first diagnostic's unused-import failure is retained,
and the corrected diagnostic proves the conflict. Normal original-run shutdown
is verified at 15:15:57 UTC. [M3 report §11.1](MILESTONE_M3_REPORT.md#111-confirmed-reused-database-cause-and-normal-shutdown-1524-utc)
records hashes and exact evidence. A narrow runner-only fresh-database mode and
new isolation tests are being prepared, preserving existing data and original
assertions/titles. New source freeze and complete selected checks are required;
the first failed run and prior 1,676-input results remain historical, not rewritten.

### 8.6 Fresh-source File and local-check checkpoint, 15:42 UTC

After the runner-only fresh-database correction, current receipts bind **1,677
inputs**, map SHA256
`964ad4a0c317f43d65e2aa8793d6f87b5e6630b977ee269803c42c6248fd143f`.
The **complete selected 53-file File owner range** is **2,109 PASS / 1,099 skips**,
317.00 s; it is not all **10,362** product nodes. Freshly rerun frontend is
**1,981 PASS / 8 existing skips**, build/45-file token PASS, infrastructure/catalog
**279 PASS** and browser collection **7 original + 11 independent, inventory only**.
All these maps and logs were verified, rather than borrowing initial-source runs.

Fresh smoke reruns the original two failed tests unchanged: **2 PASS**, with
actual PG 17.11 database OID 31259, empty-before-migration proof, all 20 original
SQL files, normal stop and retained data. Runner/helper regressions are **32 PASS**;
the first integration failure remains preserved. New written inventory is
**10,362 = 10,335 + 27**, SHA256
`bc15318b92cae0ee7a3c581321de95f3577c684b0ced26daf9f7228ccda57715`,
with old tests/gates/order/skips intact. Catalog stays **2,111 operations (+4/−0)**
and application source is unchanged. Exact fresh receipt/source/log hashes are in
[M3 report §12](MILESTONE_M3_REPORT.md#12-fresh-database-correction-and-current-source-checks--1542-utc).
The complete fresh PG owner run is still pending. M3 stays PARTIAL; full-product
hosted CI awaits publication, and browser/user-Windows/inference proof is separate.

### 8.7 Final local M3-A checkpoint, 15:47 UTC

The fresh real PostgreSQL 17.11 run is now **PASS: 2,076 passed / 1,132 skipped**,
831.24 s, with the same stable **1,677-input** map as File **2,109/1,099**, full
frontend **1,981/8**, passing build/45-file token and **279** infrastructure/catalog
checks. Actual fresh DB OID **32129**, empty-before-migration proof, all 20 original
SQL hashes, retained data and normal shutdown at 15:45:46 UTC were verified.
[M3 report §13](MILESTONE_M3_REPORT.md#13-final-local-m3-a-checkpoint--1547-utc)
contains exact current receipts/log hashes and publication identity rules.

This completes the **selected 53-file owner range**, not full-product execution
of all **10,362** manifest nodes. Catalog 2,111 (+4/−0), written manifest and 7+11
browser collection retain their separate inventory level. Earlier failed attempts,
including the diagnosed reused-database run and M2 hosted failures, remain intact.
M3-A is a publishable **PARTIAL** checkpoint. Exact end SHA/tree will be bound via
PR 47's publication receipt, not self-embedded or replaced with the M2 parent.
New-SHA full-product hosted CI and M3 browser/visual results remain pending; actual
user Windows, real inference/quality and full M3 model/API gates remain open.
