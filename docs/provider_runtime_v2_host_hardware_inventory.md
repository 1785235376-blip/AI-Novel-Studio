# Provider Runtime 2.1C Host Hardware Inventory

This foundation produces the existing Provider Runtime `HardwareSnapshot` for
the current Host-owned `ExecutionNodeIdentity`. It reports positively known
node capability facts. It does not report runtime requirements, preferences,
routing choices, authorization, trust, compatibility, or cloud capability.

## Fact meanings and owners

| Field | Meaning | Authority |
| --- | --- | --- |
| `node.execution_node_id` | Existing opaque identity of this Host execution node | Read-only `StableIdentityStore` entry `execution_node/local` |
| `architecture_id` | CPU architecture actually reported by the Host | Strict alias normalization of the native architecture fact into the existing Stable Identity architecture taxonomy |
| `gpu_vendor_id` | Vendor of one unambiguous physical GPU adapter | Windows DXGI adapter vendor fact, mapped into the existing GPU vendor taxonomy |
| `vram_mib` | Conservative floor of positively reported dedicated video-memory capacity | Dedicated-memory fact from the same Windows DXGI adapter description as the vendor |
| `ram_mib` | Installed physical Host RAM capacity, not free/available/process memory | Windows `GlobalMemoryStatusEx.ullTotalPhys` |
| `runtime_family_ids` | Runtime families positively available on this node | Known local managed runtime definition plus its exact Host-owned live lifecycle process |

`ram_mib` and known `vram_mib` use `bytes // (1024 * 1024)` and never round
up. Runtime requirements remain owned by PR #34. A runtime's configured
`architecture_id` is never an input to Host architecture detection.

Model Center `HardwareProfile` is not Host inventory. It records model-specific
requirements, tested configurations, validation provenance, and benchmarks.
Those values describe what a model/runtime configuration needs or previously
used; they do not prove what hardware the current execution node has.

## GPU and VRAM fail-closed semantics

The existing `HardwareSnapshot` requires numeric `vram_mib`. In this producer,
zero means **no positively established dedicated-VRAM capability**. It does not
assert that a GPU is physically absent. Consequently every requirement greater
than zero fails the existing numeric capability comparison.

The raw fact seam distinguishes these cases before normalization:

- no physical GPU: empty GPU facts;
- GPU vendor known but dedicated VRAM unavailable: known vendor and unknown
  memory, normalized to that vendor and zero VRAM capability;
- GPU facts unavailable: unknown GPU facts, normalized to no vendor and zero;
- more than one physical GPU: ambiguous node-level execution device, normalized
  to no vendor and zero rather than choosing GPU 0 or the largest device;
- one supported GPU: vendor taxonomy ID and conservative dedicated-memory MiB.

No GPU model-name table, internet lookup, environment variable, runtime family,
runtime requirement, executable name, WMI query, `EnumDisplayDevicesW`,
`nvidia-smi`, or new package is used. One DXGI enumeration obtains vendor and
dedicated memory from the same `DXGI_ADAPTER_DESC1`. Adapters carrying the DXGI
software flag are excluded. Every remaining hardware adapter is counted,
including adapters without a display head; two or more therefore fail closed as
an ambiguous node-level capability.

## Runtime-family authority

A default `RuntimeDefinition`, executable file, instance state, or reachability
boolean does not establish capability. A family is present only for a known,
local, managed runtime whose exact runtime ID is in the production lifecycle's
Host-owned process registry and whose owned process is currently live
(`poll() is None`).

Generic HTTP reachability does not prove external ComfyUI service identity, so
external ComfyUI remains unavailable and fail closed. A future runtime binary or
service identity authority may support validated stopped managed runtimes or a
validated external ComfyUI service; this foundation does not invent that
authority. Inventory collection does not call Model Center health, validation,
discovery, start, stop, binary/subprocess probe, or network methods. It only
checks the liveness of an already Host-owned process. Duplicate runtime
definitions collapse into the existing taxonomy set, and unknown runtime types
produce no family.

## Failure and side-effect boundary

Unknown architecture, unavailable physical RAM, invalid facts, and a missing or
invalid existing node identity fail before a `HardwareSnapshot` is produced.
Unsupported operating systems fail with `UNSUPPORTED_PLATFORM`. GPU observation
failure is representable as the conservative zero capability described above.

Collection is snapshot-scoped and not persisted. It does not mutate Stable
Identity, Model Center configuration, routing policy, Provider/Model registries,
or runtime requirements. It performs no Provider/model call, HTTP request,
credential or Vault access, runtime lifecycle action, plugin execution, model
download, Team Compute discovery, telemetry, or remote reporting. No public API
endpoint is added. `serialize_host_hardware_snapshot()` sorts runtime-family IDs
for deterministic JSON-ready output. Production callers inject the already-owned
execution-node identity and Model Center into `collect_host_hardware_snapshot()`;
the module does not import the application dependency graph or initialize those
owners itself.

This module ends at truthful current-node `HardwareSnapshot` production. The
existing pure `evaluate_routing()` function may consume the snapshot, but no
Routing Service, candidate orchestration, credential resolver, execution path,
or remote-node inventory is part of this foundation.
