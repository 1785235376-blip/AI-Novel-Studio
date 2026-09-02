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
| `gpu_vendor_id` | Vendor of one unambiguous physical display adapter | Windows display-device PCI vendor fact, mapped into the existing GPU vendor taxonomy |
| `vram_mib` | Conservative floor of positively reported dedicated video-memory capacity | Windows DXGI dedicated-video-memory fact |
| `ram_mib` | Installed physical Host RAM capacity, not free/available/process memory | Windows `GlobalMemoryStatusEx.ullTotalPhys` |
| `runtime_family_ids` | Runtime families positively available on this node | Existing Model Center runtime definition and resident lifecycle facts |

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
runtime requirement, executable name, WMI query, `nvidia-smi`, or new package is
used. The Windows probe enumerates physical PCI display adapters with
`EnumDisplayDevicesW`, excludes non-PCI virtual display devices, and obtains
dedicated memory through DXGI. Adapter identifiers used to distinguish display
heads remain inside the probe and are never returned or serialized.

## Runtime-family authority

A default `RuntimeDefinition` does not establish capability. A family is present
only when one of these existing positive facts holds:

- a managed runtime has an absolute configured executable that currently exists;
- an already-resident lifecycle instance is running/process-alive or has a
  positive local reachability fact.

An external URL merely being configured is insufficient. Inventory collection
does not call Model Center health, validation, discovery, start, stop, or network
probe methods. Duplicate runtime definitions collapse into the existing
taxonomy set, and unknown runtime types produce no family.

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
