# Provider Runtime 2.1A Model Center Snapshot Bridge

`app.provider_runtime_v2_model_center_snapshot_bridge` is a read-only adapter
between Host-owned Model Center facts and the Provider Runtime metadata
contracts. `app.dependencies.create_provider_runtime_snapshot()` is the
production entrypoint; it obtains the Provider Registry, Model Registry, Model
Center and Host execution-node identity internally. Request payloads cannot
replace those authorities.

The bridge preserves Provider, provider-scoped Model, Runtime and local
ExecutionNode UUIDs. It never calls identity-store creation, migration,
repair, rename or rekey operations. Missing or invalid identities become typed
rejections. Each source item is exactly one accepted candidate or one
rejection, and both collections are deterministically ordered by canonical
source key.

Capability mapping is explicit:

- `TEXT` -> text input/text output
- `IMAGE` -> text input/image output
- `VIDEO` -> text input/video output
- `TTS` -> text input/audio output
- `AUDIO` -> audio input/audio output
- `EMBEDDING` -> text input/vector output

Other Model Center capabilities are rejected as unsupported; no input/output
shape inference is performed. Installed, configured, running, reachable and
healthy facts remain separate. Loopback is only a locality fact and does not
grant ownership or trust. The bridge does not evaluate routing policy and does
not access credentials or Vault, perform HTTP or hardware probing, start or
stop runtimes, execute models/providers/plugins, or invoke Team Compute.
