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
