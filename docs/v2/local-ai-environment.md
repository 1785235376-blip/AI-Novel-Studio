# V2 local AI environment report

## Scope and safety

`narrative_production_v2` is opt-in and remains disabled by default. `V1_ACCEPTANCE_MODE` overrides the opt-in. With the flag off, the existing V1/R2 discovery surface remains available with its established known services and configured GGUF roots. The new environment endpoint is unavailable and automatic V2 service/common-directory probes are not added.

The environment report describes **the host running the backend**. A cloud or Linux report does not describe the user's Windows PC. Windows native discovery, device usability, driver compatibility, inference speed/quality, and actual model generation remain **NOT_RUN** until independently tested on that host. Component presence, a valid model header, an advertised model, and successful inference are distinct facts.

The implementation reuses LocalDiscovery, Model Center, HardwareInventory, existing runtime configurations, and the existing registration/routing bridge. It does not add a second runtime registry. Detect → Validate → Register → explicit Enable → authorized task Launch remains unchanged. Detection never enables a route, starts a runtime, runs `--version`, imports model code, loads tensor weights, invokes a paid API, reads credentials, installs software, or scans whole drives.

## API and UI

Both existing local-AI router prefixes expose a host-session-protected, flag-gated:

- `GET /api/model-center/local-ai/environment`
- `GET /api/v1/model-center/local-ai/environment`

The response is the Pydantic `AIEnvironmentReport` contract, with matching TypeScript type in `frontend/src/localAiDiscoveryApi.ts`:

- `schema_version: 2`
- `execution_scope: BACKEND_HOST`
- `inference_status: NOT_RUN` and `windows_acceptance: NOT_RUN`
- Scan ID, timestamps, and `NOT_SCANNED/RUNNING/COMPLETED/PARTIAL/CANCELLED` status
- CPU, logical CPU count, RAM, enumerated GPU vendor/name/dedicated VRAM
- CUDA and DirectML passive system-component evidence
- Service health, advertised model names, and existing candidate IDs
- GGUF, Safetensors, and Diffusers model-index file observations
- Configured/common roots with individual status, bounded failures, and published limits

GET only reads the latest explicit scan. It performs no discovery or network requests. The existing Scan, scan-status, and Cancel APIs retain control. The creative inspector's `AIEnvironmentSummary` is read-only and links to the existing Model Center. It polls only a scan already reported as running, aborts on unmount, rejects stale responses, and clears old private observations on authorization errors.

`PUT /settings` additionally accepts optional `include_common_model_dirs`. An explicit `false` persists across restart and is preserved when older clients omit this field. The default is true **only when the V2 scan feature is enabled**.

## Bounded observations

- Known service defaults retain Ollama (`11434`), ComfyUI (`8188`), and Automatic1111 (`7860`), and add LM Studio (`1234`, OpenAI-compatible `/v1/models`) and llama.cpp (`8080`). Numeric loopback validation, no proxy, no redirects, timeouts, and existing response limits are reused.
- LM Studio models-list evidence permits discovery/disabled registration. It does not independently authorize generation, prove weight locality, or enable the existing local-only route.
- Windows common roots are a fixed list of model-specific LM Studio, Hugging Face, Ollama, ComfyUI, and SD WebUI locations under the home directory, plus explicit standard model-cache environment settings. No home-directory recursion, PATH search, drive search, downloads, registry execution, or model-code imports occur.
- Configured roots are checked first; duplicate/nested file observations are deduplicated. Existing configured GGUF candidate identity is reused instead of creating a new default-runtime binding for the same file.
- Safetensors reads only its 8-byte length prefix and bounded JSON header. Tensor data is not read or deserialized. Header shape/dtype/offset consistency and file bounds are checked. Unknown/malformed headers remain unverified.
- Diffusers reads only bounded `model_index.json` metadata and never imports its `_class_name`. Arbitrary `.py`, pickle/checkpoint executables, prompts, novels, and unrelated documents are not opened.
- CUDA/DirectML checks use trusted Windows system-directory DLL presence without loading those DLLs. `COMPONENT_FOUND_NOT_VERIFIED` is a component hint; missing system DLLs do not prove that an application-local runtime lacks acceleration.
- Hardware failures, malformed/unavailable services, unreadable roots, cancellation, and file-budget exhaustion retain valid partial observations. Errors expose bounded reason codes rather than arbitrary exception contents.

Bounds: 45-second scan budget checked between bounded operations, 2-second network I/O timeout, 20 runtime observations, 512 models per service, 4 MiB response limit, 32 roots, 5,000 total directory entries, 2,000 model files, three subdirectory levels, and 256 KiB metadata. Existing filesystem and request calls may complete before cancellation or the deadline becomes terminal. Symlinks, junctions, network roots, and linked ancestors are rejected or skipped. A depth/entry/file budget hit is explicitly reported as partial.

## External llama.cpp locality evidence

The original Model Center validator marks an external `LLAMA_CPP` candidate
`source_locality: LOCAL_VERIFIED` only when bounded metadata identifies a valid
TEXT-capable GGUF at the exact configured safe absolute local path, and the
configured numeric-loopback runtime is running and advertises the configured
model alias (or the configured filename when no alias is set). A loopback URL,
model listing, or model name alone does not qualify. Managed runtimes retain
their separate lifecycle contract and gain no external-locality marker.

This classification is configured local-file metadata plus external runtime
metadata/alias agreement. It is not executable/process attestation, proof that
the server loaded those complete weights, or an inference/quality certificate.
Validation preserves `verified: false` and `INFERENCE_NOT_RUN`; executable
version and GPU usability remain unverified. The separate real CPU acceptance
owns its official-server provenance, PID/argv, full GGUF hash, and actual
generation receipts rather than inferring those facts from discovery.

Failed revalidation clears earlier positive locality. Existing dispatch-time
file/metadata/alias checks, license review after model-evidence changes, explicit
Enable, revoke/configuration fencing, and restart revalidation remain mandatory.
No new registry, scan path, process launch, or inference transport is introduced.
`tests/test_v2_llama_locality_validation.py` covers the original invocation gate
and these fail-closed cases using synthetic metadata only.

## Verification

`tests/test_local_ai_environment_v2.py` uses cloud fixtures and synthetic protocol/file/Windows-component doubles. Coverage includes default-off/V1 isolation, API authorization, no GET-triggered scan, service enumeration, disabled LM Studio registration, common-root opt-out persistence, metadata-only inspection, malformed/oversized inputs, private-file exclusion, symlink/duplicate protection, cancellation, bounds, permission errors, hardware partial failures, and no implicit process launch.

The existing local-AI discovery, adversarial, egress, remaining-controls, and HardwareInventory suites continue to protect the established state chain and routing/privacy boundaries. `AIEnvironmentSummary.test.tsx` covers disabled/loading/empty/partial/cancelled/auth/retry/stale-response/unmount states. `localAiDiscoveryApi.test.ts` verifies the authenticated report API and settings semantics.

These tests are **contract verification**, not Windows or real-model acceptance. See `LOCAL_AI_WINDOWS_ACCEPTANCE.md` for the independent native acceptance matrix.
