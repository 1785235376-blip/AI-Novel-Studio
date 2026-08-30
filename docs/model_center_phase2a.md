# Model Center Phase 2A

Phase 2A closes the local runtime control plane without connecting runtimes to novel generation.

## Runtime Profiles

Runtime configuration uses typed llama.cpp and ComfyUI profiles. llama.cpp launch arguments are always re-synthesized as an argv list from the typed profile on load and start; raw `launch_arguments` are not accepted, persisted, or treated as authoritative. Optional flags use a narrow allowlist. Model, host, port, and other protected values cannot be overridden by extra arguments. Shell execution is not used. GET `/configuration` returns only the editable DTO; Save submits an explicit allowlisted payload. Managed log responses always include `stdout` and `stderr` arrays, including before the first start.

ComfyUI remains external-only. Model Center may configure its installation path and loopback endpoint, validate health, and inspect `/object_info`; it does not install, update, start, stop, or modify ComfyUI or its Custom Nodes.

Machine paths remain in the ignored runtime sidecar. Candidate profiles are validated and atomically persisted before the in-memory registry is updated.

## Validation And Observability

llama.cpp validation checks the executable, bounded version probe, loopback endpoint, port, model file, GGUF magic, and a detectable CUDA backend when GPU layers are enabled. Managed startup rejects an already occupied port before process creation.

Runtime diagnostics expose structured state, process ownership, HTTP reachability, version, latency, success/failure timestamps, checks, and safe error codes. Capability snapshots distinguish runtime adapters and node classes from available or verified models. A detected ComfyUI node never marks a model or pipeline verified.

Managed stdout and stderr remain memory-only and bounded by line and byte limits. The dedicated log endpoint redacts secret-like assignments, authorization headers, and bearer tokens. General runtime APIs continue to omit logs, executable paths, model paths, working directories, and launch arguments.

## Authorization

Edit, Validate, Start, Stop, configuration detail, advanced diagnostics, and logs require the existing trusted desktop/session authorization. Default local browser mode remains read-only. Packaged mode uses its one-shot bootstrap session, collaboration mode uses its trusted session, and development mode requires an explicitly configured trusted session. Capability snapshots and sanitized runtime metadata remain readable without granting control authority.

Both `/api/model-center` and `/api/v1/model-center` use the same service and authorization contracts.

## Excluded Work

Phase 2A does not execute generation routing, model inference, image or video workflows, model downloads, runtime installation, or Custom Node installation. Qwen text provider integration begins in Phase 2B.
