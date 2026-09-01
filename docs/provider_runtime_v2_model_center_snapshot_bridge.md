# Provider Runtime 2.1A Model Center Snapshot Bridge

`app.provider_runtime_v2_model_center_snapshot_bridge` is a read-only adapter
between Host-owned Model Center facts and the Provider Runtime metadata
contracts. `app.dependencies.create_provider_runtime_snapshot()` is the
production entrypoint; it obtains the Provider Registry, Model Registry, Model
Center and Host execution-node identity internally. Request payloads cannot
replace those authorities.

The bridge preserves Provider, provider-scoped Model, Runtime and local
ExecutionNode UUIDs. Each identity is cross-checked against the same
Host-owned StableIdentityStore; a syntactically valid but different UUID is a
rejection. It never calls identity-store creation, migration, repair, rename
or rekey operations. Each source item is exactly one accepted candidate or one
rejection, and both collections are deterministically ordered by canonical
source key.

Provider association comes from the matched Model Registry descriptor, and
Model-to-Runtime association comes only from Model Center's explicit routing
policy. Runtime type and capability are used only for compatibility checks.
There is no runtime-type-to-provider mapping and no compatible-runtime
pairing. Locality is read from Model Center's existing `is_local` security
rule; it does not imply authorization, trust, self-hosting, or workspace
membership. The current Model Center does not expose an authoritative runtime
architecture requirement, so production entries without one are rejected as
`MISSING_REQUIRED_HARDWARE_FACT`. Host Hardware / Runtime Requirement
Authority is deferred to a separate foundation.

Capability mapping is explicit:

- `TEXT` -> text input/text output
- `IMAGE` -> text input/image output
- `VIDEO` -> text input/video output
- `TTS` -> text input/audio output
- `AUDIO` -> audio input/audio output
- `EMBEDDING` -> text input/vector output

Other Model Center capabilities are rejected as unsupported; no input/output
shape inference is performed. Installed, configured, running, reachable and
healthy facts remain separate. Streaming comes only from the matched Model
Registry descriptor. Authorization, trust and self-hosting default to false
because no such authority belongs to this bridge. The bridge does not evaluate
routing policy, access credentials or Vault, perform HTTP or hardware probing,
start or stop runtimes, execute models/providers/plugins, or invoke Team
Compute.

For the current Model Center status model, `READY`, `DEGRADED`, `DISABLED` and
`INCOMPATIBLE` mean that an installed model definition exists. The remaining
statuses (`NOT_INSTALLED`, `DISCOVERED`, `VALIDATING`, `MISSING_COMPONENT`,
`LICENSE_REQUIRED`, `RUNTIME_REQUIRED` and `UNKNOWN`) do not establish
installation. This mapping is only the Model Center installation fact; it does
not imply runtime health or authorization.
