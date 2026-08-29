# Isolated Plugin Worker Runtime — Design Only

Status: **design document** for the *plugin* worker. Phase 1 **execution contracts and pure policy** are implemented. Phase 2A implemented a **host-owned test worker** plus a supervisor prototype and bounded stdio IPC. A follow-up correction isolated the worker Python startup (`-I -S`, environment allowlist, Host-owned bootstrap) after independent review found inherited `PYTHONPATH` could execute attacker `sitecustomize`. Phase 2B adds a **fail-closed Windows AppContainer prototype** around that Host-owned test worker; real Windows token proof is **REQUIRED / NOT RUN** on Linux. That is not third-party plugin execution and not `os_sandbox_ready=true`.

| Claim | Value |
|---|---|
| Execution contracts + fail-closed policy | IMPLEMENTED (Phase 1) |
| Host-owned Test Worker + supervisor + IPC | IMPLEMENTED (Phase 2A prototype) |
| Third-party plugin Worker | NOT IMPLEMENTED |
| Plugin code execution | DISABLED |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| Sandbox | `NOT_CONFIGURED` |
| AppContainer / LPAC | Phase 2B ctypes AppContainer **prototype** (not production-ready; Windows token proof REQUIRED / NOT RUN). LPAC = NOT IMPLEMENTED. |
| Marketplace | NOT IMPLEMENTED |
| Plugin signatures | NOT IMPLEMENTED |
| Provider plugins | NOT IMPLEMENTED |
| ComfyUI plugins | NOT IMPLEMENTED |
| Blender plugins | NOT IMPLEMENTED |
| Release claim | `0.7.0 Beta` |
| Plugin runtime (release readiness) | `DEFERRED` |

Phase 1 froze the typed contracts in `app/plugin_runtime_contracts.py` and the side-effect-free evaluator in `app/plugin_capability_policy.py`. See [plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md). Phase 2A is documented in [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md). Shipping those modules does not enable execution. Current v1 remains a declarative contract, validator, catalog, and governance UI.

Related implemented surfaces: [plugin_sdk_v1.md](plugin_sdk_v1.md), [plugin_security_model.md](plugin_security_model.md).

## 1. Why a worker exists

The host process (API, DesktopHost, WebView) must never `exec`, `eval`, `compile`, `importlib`-load, or `subprocess` a plugin. A future runtime may run **reviewed, signed, capability-brokered** plugin jobs in a child process that:

- cannot see Credential Vault secrets
- cannot write the novel database unless a scoped handle is granted
- cannot open the network unless an allowlist is granted
- cannot outlive its job or publish a result after cancellation
- cannot inject HTML/JS/CSS into the author WebView

Until that worker exists, `execution_supported` stays `false` and isolation stays `DENY_ALL`.

## 2. Process model

### 2.1 Independent worker process

Each plugin job runs in a **dedicated OS process** spawned by a host-owned supervisor, not by the plugin.

- One worker per job (default). Long-lived workers, if added later, are still one plugin identity per process.
- The worker binary is host-owned (`desktop-host` or a future `plugin-worker`), never a file from the plugin package.
- The plugin package is mounted read-only into the worker. The worker loads only what the Capability Broker admits.
- The host API process, PostgreSQL, Credential Vault, and WebView remain in other processes.

### 2.2 IPC: inherited stdio or a controlled named pipe

Allowed transports:

1. **Inherited stdio** — supervisor creates anonymous pipes, spawns the worker with stdin/stdout connected, never inherits extra handles.
2. **Controlled named pipe** — Windows `\\.\pipe\ai-novel-studio-plugin-<job_id>` (or a Unix socket under a host-owned directory). The name is random per job, created by the host, mode `0600` / DACL limited to the current user.

Forbidden:

- Listening TCP/UDP sockets chosen by the plugin
- Arbitrary localhost ports
- HTTP/WebSocket servers inside the plugin
- Reverse shells, dbus, COM, or WinRM as a control plane

The IPC frame is length-prefixed JSON (or a later bounded binary codec). Max frame size is enforced by the host. Unknown methods are rejected.

### 2.3 No arbitrary listening ports

The worker net namespace (or Windows equivalent filter) defaults to **deny all bind and connect**. A plugin that tries to `listen()` fails closed. Diagnostics may use the inherited IPC only.

## 3. Capability Broker

The broker is the only path from a worker to host capabilities. The worker never imports host Python modules.

```
Plugin job
  → Worker process
    → IPC request { method, capability, scope, handle, payload }
      → Capability Broker (host)
        → allow / deny / redact
          → scoped adapter (files, model, project metadata)
```

Rules:

- Every request names a **Capability** and a **Permission Scope**.
- Missing capability ⇒ deny.
- Granted permission that does not cover the scope ⇒ deny.
- Broker logs `(plugin_id, job_id, capability, decision, reason_code)` without payload secrets.
- Broker never forwards raw OS credentials, env, or vault material.

Phase v1 of the broker, when implemented, should start with a deny-all table and add rows only for reviewed permissions already stored on the plugin sidecar.

## 4. Scope

Every job carries an immutable **typed scope tuple**. The worker cannot widen it.

```
Scope = {
  workspace_id: WorkspaceId | null,
  project_id: ProjectId,
  storyline_id: StorylineId | null,
  modality: Modality,
  resource_id: ResourceId | null
}
```

Authorization is exact equality on each identifier the job names:

- `workspace_id`, `project_id`, `storyline_id`, and `resource_id` must match the frozen job scope **exactly**.
- String prefix matching (`novel_` prefix, path prefixes, `startswith`) is forbidden.
- A child resource (chapter, asset, export job) may be authorized only when the **host** proves the parent/child relation from its own database. The plugin cannot assert that relationship by encoding it in a string.

Cross-project reads are denied even if `project.read` was granted for another project. Missing or extra tuple fields fail closed.

## 5. Host API version negotiation

Before the first job:

1. Host advertises `host_api_version` (currently `"1"`) and a list of supported capability ids.
2. Plugin manifest declares `host_api_version` and `capabilities`.
3. Intersection is computed. Empty intersection ⇒ plugin stays inert; `execution_supported` remains false.
4. Unknown future methods are rejected with `HOST_API_UNSUPPORTED`.

v1 negotiation is already performed statically by the declarative contract. A worker, when it exists, must repeat it at process start and must not silently enable extra methods.

## 6. Credential handles

Plugins never receive API keys, OAuth tokens, vault bytes, or `.env` values.

Instead the broker issues an opaque **credential handle**:

```json
{
  "handle_id": "credh_…",
  "provider_id": "openai",
  "kind": "model.text",
  "expires_at": "…",
  "secret": null
}
```

The worker may pass `handle_id` back to the broker when asking the host to call a model. The host resolves the handle inside the vault, performs the call, and returns a redacted result. `secret` is always `null` on the wire.

Handle properties:

- Bound to `(plugin_id, job_id, provider_id)`
- Short TTL, not reusable after job end
- Revoked immediately on cancel, crash, or quarantine
- Never persisted in plugin storage

## 7. Virtual file mounts

The worker sees a synthetic filesystem, not the author's real disks.

| Mount | Mode | Contents |
|---|---|---|
| `/plugin` | read-only | The verified plugin package (JSON resources + future signed payload) |
| `/job/in` | read-only | Inputs the broker copied for this job |
| `/job/out` | write, quota | Outputs harvested at job end |
| `/tmp` | write, wiped | Scratch; discarded after the job |

Denied:

- Host source tree, `.env`, Credential Vault paths
- Novel markdown / PostgreSQL data directories
- Other plugins' directories
- `..` traversal out of a mount (same guards as declarative `relative_path`)
- Symlink / reparse escape (same as P0)

The host copies allowed outputs after hash, size, and type checks. Plugins cannot write the project database themselves.

## 8. Network

Default: **deny all**.

If `network` was reviewed and granted, the broker still requires a **domain allowlist** declared in the manifest (future field; not accepted in Contract v1 today). Wildcards are exact-suffix only (`*.example.com` does not match `notexample.com`). IP literals, link-local, metadata endpoints (`169.254.169.254`), and `localhost` are denied unless a later contract explicitly allows a named local provider.

DNS, CONNECT, and WebSocket upgrades follow the same allowlist. The worker has no raw socket API.

## 9. Resource limits

Supervisor enforces hard limits. Exceeding any limit kills the worker and fails the job.

| Limit | Suggested default | Notes |
|---|---|---|
| CPU time | 5 s | cgroup / Job Object |
| Wall clock | 15 s | includes IPC wait |
| Memory | 256 MiB | working set |
| Output size | 1 MiB | `/job/out` + IPC frames |
| File count | 32 | created in `/job/out` |
| Thread / handle count | host-defined low cap | |
| Open files | small fixed cap | |

Declarative resource limits from Contract v1 (1 MiB / file, 100 files, 10 MiB total) remain in force for the package itself.

## 10. Subprocess prohibition

The worker must not create children.

- Linux: `PR_SET_NO_NEW_PRIVS`, seccomp / landlock denying `execve`, `execveat`, `fork`+`exec`
- Windows: a Job Object with `ACTIVE_PROCESS_LIMIT=1` may **only** cap process lifetime, child creation, CPU, and memory. It is **not** a security sandbox.

Before any third-party plugin code is executed on Windows, the host must place the worker in an AppContainer / Less-Privileged AppContainer (or an equivalent OS isolation boundary that has passed an independent security review). Default deny:

- filesystem (except the virtual mounts in §7)
- registry
- network
- other users' identity
- Credential Manager / vault
- process and thread handles of the host

If those isolation primitives are unavailable or fail to apply, the host **fail-closes**: `execution_supported` stays `false`, no worker is spawned, and the job is refused.

`os.system`, `subprocess`, `powershell`, `cmd`, `wmic`, `mshta`, and equivalent are policy-fail, not "unsupported". A violation quarantines the plugin.

## 11. Crash, restart, quarantine

| Event | Host action |
|---|---|
| Worker non-zero exit | job `FAILED`; no retry unless the author re-runs |
| Worker timeout | kill process tree; job `FAILED` |
| IPC protocol break | kill; quarantine if repeated |
| Limit breach | kill; record `PLUGIN_RESOURCE_TOO_LARGE` or a future runtime code |
| Crash loop (≥3 in a window) | plugin `QUARANTINED`; jobs refused until manual review |

Quarantine is a host sidecar state. It does not delete the package. It does not auto-recover. Governance UI must show quarantine as **not executable**.

The supervisor never restarts a worker to "finish" a cancelled or timed-out job.

## 12. Task / job provenance

Every execution attempt is an immutable record:

```
execution_attempt_id
plugin_id
plugin_version
package_sha256
manifest_sha256
host_api_version
job_id
scope
requested_capabilities
granted_capabilities
credential_handle_ids   # ids only
started_at / ended_at
decision                # SUCCEEDED | FAILED | CANCELLED | REJECTED_LATE
output_sha256
```

Provenance is written by the host, not the plugin. Authors can see that a result belongs to a specific attempt. Downstream workflow nodes must store `execution_attempt_id`.

## 13. Late result / execution_attempt protection

A result is accepted only if:

1. `execution_attempt_id` matches the **current** attempt
2. the job is still `RUNNING`
3. the worker pid / pipe still belongs to that attempt
4. wall-clock has not expired

Otherwise the result is `REJECTED_LATE` and discarded. This blocks:

- a killed worker flushing stdout after timeout
- a reused named pipe delivering a previous job's payload
- a plugin retrying an old handle after cancel

Cancellation is synchronous from the author's point of view: the host marks the attempt cancelled, closes IPC, kills the process, then ignores any subsequent frames.

## 14. Plugin signatures, publisher trust, revocation

Contract v1 `publisher` is **unverified metadata**. A future signing layer must be independent of that string.

Required before any code execution:

- Package signature over `(manifest, resource bytes, plugin id, version)`
- Publisher key identity distinct from the display name
- Host trust store with pin / TOFU policy
- Revocation list checked at discover, activate, and job start
- Fail closed if the key is unknown, expired, or revoked

Unsigned packages may remain valid as **declarative JSON** (current v1). They must never become executable merely because a worker exists.

Revocation does not require deleting files. Discover may still list the package with `publisher_trust=revoked` and `execution_supported=false`.

## 15. Plugin update and state migration

Updates are host-driven. There is no plugin auto-updater and no marketplace download in this design.

On replace:

1. New package must pass Contract v1 validation independently
2. Hash mismatch with the previously activated package ⇒ fail closed until the author re-reviews
3. Sidecar state (granted permissions, status) is **not** reused if `id` is the same but `version` or permission set changed
4. Permission review is required again if `requested_permissions` grew
5. In-flight jobs using the old `package_sha256` finish or cancel; they do not hot-swap code
6. Worker-local state under `/tmp` is discarded; plugins must not assume durable local disk

Declarative resources are always re-hashed (already implemented by `DeclarativePluginCatalog`).

## 16. UI contributions are declarative

Plugins must not:

- inject JS/CSS into the host WebView
- call `dangerouslySetInnerHTML` equivalents
- supply clickable URLs, images, fonts, or scripts that the host loads
- register native menu handlers or DLL hooks

Future UI contributions, if any, are **JSON descriptors** (label, slot, icon id from a host set, action id). The host renders them as React text/components it already trusts. Plugin-provided HTML is data, never markup. This matches the current governance UI rules.

## 17. Shared contracts with Node Workflow and Provider Runtime 2.0

The worker, the future Node Workflow engine, and Provider Runtime 2.0 should share the same vocabulary so a plugin-contributed node is not a second permission system.

| Type | Role |
|---|---|
| `NodeType` | Stable id of a node or tool (`writing.preset.apply`, `workflow.template.instantiate`, …) |
| `InputSchema` | JSON Schema for job inputs; validated before the worker starts |
| `OutputSchema` | JSON Schema for harvested outputs; extra fields stripped |
| `Capability` | Broker capability id from the existing allowlist (not expanded in v1) |
| `RuntimeProfile` | Declares CPU/memory/time/network class the supervisor applies |
| `Permission Scope` | Workspace / project / modality / resource tuple from §4 |

A workflow node that would execute plugin code must attach `execution_attempt_id` and must refuse to run while `execution_supported` is false. Instantiating a `workflow_templates` JSON document is **not** execution; it remains a data copy.

Provider Runtime 2.0 must not register a plugin as a Provider unless:

- the plugin is signed
- `provider` capability was reviewed
- the worker is implemented
- credential access uses handles only

None of those gates are open today.

## 18. Explicitly not implemented

The following remain unimplemented for **plugin** execution after Phase 2B:

- Third-party plugin Worker (the host-owned **test** worker is a prototype only; see [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md) and [plugin_runtime_phase2b_windows_sandbox.md](plugin_runtime_phase2b_windows_sandbox.md))
- Capability Broker **runtime** (the pure policy evaluator exists; it does not broker real capabilities)
- Plugin signatures, publisher trust store, revocation
- Marketplace, install, update, uninstall, online download
- Provider plugins
- ComfyUI plugins
- Blender plugins
- Any third-party Python / JavaScript / Shell / PowerShell / native code execution
- Automatic permission grant
- Production-ready AppContainer / LPAC (`os_sandbox_ready` remains false; Job Object is not a security sandbox)
- Changing `execution_supported` to `true`

If a change to P1 / P1.5 would require `execution_supported = true`, that change is out of bounds and must be rejected.

Phase 2A **did** implement: host-owned test worker, supervisor prototype, bounded versioned stdio IPC, handshake, job/attempt binding via Phase 1 `evaluate_late_result`, timeout, cancellation, crash detection, host-side IPC quota, and owned-process cleanup. It did **not** implement OS memory/CPU enforcement, real mounts, or a production execution API/UI.

## 19. Rollout sketch (future, not this PR)

1. Keep Contract v1 + catalog + governance UI (done)
2. Freeze execution contracts + fail-closed policy (Phase 1, done)
3. Implement supervisor + empty **host-owned** worker that only pings and exits (Phase 2A prototype, done for the test worker; not a plugin worker)
4. Add Capability Broker with deny-all runtime adapters
5. Add signing and revocation **before** loading any plugin code
6. Allow a single host-written conformance plugin under test flags
7. Only then consider reviewed third-party declarative-plus-code packages

Each step is a separate review. The plugin worker described in this file is still blocked on steps 4–5 and on a **proven** Windows AppContainer / LPAC (or an independently reviewed equivalent). Phase 2B landed a fail-closed AppContainer prototype; it is not that gate until a real Windows host proves `TokenIsAppContainer`. Job Object is not that gate.

## 20. Current host invariants (must not regress)

- `GET /api/plugins/runtime-status` → `execution_supported=false`, `sandbox=NOT_CONFIGURED`, `isolation=DENY_ALL`
- Release readiness `plugin_runtime.status = DEFERRED`
- Discover / catalog APIs never return absolute paths or raw exceptions
- Activation of a manifest is not execution
- Declarative packs stay data-only; they do not become executable because a runtime contract exists
