# Model Center Phase 1

Model Center Phase 1 adds a local model and runtime foundation without replacing the existing Provider system.

## Architecture

- The Model Registry stores structured model identity, capabilities, format, status, components, hardware profiles, and validation provenance.
- The Component Compatibility Graph matches family, variant, architecture, version, and explicit compatible model IDs. FLUX.2 Dev and Klein encoders are intentionally not interchangeable.
- The Runtime Registry separates durable runtime definitions from in-memory runtime instances.
- Runtime Discovery only inspects explicitly configured locations. Validation may run a bounded `--version` probe and a direct loopback health request. Runtime probes ignore environment proxies and reject every HTTP redirect.
- Runtime Lifecycle manages llama.cpp processes started by this application. It tracks the exact process object, drains bounded stdout/stderr tails, detects crashes, and never kills by name or arbitrary PID.
- ComfyUI is external-only in V1. Model Center checks its configured path and health but does not install, update, start, or stop it.
- Hardware Profiles distinguish smoke, default, and verified maximum profiles.
- Validation Provenance distinguishes file, hash, load, inference, and pipeline validation. Historical inference remains visible, but current verification additionally requires matching model hash, runtime version and fingerprint, and the current hardware profile.
- The Pipeline Registry represents `LOCAL_VIDEO_PIPELINE_V1` as nodes, edges, contracts, capabilities, and hardware requirements.
- The local Routing Foundation resolves capability to model, runtime, and Provider adapter. It does not replace existing Provider routing.

## Persistence And Security

Machine-specific runtime configuration is stored in the ignored `novel_data/model-center/runtime-config.json` sidecar with schema version 1. It is independent of File/PostgreSQL product data, excludes environment variables and secrets, and tolerates missing, corrupt, or unsupported files. Configuration mutations are serialized and use a flushed, fsynced, uniquely named temporary file before atomic replacement; failed persistence does not publish in-memory state. PID, health, logs, and process state remain memory-only.

Managed runtimes accept only resolved loopback bindings and reject wildcard, LAN, public, malformed, userinfo, and lookalike-host addresses. Runtime mutation endpoints require a trusted session in local, packaged, and collaboration modes. Managed children receive a minimal environment allowlist instead of the host environment; secret-like explicit variables are rejected. Bounded raw logs remain internal and are not included in general Model Center API responses. ComfyUI remains externally owned.

## Runtime Control Authorization

Validate, Start, and Stop are trusted desktop control operations. Packaged production uses the existing one-shot `LocalSessionBootstrap` exchange and its opaque session. Collaboration mode uses its existing trusted session. Default local browser mode is intentionally read-only unless a developer explicitly configures `COLLABORATION_DEV_SESSIONS_JSON` and supplies that session through the existing frontend collaboration context. Loopback origin or source IP alone never authorizes runtime mutation, and session tokens are not persisted in Model Center data or sidecars.

## V1 Limitations

- No model download or model store.
- No managed ComfyUI installation or updates.
- No automatic Custom Node installation.
- No automatic benchmark router.
- No Dasheng, MiniMax H3, LTX2.5, or Qwen-Image provider integration.
