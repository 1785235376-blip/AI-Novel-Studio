# Plugin Runtime Foundation — Phase 1

Status: **contracts + pure policy**. This is not a plugin executor.

| Claim | Value |
|---|---|
| Plugin code execution | DISABLED |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| Worker process | NOT IMPLEMENTED in Phase 1. Phase 2A adds a **host-owned test worker only** — see [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md) |
| Worker supervisor | NOT IMPLEMENTED in Phase 1. Phase 2A adds a prototype for the host-owned test worker only |
| IPC | NOT IMPLEMENTED in Phase 1. Phase 2A adds bounded versioned stdio IPC for the test worker only |
| Windows AppContainer / LPAC | Phase 2B ctypes AppContainer **prototype** only; real Windows proof REQUIRED / NOT RUN. LPAC = NOT IMPLEMENTED. `os_sandbox_ready` remains false. See [plugin_runtime_phase2b_windows_sandbox.md](plugin_runtime_phase2b_windows_sandbox.md) |
| OS sandbox ready | `false` / `NOT_CONFIGURED` |
| Capability Broker runtime | NOT IMPLEMENTED |
| Capability policy foundation | IMPLEMENTED (pure, fail-closed) |
| Credential resolution | NOT IMPLEMENTED |
| Signature verification | NOT IMPLEMENTED |
| Marketplace | NOT IMPLEMENTED |
| Provider / Blender / ComfyUI plugins | NOT IMPLEMENTED |
| Database schema / migrations | 0 |
| Frontend production changes | 0 |
| Public execute API | none |
| Release claim | `0.7.0 Beta` (unchanged) |

Phase 1 freezes the Host → Broker → Supervisor → Worker vocabulary so a future isolated worker does not invent a second permission system. Shipping these modules does not enable execution.

Related: [plugin_sdk_v1.md](plugin_sdk_v1.md), [plugin_security_model.md](plugin_security_model.md), [plugin_worker_runtime_design.md](plugin_worker_runtime_design.md), [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md), [plugin_runtime_phase2b_windows_sandbox.md](plugin_runtime_phase2b_windows_sandbox.md), [official_declarative_plugin_packs.md](official_declarative_plugin_packs.md).

## Implemented in Phase 1

| Surface | Module |
|---|---|
| Execution job contract | `PluginExecutionJob` in `app/plugin_runtime_contracts.py` |
| Immutable scope contract | `ImmutableExecutionScope` |
| Capability request / decision | `CapabilityRequest`, `CapabilityDecision` |
| Pure capability policy | `evaluate_capability_request` in `app/plugin_capability_policy.py` |
| Execution gate | `ExecutionGateSnapshot`, `evaluate_execution_gate` |
| Opaque credential handle | `CredentialHandle` |
| Runtime profile | `RuntimeProfile` |
| Resource limit policy | `ResourceLimitPolicy` (`enforcement_implemented=false`) |
| Virtual mount policy | `VirtualMountPolicy` (`host_mount_implemented=false`) |
| Network / subprocess policy | `NetworkPolicy` default DENY, `SubprocessPolicy` default PROHIBITED |
| Lifecycle contract | `ExecutionLifecycleState` + legal transitions |
| Provenance contract | `ExecutionProvenance` |
| Late-result rejection | `ExecutionResultEnvelope` + `evaluate_late_result` |

These types are serializable, `extra=forbid`, and frozen. They reject secret-like fields, host absolute paths, and executable command fields.

## Not implemented

- Third-party plugin Worker, and any plugin Python / JavaScript / native / Shell / PowerShell execution
- AppContainer / LPAC / Job Object enforcement
- Provider plugin, ComfyUI plugin, Blender plugin
- Network broker, project data broker
- Credential Vault resolver
- Signature verifier and publisher trust store
- Marketplace
- Workflow / export execution
- `POST /api/plugins/.../execute` and any Run Plugin UI

Phase 2A added a **host-owned test worker** (fixed argv, not plugin-replaceable) plus a supervisor prototype and bounded IPC. That worker is not a plugin runtime. `execution_supported` remains `false`. See [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md).

`GET /api/plugins/runtime-status` is unchanged: `execution_supported=false`, `sandbox=NOT_CONFIGURED`, `isolation=DENY_ALL`.

## Execution attempt identity

Every attempt has a unique `execution_attempt_id`. Retry creates a **new** attempt for the same `job_id`. An old attempt cannot be resurrected (`SUCCEEDED`/`FAILED`/`CANCELLED`/`TIMED_OUT`/`REJECTED` → `RUNNING` is illegal).

This is how late IPC, killed-worker stdout, and retry races are rejected: the host compares the result envelope's attempt id to the current attempt. Mismatch ⇒ `STALE_EXECUTION_ATTEMPT`.

## Immutable scope

```
ImmutableExecutionScope = {
  workspace_id, project_id, storyline_id, modality, resource_id
}
```

Authorization is exact equality. String prefix matching, path-prefix impersonation, and wildcard ids (`project-*`, `workspace/*`, `*`) are forbidden. Parent/child relations must be proven later by the Host from its own database, never by a plugin-encoded string.

## Capability vocabulary

Broker capability ids reuse Plugin Contract v1 permissions:

`project.read`, `project.write`, `model.text`, `model.image`, `model.audio`, `model.video`, `filesystem.read`, `filesystem.write`, `network`, `process`

The enum existing **is not** an implementation. All real capabilities remain unavailable to plugin code because plugin code still cannot run.

Request ≠ authorization:

```
CapabilityRequest → pure policy → CapabilityDecision (ALLOW | DENY)
```

Default is DENY. Unknown capability, missing approval, capability outside the host-approved set, invalid/wildcard/prefix scope, missing context, any unready gate, and any ambiguity fail closed.

## Execution gate

Future worker start requires every required gate to be ready at once:

| Gate | Phase 1 production |
|---|---|
| `plugin_contract_valid` | may be true for a reviewed pack |
| `manifest_reviewed` | may be true |
| `plugin_enabled` | may be true |
| `package_identity_verified` | may be true |
| `package_trust` | `UNVERIFIED` (no signature verifier) |
| `capability_broker_ready` | `false` |
| `worker_runtime_ready` | `false` |
| `os_sandbox_ready` | `false` |
| `os_sandbox_kind` | `NOT_CONFIGURED` |
| `runtime_profile_supported` | may be true as a semantic profile |
| `execution_supported` | **`false`** |

Windows Job Object is **not** a security sandbox. `os_sandbox_kind=JOB_OBJECT_NOT_A_SANDBOX` is always denied. Executable plugins on Windows will require AppContainer, LPAC, or an independently reviewed equivalent **before** `execution_supported` can become true.

Official / `publisher="Official"` remains unverified metadata. Production trust stays `UNVERIFIED`.

## Opaque credential handle

```
CredentialHandle { handle_id, provider_id, scope, kind, expires_at }
```

No `secret`, API key, token value, password, or DSN. Future path: worker asks the broker with `handle_id` only; the host resolves inside the vault and performs the Provider call. Phase 1 does **not** access the vault.

## Runtime profile

`RuntimeProfile` is a portable semantic description (`runtime_kind`, `platform`, `architecture`, `isolation_requirement`, `resource_class`, `capability_class`). It is not `python.exe = C:\...` and not a specific machine.

Shared vocabulary with future Node Workflow, Provider Runtime 2.0, Compute Fabric, ExecutionNode, and Job Runtime: `NodeType` (job `operation`), `Capability`, `RuntimeProfile`, `Permission Scope`, `ExecutionAttempt`, `ArtifactReference`.

## Resource limits (policy declared, not OS-enforced)

Suggested defaults from the worker design, still **not enforced by the OS**:

| Limit | Default | Enforcement |
|---|---|---|
| wall time | 15 s | `enforcement_implemented=false` |
| CPU time | 5 s | false |
| memory | 256 MiB | false |
| output bytes | 1 MiB | false (OS). Phase 2A host IPC quota is a separate, implemented supervisor limit — see [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md) |
| temp bytes | 64 MiB | false |
| process count | 1 | false (subprocess still PROHIBITED by policy) |
| file count | 32 | false |

## Virtual mounts (policy only — not mounted)

| Mount | Mode |
|---|---|
| `/plugin` | read-only |
| `/job/in` | read-only |
| `/job/out` | quota-limited write |
| `/tmp` | ephemeral |

Path matching is **component-aware**: `/plugin` and `/plugin/foo` are in the virtual namespace; `/plugin-evil` is not. The same rule applies to `/job/in`, `/job/out`, and `/tmp`. `.` / `..` / empty segments are rejected. Forbidden targets: repository source, `.env`, credential vault, database data directory, other plugin packages, user home, host drive. Phase 1 does not create mounts and does not fake them. Phase 2A hardens the validator only; it still does not mount anything.

## Network and subprocess

- Network default: **DENY**. Domain allowlist is reserved and must stay empty while `implementation_status=NONE`. Manifest `network=true` is not a grant; only a future broker may grant.
- Subprocess default: **PROHIBITED**. A future Blender adapter must be a host-owned capability, not `subprocess.Popen("blender.exe")`. A future ComfyUI adapter must be a host-owned capability, not arbitrary localhost HTTP.

## Lifecycle

Legal path:

`CREATED` → `AUTHORIZATION_PENDING` → `AUTHORIZED` → `READY` → `STARTING` → `RUNNING` → `{SUCCEEDED, FAILED, TIMED_OUT}`

Cancel: `READY`/`STARTING`/`RUNNING` → `CANCEL_REQUESTED` → `CANCELLED` (or `FAILED`/`TIMED_OUT`).

`REJECTED` is reachable from pre-running states when policy or gates fail.

Illegal: any terminal → `RUNNING`/`CREATED`, `SUCCEEDED` → `RUNNING`, `FAILED` → `RUNNING`, skipping authorization. Retry = new `execution_attempt_id` in `CREATED`.

Entering `READY`/`STARTING`/`RUNNING` additionally requires a fully ready gate. Production Phase 1 gates never allow that.

## Late result rejection

A result envelope must include `job_id` and `execution_attempt_id`. The host accepts it only when both match the **current** attempt and the lifecycle is `RUNNING`. Otherwise:

- attempt mismatch → `STALE_EXECUTION_ATTEMPT`
- job mismatch → `JOB_ID_MISMATCH`
- not running → `ATTEMPT_NOT_RUNNING`

Covered without a worker: Attempt 1 times out, Attempt 2 starts, Attempt 1 late result is rejected, Attempt 2 result is accepted.

## Provenance

Host-written audit record: plugin id/version, package/manifest fingerprints, job/attempt ids, scope, runtime profile, capability decision **references** (ids, not payloads), timestamps, `publisher_trust=UNVERIFIED`.

It must not record secrets, raw credentials, or arbitrary host filesystem paths.

## Existing declarative packs

The eight official declarative packs from PR #21 remain data-only. Discovery, registration, review, activation, catalog, live SHA, budgets, and read-only behavior are unchanged. `execution_mode=declarative` does **not** translate into an executable job. `PluginExecutionJob` is a future host contract; it is not a public execution API.

## Blender / ComfyUI design constraint

Phase 1 does not ship those plugins. The contracts exist so they can be added later **without** granting `process` or `network` to plugin code:

- Blender: host-owned adapter capability; the host launches a reviewed runtime, never an arbitrary plugin `Popen`.
- ComfyUI: host-owned adapter capability; the host speaks a bounded protocol, never arbitrary localhost HTTP from the plugin.

## Persistence and UI

No execution tables, no migrations, no Run Plugin button, no Worker monitor. Jobs are in-memory typed objects for tests and future supervisors.

## Verification

Targeted tests in `tests/test_plugin_runtime_foundation_phase1.py` plus existing plugin contract / discovery / catalog / official pack tests. Policy evaluation is monkeypatched to fail on `subprocess`, `socket`, `httpx`, and vault resolve. Phase 2A process-lifecycle coverage lives in `tests/test_plugin_runtime_phase2a_test_worker.py`.
