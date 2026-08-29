# Plugin Runtime — Phase 2A Host-owned Test Worker + IPC

Status: **host-owned test worker prototype**. This is not third-party plugin execution.

| Claim | Value |
|---|---|
| Host-owned Test Worker | IMPLEMENTED (prototype) |
| Supervisor prototype | IMPLEMENTED |
| Bounded versioned IPC | IMPLEMENTED (`protocol_version="1"`) |
| Handshake | IMPLEMENTED |
| Job / attempt binding | IMPLEMENTED (reuses Phase 1 `evaluate_late_result`) |
| Timeout / cancel / crash | IMPLEMENTED |
| IPC output quota | IMPLEMENTED (host supervisor) |
| Process / pipe cleanup | IMPLEMENTED (owned-PID registry) |
| Third-party plugin Worker | NOT IMPLEMENTED |
| Third-party plugin code execution | DISABLED |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| OS sandbox ready | `false` / `NOT_CONFIGURED` |
| AppContainer / LPAC | NOT IMPLEMENTED |
| Job Object security isolation | NOT IMPLEMENTED |
| Capability Broker runtime | NOT IMPLEMENTED |
| Credential resolver | NOT IMPLEMENTED |
| Signature verification | NOT IMPLEMENTED |
| Provider / Blender / ComfyUI plugins | NOT IMPLEMENTED |
| Marketplace | NOT IMPLEMENTED |
| Public execute API | none |
| Run Plugin UI | none |
| Database schema / migrations | 0 |
| Frontend production changes | 0 |
| Release claim | `0.7.0 Beta` (unchanged) |

Phase 2A proves that Phase 1 contracts can control a **fixed, host-owned** process:

```
Host → Supervisor → Host-owned Test Worker
```

It does **not** run plugin packages, plugin Python/JS/native/shell, or any user-controlled executable. Shipping these modules does not enable production plugin execution.

Related: [plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md), [plugin_sdk_v1.md](plugin_sdk_v1.md), [plugin_security_model.md](plugin_security_model.md), [plugin_worker_runtime_design.md](plugin_worker_runtime_design.md).

## Implemented in Phase 2A

| Surface | Module |
|---|---|
| Length-prefixed JSON IPC | `app/plugin_worker_protocol.py` |
| Frozen spawn spec | `spawn_host_test_worker()` in `app/plugin_worker_process.py` |
| Host-owned test worker | `python -u -m app.plugin_test_worker` |
| Supervisor prototype | `HostTestWorkerSupervisor` in `app/plugin_test_worker_supervisor.py` |
| Component-aware virtual-mount path check | `is_allowed_virtual_mount_path` in `app/plugin_runtime_contracts.py` |

`GET /api/plugins/runtime-status` is unchanged: `execution_supported=false`, `sandbox=NOT_CONFIGURED`, `isolation=DENY_ALL`. Production startup (`app.main`, FastAPI routes, catalog, frontend, desktop-host) does **not** import or spawn the test worker.

## What the test worker is

A repository-built, fixed implementation that the supervisor starts with a **closed argv**:

```
[sys.executable, "-u", "-m", "app.plugin_test_worker"]
```

There is no `command: str`, no plugin-controlled executable path, no plugin-controlled module name, and no generic `run_command` / `execute_path` / `spawn` / `invoke_module` API.

Allowed operations (allowlist, dict dispatch — **not** `getattr`):

| Operation | Purpose |
|---|---|
| `PING` | Handshake-level liveness |
| `ECHO_SAFE` | Echo a bounded test payload (`[A-Za-z0-9._\- ]{0,1024}`) |
| `SLEEP` | Wall-timeout and cancel prototype |
| `RETURN_FIXED_RESULT` | Fixed `{fixed: "host-test-worker"}` |
| `CRASH_FOR_TEST` | Unexpected `os._exit(17)` |
| `EMIT_MALFORMED_FRAME_FOR_TEST` | Invalid JSON frame |
| `EMIT_OVERSIZED_FRAME_FOR_TEST` | Declared length `MAX_FRAME_BYTES + 1` |
| `EMIT_TRUNCATED_FRAME_FOR_TEST` | Partial frame then exit |
| `ATTEMPT_SUBPROCESS_FOR_TEST` | Returns `SUBPROCESS_PROHIBITED` without spawning |

The worker does not read the database, project content, vault, providers, plugin packages, or the network. It has no `eval` / `exec` / command / script / module / entrypoint fields.

## Spawn boundary

`spawn_host_test_worker()` takes **no arguments**. The only image is the current host interpreter. The only module is `app.plugin_test_worker`. Plugin id, manifest, and resource JSON cannot choose the process.

POSIX adapter: `start_new_session=True` plus `killpg` on terminate. Windows adapter: `terminate()` then `kill()`. Ownership is tracked in an in-process PID registry; cleanup is ownership-aware and does not kill unrelated processes.

## IPC transport

Inherited stdin/stdout only. No localhost port, HTTP, WebSocket, plugin-chosen named pipe, or network socket.

Frame format: 4-byte big-endian length + UTF-8 JSON. Limits:

| Limit | Value | Enforcement |
|---|---|---|
| `MAX_FRAME_BYTES` | 64 KiB | host + worker, fail-closed |
| `MAX_TOTAL_OUTPUT_BYTES` | 64 KiB | **host supervisor IPC quota** |
| `MAX_STDERR_BYTES` | 8 KiB | bounded drain; not a secret transport |
| `MAX_JSON_DEPTH` | 8 | fail-closed |
| JSON keys / list length | 32 | fail-closed |

Unknown fields, unknown message types, version mismatch, invalid UTF-8, trailing garbage, truncated frames, and oversized declared lengths are rejected. The host supervisor is not allowed to crash on a bad frame.

**IPC quota enforcement = IMPLEMENTED** at the supervisor. **OS memory / CPU enforcement = NOT IMPLEMENTED** (`ResourceLimitPolicy.enforcement_implemented` remains `false`).

## Envelope and protocol version

```
{
  protocol_version,   # must be "1"
  message_type,       # HELLO | READY | JOB_START | JOB_RESULT | JOB_ERROR | CANCEL | SHUTDOWN
  job_id,             # UUID, or null for HELLO/READY/SHUTDOWN
  execution_attempt_id,
  message_id,         # UUID
  payload             # allowlisted keys per message type
}
```

`PLUGIN_WORKER_PROTOCOL_VERSION = "1"`. Host and worker different versions → immediate `PROTOCOL_VERSION_MISMATCH`. There is no compatibility fallback.

Handshake: Host `HELLO` with `worker_identity="host.test_worker"` and a host-issued `session_nonce`. Worker replies `READY` with the same identity and nonce. No successful handshake ⇒ supervisor does not treat the worker as `READY`. Timeout, wrong version, or malformed handshake ⇒ terminate.

## Job / attempt identity

Supervisor jobs carry Phase 1 `job_id` and `execution_attempt_id`. Worker results must echo the same pair. The host calls existing `evaluate_late_result`; it does not copy that logic.

- attempt mismatch → `STALE_EXECUTION_ATTEMPT`
- job mismatch → `JOB_ID_MISMATCH`
- not running (including after timeout / cancel) → `ATTEMPT_NOT_RUNNING`

Retry uses existing `begin_retry` (new `execution_attempt_id`, same `job_id`). A late result from attempt 1 cannot become SUCCESS for attempt 2.

## Timeout, cancel, crash

| Event | Lifecycle | Worker process |
|---|---|---|
| Wall timeout (`SLEEP` past `wall_timeout_ms`) | `TIMED_OUT` | terminated; pipes closed; late SUCCESS rejected |
| Host cancel | `RUNNING` → `CANCEL_REQUESTED` → `CANCELLED` | cooperative CANCEL, then terminate if needed; result cannot be SUCCESS |
| Unexpected exit (`CRASH_FOR_TEST`) | `FAILED` | reason `WORKER_CRASH`; exit status recorded where safe |
| Malformed / oversized / truncated frame | `FAILED` | worker terminated |

stderr is bounded and never treated as a credential/DSN transport. This phase has no public API; the contract still forbids leaking stderr to users later.

## Process tree

The test worker does not start children. `ATTEMPT_SUBPROCESS_FOR_TEST` returns `SUBPROCESS_PROHIBITED` and does **not** expose a generic subprocess interface. Phase 2A does not implement OS-level no-new-privs / AppContainer process-tree enforcement.

## Virtual-mount path hardening

Before any real mount exists, `_looks_like_host_absolute_path` is component-aware:

- `/plugin`, `/plugin/foo`, `/job/in`, `/job/out`, `/tmp` (and children without `.` / `..` / empty segments) are the virtual namespace
- `/plugin-evil`, `/job/input`, `/tmpfoo`, `/plugin/../etc/passwd` remain host-absolute and forbidden

No real mounts are created.

## Test-only vs production

Supervisor primitives live under `app/` so tests can import them. Production startup must not import or activate them. `tests/test_plugin_runtime_phase2a_test_worker.py` asserts `app.main` does not load `plugin_test_worker_supervisor` / `plugin_test_worker`, and that runtime status stays `execution_supported=false`.

Job/worker state is **in-memory only**. No schema, no migrations, no durable execution tables.

## Not implemented

- Third-party plugin Worker or plugin package code loading
- AppContainer, LPAC, Job Object security isolation, OS sandbox
- Capability Broker runtime, credential resolver, signature verification
- Provider plugin, Blender plugin, ComfyUI plugin, marketplace
- `POST /api/plugins/.../execute`, Run Plugin UI, Worker Console
- OS enforcement of CPU / memory / file-count limits
- Real virtual mounts

A future Phase 2B / security gate is required before any third-party code runs. Job Object remains **not** a sandbox.

## Verification

Targeted tests: `tests/test_plugin_runtime_phase2a_test_worker.py` plus Phase 1 adversarial additions in `tests/test_plugin_runtime_foundation_phase1.py`. Existing plugin SDK, discovery, catalog, and official declarative pack tests must still pass.

Each supervisor test tears down owned workers and asserts `OWNED WORKER PROCESSES = 0`. Unrelated processes are not terminated.
