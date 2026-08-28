# Plugin SDK v1 — Declarative Contract

Status: **contract and validator only**. This is not a plugin executor, marketplace, installer, or V1.0 claim.

| Field | Value |
|---|---|
| Manifest version | `1.0` |
| Host API version | `1` |
| Execution mode | `declarative` only |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| Runtime | `DEFERRED` |
| Release claim | `0.7.0 Beta` |

The runtime Pydantic model in `app/plugin_contracts.py` is the single source of truth. `schemas/plugin-manifest-v1.schema.json` is generated from that model and kept in lockstep by tests.

## What v1 can do

- Discover local plugin directories under the host-controlled plugins root
- Validate a versioned manifest
- Verify declarative JSON resources (path, type, size, SHA-256)
- Register a manifest, review requested permissions, and activate the **manifest**
- List verified resource metadata later via the declarative catalog

## What v1 cannot do

- Run Python, JavaScript, Shell, PowerShell, or native binaries
- Load plugins with `importlib`, `exec`, `eval`, or `subprocess`
- Install, update, or uninstall packages
- Register Providers or execute workflow nodes
- Read Credential Vault secrets or novel body text
- Fetch plugin URLs or inject UI into the WebView

`MANIFEST_ACTIVE` means the manifest is enabled. It does not mean plugin code can run.

## Manifest fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `manifest_version` | no | `"1.0"` | Other values are rejected |
| `host_api_version` | no | `"1"` | Other values are rejected |
| `id` | yes | — | `[A-Za-z0-9][A-Za-z0-9._-]{1,79}` |
| `name` | yes | — | Display name, rendered as plain text |
| `version` | yes | — | SemVer `MAJOR.MINOR.PATCH` with optional pre-release |
| `description` | no | `""` | Plain text |
| `capabilities` | no | `[]` | Existing allowlist only |
| `requested_permissions` | no | `[]` | Existing allowlist only; grant is a separate review |
| `execution_mode` | no | `"declarative"` | The only legal value |
| `publisher` | no | `""` | Unverified metadata, never a signature |
| `resources` | no | `[]` | Declarative JSON resource list |

Unknown fields are rejected. The following execution fields are always rejected:

`entrypoint`, `script`, `command`, `executable`, `module`, `url-based-code`, `install_hook`, `postinstall`

Legacy minimal manifests remain valid: missing v1 fields receive the safe defaults above and do **not** receive extra permissions.

## Capability and permission allowlists

Capabilities: `provider`, `writing_tool`, `multimodal_tool`, `exporter`, `workflow`

Permissions: `network`, `filesystem.read`, `filesystem.write`, `process`, `model.text`, `model.image`, `model.audio`, `model.video`, `project.read`, `project.write`

The allowlists are not expanded in this phase. An example pack that only ships JSON should request no permissions.

## Declarative resources

Allowed kinds: `writing_presets`, `workflow_templates`, `export_profiles`

Each resource must declare `kind`, `relative_path`, `sha256`, and either `media_type` or `schema_version`. Only JSON files are accepted.

Limits:

- 1 MiB per resource
- 100 resources per plugin
- 10 MiB total declarative payload

See [plugin_security_model.md](plugin_security_model.md) for path, symlink, and disclosure rules.

## Example

`examples/plugins/story-workflow-pack/` is a Contract/Validator sample. It does not execute workflows.
