# R2 Local AI Discovery implementation receipt

Source: user-authorized 28-section R2 Local AI Discovery / Model Center supplement. Same repository/work branch as R2; no separate project. Publication and final commit/CI identity are owned by the release lead.

## Delivered implementation

- `app/model_center/discovery_types.py`: strict host-local runtime/settings/explicit-enable schemas; loopback canonicalization; filesystem scope/link/network restrictions
- `discovery_probes.py`: bounded HTTP, GGUF metadata, passive executable version/CUDA component metadata and reused hardware inventory
- `discovery.py`: background scan/cancel/partial results, capability evidence, conservative license review, atomic persisted registration, revalidation/disable/restart invalidation, Model Center/stable identity reuse
- `discovery_api.py`: trusted-session authorization on every new read/write route, both supported API prefixes via host mounting
- `discovery_bridge.py`: existing text/model/image registries; adapter live enable checks; local-only inference transports; explicit task-only llama.cpp launch/release
- `domain.py`, `service.py`: runtime/status additions and MiniMax identity split. Old audio identity stays disabled for history compatibility; independent VIDEO identity added
- `frontend/src/localAiDiscoveryApi.ts` and `ui/LocalAiDiscovery.tsx`/CSS: functional settings/model-center surface, scan/rescan/cancel, hardware/runtime/model evidence, categories, settings, Validate/Register/explicit Enable/Disable/Configure/Remove-only
- `ModelCenter.tsx`: minimal embedding, existing shared shell preserved
- `tests/test_local_ai_discovery.py`, frontend unit/API tests, `frontend/tests/visual/local-ai-discovery.spec.ts`
- Root `LOCAL_AI_DISCOVERY.md`, `LOCAL_AI_WINDOWS_ACCEPTANCE.md`

## Behavior and supported depth

Ollama tags + explicit completion metadata; flexible Qwen families; configured GGUF/llama; ComfyUI stats+node/model enumeration; A1111 checkpoint enumeration; custom local runtime editor. Runtime/model/workflow evidence is separate. SeedVR2 and RIFE retain independent utility modalities. Missing services yield partial results. No detect/validate/register/enable path starts a process or performs inference.

Explicitly enabled Ollama, known-architecture managed/external llama and A1111/standard SD Comfy registrations bridge into existing creative-task registries. No new cloud provider or parallel job/history system is introduced. Model outputs continue through existing task/Draft/review contracts.

## PARTIAL

- Qwen-Image/FLUX/Z-Image/H3/Wan/LTX/SeedVR2/RIFE discovery and registration exist; non-standard workflow execution remains blocked until reviewed family/operation adapters are available. Node presence alone is not runnable-workflow proof.
- Generic OpenAI-compatible `/models` lists and Custom HTTP health checks do not prove capabilities; unknown adapters and credential-required custom runtimes remain disabled.
- Actual inference/hardware compatibility is never inferred from names or metadata. Unknown license requires user acknowledgment of their review; no commercial-use claim.
- Registrations require revalidation and explicit re-enable after backend restart. On-demand managed llama support uses conservative one-managed-runtime-at-a-time release-after-task behavior; external runtimes are not terminated.

## Verification

- Dedicated synthetic Local AI suite: 64 passed; combined with 140 existing regressions, 204 passed. Evidence: `evidence/local-ai-backend.txt` and `.xml`. These include mounted standalone routers for both prefixes, not yet the application integration mount.
- Existing Model Center phase1/phase2 + provider-runtime snapshot bridge: 140 passed after catalog/type integration.
- Frontend Local AI/API/existing ModelCenter targeted tests: 36 passed after stale-state recovery/license-flow hardening; evidence `evidence/local-ai-frontend.txt`. TypeScript and token guard passed after final UI changes; production build passed at the initial UI checkpoint.
- Four browser cases added (explicit lifecycle plus 1366×768/1440×900/1920×1080 shell/model geometry). Test collection verified. Execution locally **NOT_RUN** because Chromium exits before test startup with sandbox socket `EPERM`; bundled browser also absent. Hosted CI must run the new spec; visual config needs the corresponding testMatch.
- Actual Windows, actual GGUF/model generation, actual CUDA/GPU, real Comfy custom nodes/workflows and user's licenses: **NOT_RUN**. Dedicated acceptance guide supplied.

No actual model binary is executed by tests. Network transport coverage uses only a synthetic loopback HTTP server or injected fixture adapters. No real prompt, model file, key, private path or GPU inventory is published.

## Opus handoff addition

Model Center consumes the new `LocalAiDiscovery` panel. It uses existing Panel/Button/Badge/StatusMessage/EmptyState and token-only CSS; no AppShell/global-header/module-switcher/inspector geometry changes. Opus can improve visual hierarchy, spacing within tokens, labels and responsive controls. Preserve all separate Detect/Validate/Register/explicit Enable gates, unknown/partial errors, local path privacy, authorization failure lockout, cancellation/late-response handling, disabled/restart semantics, license acknowledgment and registration-only deletion. Preserve the explicit distinction between declared capability, metadata-verified capability, workflow structure and actual inference verification.

## Pending release-lead integration at worker handoff

Owned component/service files are ready. Shared files were intentionally not edited without coordination. Before publishing this supplement, the lead must:

1. Construct `LocalDiscoveryService(model_center_service, settings.data_path()/"model-center"/"local-discovery.json")` after the existing asset registry is initialized and assign `LocalDiscoveryBridge(service, runtime, asset_provider_registry)` to `service.route_bridge`.
2. Mount `create_local_discovery_router` for both `/api/model-center/local-ai` and `/api/v1/model-center/local-ai` with the existing `_model_center_mutation_authorization` callback.
3. Append `service.media_routes()` to the existing asset-provider selection response; it probes local health read-only and deduplicates endpoints.
4. Make packaged local-text readiness accept the existing provider registry's enabled local descriptors/adapter health check, without introducing a cloud fallback.
5. Include `local-ai-discovery.spec.ts` in hosted visual test selection.
6. Completed after explicit ownership coordination: discovery now calls existing `OllamaProvider.list_models` with an injected bounded local reader, metadata details and strict probe errors; the no-argument legacy response remains unchanged. `HostGpuFact.name` preserves DXGI description for display only. Vendor/VRAM normalization still uses numeric facts, never names. Final application integration verification remains the lead's step.
7. Add the Opus handoff paragraph above to the root handoff file, update release matrix/PR and final commit identity.

Until the shared mounts and integrated test are complete, application end-to-end availability remains **PENDING INTEGRATION**, not completed. The callback/service standalone state machine and registry bridges are verified with synthetic adapters.

## Coordinated provider/hardware completion

Files: `app/providers.py`, `app/provider_runtime_v2_host_hardware_inventory.py`, discovery integration and three additional tests. Final related combined run: **263 passed, 1 skipped**. The single skip is the existing real-Windows native acceptance test (`tests/test_provider_runtime_v2_host_hardware_inventory.py:407`), not a passing native test. Evidence: `evidence/local-ai-provider-hardware.txt` and `.xml`. No executable or real model was launched. `git diff --check` passed.
