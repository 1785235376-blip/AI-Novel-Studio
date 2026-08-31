# Provider Runtime 2.1A: Model Center snapshot bridge

This phase is a **read-only** adapter. It copies already-resident Model Center
registry and instance facts into Provider Runtime 2.0 snapshot types. It does
not execute `ProviderRoutingDecision`, start or stop runtimes, download models,
resolve credentials, read Vault, perform provider HTTP, spawn subprocesses,
change database schema, or touch the frontend.

Existing Provider Runtime 2.0 modules remain frozen:

- `app/provider_runtime_v2_contracts.py`
- `app/provider_routing_policy_v2.py`

Existing Model Center Phase 2A behavior is not changed.

## Architecture

```text
Model Center authoritative in-memory state
        |
        v
capture_model_center_facts()     # no probe, start, stop, or I/O
        |
        v
ModelCenterFactSource            # sanitized, frozen, no paths/env/secrets
        |
        v
build_provider_runtime_snapshots()
        |
        v
ProviderRuntimeSnapshotBundle
    candidates:  always empty in 2.1A
    hardware:    always empty in 2.1A
    credentials: always empty in 2.1A
    rejections:  normalized fail-closed reasons + availability projections
        |
        v
existing pure evaluate_routing()   # never ALLOW on 2.1A output
```

The bridge owns normalization. Caller-supplied `trusted=true`,
`authorized=true`, `healthy=true`, `compatible=true`, credential values,
Plugin Trust VERIFIED, Team Compute locations, and execution-node overrides
are rejected as untrusted.

## Identity foundation (blocked, not invented)

Provider Runtime 2.0 `RouteIdentity` requires four registry UUIDs:

| Contract | Current Model Center representation | Sufficient for RouteIdentity? |
| --- | --- | --- |
| ProviderIdentity | `RuntimeDefinition.provider_adapter` string (`OPENAI_COMPATIBLE_TEXT`, `COMFYUI_ASSET`) | No |
| ModelIdentity | `ModelDefinition.id` slug (`qwen36-27b-q4km`) | No |
| RuntimeIdentity | `RuntimeDefinition.id` slug (`llama-cpp-local`) | No |
| ExecutionNodeIdentity | **no field** | No |

Hardware/capability UUID facts are also absent:

| Provider Runtime fact | Current Model Center representation |
| --- | --- |
| `runtime_family_id` | `RuntimeType` enum string (`LLAMA_CPP`, `COMFYUI`) |
| `architecture_id` | component architecture strings (`QWEN3`, `RIFE49`), not host ISA |
| `gpu_vendor_id` | marketing GPU name (`RTX 5080`), often with **no VRAM/RAM numbers** |
| `quantization_id` | string (`Q4_K_M`) |

This phase **does not**:

- generate random UUIDs
- UUID5/hash slugs, display names, paths, or URLs
- invent an execution-node identity for the local device
- treat adapter names as provider registry IDs

If a future Model Center record already stores a canonical UUID in
`registry_id` / `provider_adapter`, the bridge will recognize it as a UUID
and omit the corresponding `MISSING_*_IDENTITY` reason. Execution-node and
hardware UUID facts still do not exist on current Model Center types, so
**2.1A never emits `CandidateDescriptor` or `HardwareSnapshot`**.

## Location, capability, availability

- Location is `DEVICE` only for loopback IP literals (`127.0.0.1`, `::1`).
  `localhost` (needs DNS), wildcard, LAN, and public binds fail closed.
  SAME_USER_NODE, WORKSPACE_NODE, and CLOUD are not mapped.
- Modalities map only when Model Center declares an overlapping value:
  TEXT, IMAGE, VIDEO, TTS, AUDIO, EMBEDDING. VISION, RERANK, RESTORATION,
  and INTERPOLATION remain unknown. Names such as `qwen` / `comfyui` are
  not capabilities. EMBEDDING does not guess `VECTOR` assets.
- Availability dimensions stay distinct. `authorized` is always false
  (this phase does not invent Provider authorization). `compatible` is
  always false (no UUID architecture/vendor/VRAM/RAM host snapshot).
  Installed requires already-resident instance liveness/reachability;
  the bridge does not probe files or HTTP.

## Security boundary

| Action | Count |
| --- | --- |
| Real model calls | 0 |
| Provider network requests | 0 |
| Credential / Vault access | 0 |
| Subprocess created by the bridge | 0 |
| Runtime start / stop | 0 |
| Model download / install | 0 |
| Plugin / Team Compute execution | 0 |
| Database schema / migrations | 0 |
| Frontend changes | 0 |

`evaluate_routing()` over a 2.1A bundle cannot return `ALLOW`.

## Predecessor task

Minimal identity foundation required before a later phase may emit
ALLOW-capable routes:

1. Stable registry UUIDs on Model Center for provider, model, runtime, and
   the local execution node (not derived from slugs, paths, or URLs).
2. Registry UUIDs for runtime family, host architecture, GPU vendor, and
   quantization, plus host VRAM/RAM in MiB.
3. A Provider authorization fact distinct from runtime presence, health,
   Plugin VERIFIED, and `candidate.trusted`.
4. Authoritative local cost/latency policy if those estimates are required
   for routing (unknown cost is excluded by 2.0, not assumed free).

Do not hash current slugs as a workaround.

## Verification

Run `tests/test_provider_runtime_v2_model_center_bridge.py` with pytest.
The local autouse fixture shadows the root fixture so Vault/runtime are
not initialized. Tests cover missing identities, unknown capabilities,
each availability dimension, location fail-closed, untrusted overrides,
no credential/Plugin Trust/Team Compute substitution, capture sanitization,
determinism, and a dynamic I/O + UUID-minting trap.
